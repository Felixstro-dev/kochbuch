from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, require_write
from app.core.security import API_KEY_PREFIX, generate_token, hash_token, key_prefix
from app.db.base import utcnow
from app.db.models import ApiKey
from app.db.session import get_db
from app.schemas.api_keys import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.services import auth as auth_service

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _get_owned_key(db: Session, key_id: str, principal: Principal) -> ApiKey:
    key = db.get(ApiKey, key_id)
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API-Key nicht gefunden.")
    is_owner = principal.user is not None and key.user_id == principal.user.id
    if not is_owner and not principal.is_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API-Key nicht gefunden.")
    return key


@router.get("")
def list_keys(
    all_users: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[ApiKeyOut]:
    stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
    if all_users:
        if not principal.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administratorrechte erforderlich.",
            )
    else:
        if not principal.user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Diese Ansicht erfordert eine Benutzersitzung.",
            )
        stmt = stmt.where(ApiKey.user_id == principal.user.id)
    keys = list(db.scalars(stmt))
    return [ApiKeyOut.model_validate(key) for key in keys]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    payload: ApiKeyCreate,
    request: Request,
    principal: Principal = Depends(require_write),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    if not principal.user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API-Keys können nur für Benutzerkonten erstellt werden.",
        )
    scopes = list(dict.fromkeys(payload.scopes))
    if "admin" in scopes and not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nur Administratoren dürfen Admin-Keys erstellen.",
        )
    if "write" in scopes and "read" not in scopes:
        scopes.insert(0, "read")
    secret = generate_token(API_KEY_PREFIX)
    expires_at = (
        utcnow() + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days
        else None
    )
    key = ApiKey(
        user_id=principal.user.id,
        name=payload.name.strip(),
        prefix=key_prefix(secret),
        key_hash=hash_token(secret, request.app.state.settings.token_pepper),
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    auth_service.record_audit(
        db,
        action="api_key.created",
        user_id=principal.user.id,
        request=request,
        detail={"key_id": key.id, "scopes": scopes},
    )
    return ApiKeyCreated(**ApiKeyOut.model_validate(key).model_dump(), secret=secret)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_key(
    key_id: str,
    request: Request,
    principal: Principal = Depends(require_write),
    db: Session = Depends(get_db),
) -> None:
    key = _get_owned_key(db, key_id, principal)
    if not key.revoked_at:
        key.revoked_at = utcnow()
        db.commit()
        auth_service.record_audit(
            db,
            action="api_key.revoked",
            user_id=principal.user.id if principal.user else None,
            request=request,
            detail={"key_id": key.id},
        )


@router.post("/{key_id}/rotate", response_model=ApiKeyCreated)
def rotate_key(
    key_id: str,
    request: Request,
    principal: Principal = Depends(require_write),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    old = _get_owned_key(db, key_id, principal)
    if not principal.user or old.user_id != principal.user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keys können nur für das eigene Konto rotiert werden.",
        )
    if old.revoked_at:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Der Key ist bereits widerrufen."
        )
    old.revoked_at = utcnow()
    secret = generate_token(API_KEY_PREFIX)
    new_key = ApiKey(
        user_id=old.user_id,
        name=old.name,
        prefix=key_prefix(secret),
        key_hash=hash_token(secret, request.app.state.settings.token_pepper),
        scopes=old.scopes,
        expires_at=utcnow() + timedelta(days=30) if old.expires_at else None,
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    auth_service.record_audit(
        db,
        action="api_key.rotated",
        user_id=principal.user.id,
        request=request,
        detail={"old_key_id": old.id, "new_key_id": new_key.id},
    )
    return ApiKeyCreated(**ApiKeyOut.model_validate(new_key).model_dump(), secret=secret)
