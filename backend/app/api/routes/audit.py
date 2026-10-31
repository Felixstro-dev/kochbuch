from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_admin
from app.db.models import AuditLog
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    entries = list(
        db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
    )
    return [
        {
            "id": entry.id,
            "action": entry.action,
            "user_id": entry.user_id,
            "detail": entry.detail,
            "ip_address": entry.ip_address,
            "created_at": entry.created_at,
        }
        for entry in entries
    ]
