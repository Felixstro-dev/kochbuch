from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.ratelimit import SlidingWindowLimiter
from app.db.base import Base, make_engine, make_session_factory
from app.db.models import User  # noqa: F401  (register models)
from app.providers.registry import ProviderRegistry
from app.services.auth import bootstrap_admin, cleanup_expired_sessions
from app.services.images import ImageService
from app.services.recipes import RecipeService
from app.services.search import SearchService
from app.services.update_check import UpdateChecker, start_update_loop

BACKEND_DIR = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def _run_migrations(database_url: str) -> None:
    from alembic import command
    from alembic.config import Config
    from app.core.logging import progress_bar, C
    logger = logging.getLogger(__name__)
    logger.info(f"{C['cyan']}⚡ Migration startet...{C['reset']}")
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    logger.info(f"{C['green']}✓ Migration abgeschlossen{C['reset']}")


def _bootstrap(settings: Settings, session_factory) -> None:
    with session_factory() as db:
        cleanup_expired_sessions(db)
        if settings.admin_username and settings.admin_password:
            try:
                user = bootstrap_admin(
                    db,
                    username=settings.admin_username,
                    password=settings.admin_password,
                )
                if user:
                    logger.info("Bootstrap-Administrator '%s' angelegt.", user.username)
            except Exception:
                logger.exception("Bootstrap-Administrator konnte nicht angelegt werden.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    settings.data_path.mkdir(parents=True, exist_ok=True)

    engine = make_engine(settings.resolved_database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from app.core.logging import C, progress_bar
        logger.info(f"{C['bold']}▶ Startup-Phase 1/4: Datenbank & Migration{C['reset']}")
        if settings.testing:
            Base.metadata.create_all(bind=engine)
        elif settings.auto_migrate:
            _run_migrations(settings.resolved_database_url)
        else:
            Base.metadata.create_all(bind=engine)

        logger.info(f"{C['bold']}▶ Startup-Phase 2/4: Bootstrap & Services{C['reset']}")
        _bootstrap(settings, session_factory)

        registry = ProviderRegistry(settings, session_factory)
        with session_factory() as db:
            from app.services import settings as settings_service
            registry.fetcher.apply_values(settings_service.get_values(db))
        logger.info(f"{C['bold']}▶ Startup-Phase 3/4: Registry & Services{C['reset']}")
        app.state.registry = registry
        app.state.fetch_pipeline = registry.fetcher
        app.state.image_service = ImageService(settings, registry.fetcher)
        app.state.search_service = SearchService(registry, session_factory, settings)
        app.state.recipe_service = RecipeService(registry, session_factory, settings)

        from app.core.logging import C
        logger.info(
            f"{C['bold']}%s %s gestartet (%s){C['reset']}", settings.app_name, __version__, settings.environment
        )

        logger.info(f"{C['bold']}▶ Startup-Phase 4/4: Update-Check {C['cyan']}aktiviert{C['reset']} {'✓' if settings.update_check_enabled else '✗'}{C['reset']}")
        update_task: asyncio.Task | None = None
        if settings.update_check_enabled and not settings.testing:
            from app.core.logging import C
            logger.info(f"{C['cyan']}▶ Update-Check gestartet (Interval: {settings.update_check_interval}s){C['reset']}")
            checker = UpdateChecker(
                settings.update_image, settings.git_sha, settings.update_check_interval
            )
            app.state.update_checker = checker
            update_task = start_update_loop(checker)

        yield
        if update_task:
            update_task.cancel()
        await registry.close()
        engine.dispose()

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description="Rezeptmanager-API. Anmeldung per Session-Cookie oder API-Key.",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.login_limiter = SlidingWindowLimiter(
        settings.login_rate_limit, settings.login_rate_window
    )

    if settings.cors_origin_list:
        allow_all_origins = "*" in settings.cors_origin_list
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if allow_all_origins else settings.cors_origin_list,
            # The wildcard cannot be combined with credentials; the HA card
            # authenticates with an API key header instead of cookies.
            allow_credentials=not allow_all_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["ETag", "Content-Disposition"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            f"frame-ancestors {settings.frame_ancestors}"
        )
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        logger.debug(
            "%s %s %s %.1fms", request.method, request.url.path, response.status_code, duration_ms
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unbehandelter Fehler bei %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Interner Serverfehler."},
        )

    app.include_router(api_router)

    @app.get("/api", include_in_schema=False)
    def api_root() -> dict[str, str]:
        return {
            "name": f"{settings.app_name} API",
            "version": __version__,
            "docs": "/api/docs",
        }

    frontend_dir = settings.frontend_dir
    if frontend_dir and (frontend_dir / "index.html").exists():
        from app.web import mount_frontend

        mount_frontend(app, frontend_dir)
    else:

        @app.get("/", include_in_schema=False)
        def root() -> dict[str, str]:
            return {
                "name": settings.app_name,
                "version": __version__,
                "status": "Backend läuft. Frontend noch nicht gebaut.",
                "docs": "/api/docs",
            }

    return app


app = create_app()
