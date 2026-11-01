from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    api_keys,
    audit,
    auth,
    bring,
    embed_tokens,
    health,
    recipes,
    settings,
    system,
    users,
    wishes,
    export,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(api_keys.router)
api_router.include_router(embed_tokens.router)
api_router.include_router(settings.router)
api_router.include_router(system.router)
api_router.include_router(audit.router)
api_router.include_router(recipes.router)
api_router.include_router(wishes.router)
api_router.include_router(bring.router)
api_router.include_router(export.router)