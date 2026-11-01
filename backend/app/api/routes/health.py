from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    settings = request.app.state.settings
    return {
        "status": "ok",
        "version": __version__,
        "git_sha": settings.git_sha if settings.git_sha != "unknown" else None,
        "app": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/health/ready")
def ready(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/health/shopping-list")
async def health_shopping() -> dict[str, object]:
    """Schnellcheck, ob Bring-Zugang konfiguriert und erreichbar ist."""
    from app.services.bring_service import _get_bring
    try:
        bring = await _get_bring()
        await bring.login()
        return {"status": "ok", "provider": "bring", "reachable": True}
    except Exception as exc:
        return {"status": "degraded", "provider": "bring", "reachable": False, "reason": str(exc)[:120]}
