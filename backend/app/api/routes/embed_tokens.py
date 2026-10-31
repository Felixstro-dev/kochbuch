from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_admin
from app.core.security import EMBED_TOKEN_PREFIX, generate_token, hash_token, key_prefix
from app.db.base import utcnow
from app.db.models import EmbedToken
from app.db.session import get_db
from app.schemas.api_keys import EmbedTokenCreate, EmbedTokenCreated, EmbedTokenOut
from app.services import auth as auth_service

router = APIRouter(prefix="/embed-tokens", tags=["embed"])


@router.get("", response_model=list[EmbedTokenOut])
def list_embed_tokens(
    _: Principal = Depends(require_admin), db: Session = Depends(get_db)
) -> list[EmbedTokenOut]:
    tokens = list(db.scalars(select(EmbedToken).order_by(EmbedToken.created_at.desc())))
    return [EmbedTokenOut.model_validate(token) for token in tokens]


@router.post("", response_model=EmbedTokenCreated, status_code=status.HTTP_201_CREATED)
def create_embed_token(
    payload: EmbedTokenCreate,
    request: Request,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> EmbedTokenCreated:
    secret = generate_token(EMBED_TOKEN_PREFIX)
    token = EmbedToken(
        name=payload.name.strip(),
        prefix=key_prefix(secret),
        token_hash=hash_token(secret, request.app.state.settings.token_pepper),
        created_by=principal.user.id if principal.user else None,
        expires_at=utcnow() + timedelta(hours=payload.expires_in_hours),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    auth_service.record_audit(
        db,
        action="embed_token.created",
        user_id=principal.user.id if principal.user else None,
        request=request,
        detail={"token_id": token.id},
    )
    return EmbedTokenCreated(**EmbedTokenOut.model_validate(token).model_dump(), token=secret)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_embed_token(
    token_id: str,
    request: Request,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    token = db.get(EmbedToken, token_id)
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token nicht gefunden.")
    if not token.revoked_at:
        token.revoked_at = utcnow()
        db.commit()
        auth_service.record_audit(
            db,
            action="embed_token.revoked",
            user_id=principal.user.id if principal.user else None,
            request=request,
            detail={"token_id": token.id},
        )
