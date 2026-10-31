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
        "app": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/health/ready")
def ready(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
