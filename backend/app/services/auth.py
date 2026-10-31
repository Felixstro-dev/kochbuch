from __future__ import annotations

from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import (
    generate_token,
    hash_password,
    hash_token,
    validate_password,
    verify_password,
)
from app.db.base import utcnow
from app.db.models import ApiKey, AuditLog, Session as UserSession, User


class ServiceError(Exception):
    """Business rule violation with a message safe to show to the user."""


def count_users(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def normalize_username(username: str) -> str:
    return username.strip().lower()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == normalize_username(username)))


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str = "",
    role: str = "member",
) -> User:
    username = normalize_username(username)
    if len(username) < 2:
        raise ServiceError("Der Benutzername muss mindestens 2 Zeichen lang sein.")
    if get_user_by_username(db, username):
        raise ServiceError("Dieser Benutzername ist bereits vergeben.")
    problem = validate_password(password)
    if problem:
        raise ServiceError(problem)
    user = User(
        username=username,
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not user.is_active:
        # Still run a dummy verification to reduce timing differences.
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=2$" + "0" * 22 + "$" + "0" * 43)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_session(
    db: Session,
    user: User,
    request: Request,
    *,
    ttl_days: int,
    pepper: str,
) -> tuple[str, str]:
    token = generate_token()
    csrf_token = generate_token()
    now = utcnow()
    session = UserSession(
        token_hash=hash_token(token, pepper),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(days=ttl_days),
        last_used_at=now,
        user_agent=(request.headers.get("user-agent") or "")[:300],
        ip_address=(request.client.host if request.client else "")[:64],
    )
    db.add(session)
    user.last_login_at = now
    db.commit()
    return token, csrf_token


def resolve_session(db: Session, token: str, pepper: str) -> tuple[User, UserSession] | None:
    session = db.get(UserSession, hash_token(token, pepper))
    if not session:
        return None
    now = utcnow()
    if session.expires_at <= now:
        db.delete(session)
        db.commit()
        return None
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        return None
    if session.last_used_at < now - timedelta(minutes=5):
        session.last_used_at = now
        db.commit()
    return user, session


def revoke_session(db: Session, token: str, pepper: str) -> None:
    session = db.get(UserSession, hash_token(token, pepper))
    if session:
        db.delete(session)
        db.commit()


def revoke_user_sessions(
    db: Session, user_id: str, *, except_token: str | None = None, pepper: str
) -> int:
    stmt = select(UserSession).where(UserSession.user_id == user_id)
    sessions = list(db.scalars(stmt))
    except_hash = hash_token(except_token, pepper) if except_token else None
    removed = 0
    for session in sessions:
        if except_hash and session.token_hash == except_hash:
            continue
        db.delete(session)
        removed += 1
    db.commit()
    return removed


def cleanup_expired_sessions(db: Session) -> int:
    sessions = list(db.scalars(select(UserSession).where(UserSession.expires_at <= utcnow())))
    for session in sessions:
        db.delete(session)
    if sessions:
        db.commit()
    return len(sessions)


def record_audit(
    db: Session,
    *,
    action: str,
    user_id: str | None = None,
    request: Request | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            detail=detail,
            ip_address=(request.client.host if request and request.client else "")[:64],
        )
    )
    db.commit()


def bootstrap_admin(
    db: Session,
    *,
    username: str | None,
    password: str | None,
) -> User | None:
    if count_users(db) > 0 or not username or not password:
        return None
    return create_user(
        db,
        username=username,
        password=password,
        display_name=username,
        role="admin",
    )


def user_has_admin_key(db: Session, user: User) -> bool:
    return any(
        "admin" in (key.scopes or [])
        for key in db.scalars(select(ApiKey).where(ApiKey.user_id == user.id))
        if not key.revoked_at
    )
