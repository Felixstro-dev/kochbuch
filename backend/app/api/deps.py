from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import constant_time_equals, hash_token
from app.db.base import utcnow
from app.db.models import ApiKey, EmbedToken, User
from app.db.session import get_db
from app.services.auth import resolve_session


@dataclass
class Principal:
    auth_type: Literal["session", "api_key", "embed", "public"]
    user: User | None = None
    scopes: set[str] = field(default_factory=lambda: {"read"})
    session_token: str | None = None
    api_key_id: str | None = None
    embed_token_id: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.auth_type in {"session", "api_key"}

    @property
    def is_admin(self) -> bool:
        if self.auth_type == "session" and self.user:
            return self.user.role == "admin"
        return "admin" in self.scopes


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


def _unauthorized(detail: str = "Nicht angemeldet.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _load_api_key(db: Session, token: str, pepper: str) -> Principal | None:
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == hash_token(token, pepper)))
    if not key or key.revoked_at or not key.user or not key.user.is_active:
        return None
    if key.expires_at and key.expires_at <= utcnow():
        return None
    now = utcnow()
    if not key.last_used_at or key.last_used_at < now - timedelta(seconds=60):
        key.last_used_at = now
        db.commit()
    scopes = set(key.scopes or ["read"])
    if "admin" in scopes:
        scopes |= {"read", "write"}
    return Principal(
        auth_type="api_key",
        user=key.user,
        scopes=scopes,
        api_key_id=key.id,
    )


def _load_embed_token(db: Session, token: str, pepper: str) -> Principal | None:
    embed = db.scalar(
        select(EmbedToken).where(EmbedToken.token_hash == hash_token(token, pepper))
    )
    if not embed or embed.revoked_at:
        return None
    if embed.expires_at and embed.expires_at <= utcnow():
        return None
    embed.last_used_at = utcnow()
    db.commit()
    return Principal(
        auth_type="embed",
        scopes={"read"},
        embed_token_id=embed.id,
        user=db.get(User, embed.created_by) if embed.created_by else None,
    )


def get_optional_principal(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> Principal | None:
    header = request.headers.get("authorization", "")
    bearer = header[7:].strip() if header.lower().startswith("bearer ") else ""
    api_key = request.headers.get("x-api-key", "").strip()
    embed_token = request.headers.get("x-embed-token", "").strip()
    token = bearer or api_key

    if embed_token or (bearer and bearer.startswith("kbe_")):
        principal = _load_embed_token(db, embed_token or bearer, settings.token_pepper)
        if not principal:
            raise _unauthorized("Ungültiger oder abgelaufener Embed-Token.")
        return principal

    if token:
        principal = _load_api_key(db, token, settings.token_pepper)
        if not principal:
            raise _unauthorized("Ungültiger oder abgelaufener API-Key.")
        return principal

    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token:
        resolved = resolve_session(db, session_token, settings.token_pepper)
        if resolved:
            user, session = resolved
            return Principal(
                auth_type="session",
                user=user,
                scopes={"read", "write", "admin"} if user.role == "admin" else {"read", "write"},
                session_token=session_token,
            )

    if settings.embed_public:
        return Principal(auth_type="public", scopes={"read"})

    return None


def get_principal(
    principal: Principal | None = Depends(get_optional_principal),
) -> Principal:
    if principal is None:
        raise _unauthorized()
    return principal


def _verify_csrf(request: Request, principal: Principal) -> None:
    if principal.auth_type != "session":
        return
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    settings: Settings = request.app.state.settings
    cookie = request.cookies.get(settings.csrf_cookie_name, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not constant_time_equals(cookie, header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF-Token fehlt oder ist ungültig.",
        )


def require_write(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Principal:
    if "write" not in principal.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dieser Zugang ist nur lesend.",
        )
    _verify_csrf(request, principal)
    return principal


def require_admin(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Principal:
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administratorrechte erforderlich.",
        )
    _verify_csrf(request, principal)
    return principal


def require_session(principal: Principal = Depends(get_principal)) -> Principal:
    if principal.auth_type != "session":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Diese Aktion erfordert eine Anmeldung in der Oberfläche.",
        )
    return principal


def require_contributor(
    request: Request,
    principal: Principal = Depends(get_principal),
) -> Principal:
    """Schreibzugriff für Wünsche: angemeldete Nutzer (mit CSRF) oder – wenn
    das Backend öffentlich erreichbar ist – anonyme Besucher aus dem iframe."""
    if principal.auth_type in {"session", "api_key"} and "write" not in principal.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dieser Zugang ist nur lesend.",
        )
    if principal.auth_type in {"session", "api_key"}:
        _verify_csrf(request, principal)
    return principal
