from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, require_contributor, require_write
from app.api.serializers import detail_out, summary_out
from app.db.session import get_db
from app.providers.base import RecipeNotFound, SearchQuery
from app.schemas.recipes import (
    ProviderOut,
    RecipeDetailOut,
    RecipeListResponse,
    RecipePatch,
    ResolveRequest,
    SearchResponse,
)
from app.services.images import ImageService
from app.services.recipes import RecipeService, RecipeServiceError
from app.services.search import SearchService, SearchServiceError

router = APIRouter(tags=["recipes"])


def _services(request: Request) -> tuple[SearchService, RecipeService, ImageService]:
    return (
        request.app.state.search_service,
        request.app.state.recipe_service,
        request.app.state.image_service,
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    background: BackgroundTasks,
    q: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1, le=100),
    limit: int = Query(default=24, ge=1, le=50),
    sources: str | None = Query(default=None),
    max_time: int | None = Query(default=None, ge=1, le=600),
    difficulty: int | None = Query(default=None, ge=1, le=3),
    category: str | None = Query(default=None, max_length=80),
    sort: str = Query(default="relevance", pattern="^(relevance|rating|time)$"),
    refresh: bool = Query(default=False),
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> SearchResponse:
    search_service, _, images = _services(request)
    provider_names = (
        [name.strip() for name in sources.split(",") if name.strip()] if sources else None
    )
    query = SearchQuery(
        text=q.strip(),
        page=page,
        limit=limit,
        max_time=max_time,
        difficulty=difficulty,
        category=category.strip() if category else None,
        sort=sort,
    )
    if not query.text:
        provider_names = provider_names or []
        return SearchResponse(
            items=[],
            total=0,
            page=page,
            limit=limit,
            providers=provider_names,
        )
    try:
        result = await search_service.search(
            db,
            query,
            sources=provider_names,
            background=background,
            refresh=refresh,
        )
    except SearchServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SearchResponse(
        items=[summary_out(item, images) for item in result.items],
        total=result.total,
        page=result.page,
        limit=result.limit,
        providers=result.providers,
        cached=result.cached,
        stale=result.stale,
        errors=result.errors,
        took_ms=result.took_ms,
    )


@router.get("/providers", response_model=list[ProviderOut])
def providers(
    request: Request,
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[ProviderOut]:
    from app.services import settings as settings_service

    registry = request.app.state.registry
    enabled = settings_service.get_enabled_providers(
        db, request.app.state.settings.enabled_provider_list
    )
    return [
        ProviderOut(
            name=provider.name,
            label=provider.label,
            can_search=provider.can_search,
            enabled=provider.name in enabled,
        )
        for provider in registry.providers.values()
    ]


@router.get("/favorites", response_model=RecipeListResponse)
def favorites(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> RecipeListResponse:
    _, recipes, images = _services(request)
    items = recipes.list_favorites(db, limit=limit)
    return RecipeListResponse(
        items=[summary_out(item, images) for item in items], total=len(items)
    )


@router.get("/saved", response_model=RecipeListResponse)
def saved(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> RecipeListResponse:
    _, recipes, images = _services(request)
    items = recipes.list_saved(db, limit=limit)
    return RecipeListResponse(
        items=[summary_out(item, images) for item in items], total=len(items)
    )


@router.post("/recipes/resolve", response_model=RecipeDetailOut)
async def resolve_recipe(
    payload: ResolveRequest,
    request: Request,
    background: BackgroundTasks,
    _: Principal = Depends(require_contributor),
    db: Session = Depends(get_db),
) -> RecipeDetailOut:
    _, recipes, images = _services(request)
    try:
        result = await recipes.resolve_url(db, payload.url, background=background)
    except RecipeNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RecipeServiceError as exc:
        detail = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if "nicht gefunden" in detail.lower() or "existiert nicht" in detail.lower()
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=detail) from exc
    return detail_out(
        result.detail,
        images,
        fetched_at=_iso(result.fetched_at),
        stale=result.stale,
    )


@router.get("/recipes/{cache_key}", response_model=RecipeDetailOut)
async def get_recipe(
    cache_key: str,
    request: Request,
    background: BackgroundTasks,
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> RecipeDetailOut:
    _, recipes, images = _services(request)
    try:
        result = await recipes.get(db, cache_key, background=background)
    except RecipeNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RecipeServiceError as exc:
        detail = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if "nicht gefunden" in detail.lower() or "existiert nicht" in detail.lower()
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(status_code=code, detail=detail) from exc
    return detail_out(
        result.detail,
        images,
        fetched_at=_iso(result.fetched_at),
        stale=result.stale,
    )


@router.patch("/recipes/{cache_key}", response_model=RecipeDetailOut)
def update_recipe(
    cache_key: str,
    payload: RecipePatch,
    request: Request,
    background: BackgroundTasks,
    _: Principal = Depends(require_contributor),
    db: Session = Depends(get_db),
) -> RecipeDetailOut:
    _, recipes, images = _services(request)
    try:
        row = recipes.update(
            db,
            cache_key,
            is_favorite=payload.is_favorite,
            is_saved=payload.is_saved,
            tags=payload.tags,
            background=background,
        )
    except RecipeNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from app.services.recipe_store import detail_from_row

    return detail_out(
        detail_from_row(row),
        images,
        fetched_at=_iso(row.fetched_at),
    )


@router.get("/images/{cache_key}/{variant}")
async def get_image(
    cache_key: str,
    variant: str,
    request: Request,
    exp: int = Query(...),
    sig: str = Query(...),
    db: Session = Depends(get_db),
):
    _, _, images = _services(request)
    if not images.verify(cache_key, variant, exp, sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Ungültige Bild-Signatur."
        )
    from fastapi.responses import FileResponse

    try:
        path, etag, mime = await images.get(db, cache_key, variant)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if request.headers.get("if-none-match") == etag:
        from fastapi import Response

        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return FileResponse(
        path,
        media_type=mime,
        headers={
            "ETag": etag,
            "Cache-Control": "public, max-age=604800, immutable",
            "Content-Disposition": "inline",
        },
    )
