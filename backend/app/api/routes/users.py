from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_admin
from app.core.security import hash_password, validate_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import UserOut
from app.schemas.users import UserCreate, UserList, UserUpdate
from app.services import auth as auth_service

router = APIRouter(prefix="/users", tags=["users"])


def _active_admin_count(db: Session, exclude_id: str | None = None) -> int:
    stmt = select(func.count()).select_from(User).where(
        User.role == "admin", User.is_active.is_(True)
    )
    if exclude_id:
        stmt = stmt.where(User.id != exclude_id)
    return int(db.scalar(stmt) or 0)


def _get_user(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden.")
    return user


@router.get("", response_model=UserList)
def list_users(
    _: Principal = Depends(require_admin), db: Session = Depends(get_db)
) -> UserList:
    users = list(db.scalars(select(User).order_by(User.created_at)))
    return UserList(items=[UserOut.model_validate(user) for user in users])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    try:
        user = auth_service.create_user(
            db,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            role=payload.role,
        )
    except auth_service.ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    auth_service.record_audit(
        db,
        action="user.created",
        user_id=principal.user.id if principal.user else None,
        request=request,
        detail={"target": user.id, "username": user.username},
    )
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = _get_user(db, user_id)
    is_self = principal.user is not None and principal.user.id == user.id

    if payload.is_active is False and is_self:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das eigene Konto kann nicht deaktiviert werden.",
        )
    loses_admin = user.role == "admin" and user.is_active and (
        (payload.role is not None and payload.role != "admin") or payload.is_active is False
    )
    if loses_admin and _active_admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der letzte aktive Administrator kann nicht herabgestuft oder deaktiviert werden.",
        )

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or user.username
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        problem = validate_password(payload.password)
        if problem:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)
        user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    auth_service.record_audit(
        db,
        action="user.updated",
        user_id=principal.user.id if principal.user else None,
        request=request,
        detail={"target": user.id},
    )
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: str,
    request: Request,
    principal: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    user = _get_user(db, user_id)
    if principal.user and principal.user.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das eigene Konto kann nicht deaktiviert werden.",
        )
    if user.role == "admin" and user.is_active and _active_admin_count(db, exclude_id=user.id) == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der letzte aktive Administrator kann nicht deaktiviert werden.",
        )
    user.is_active = False
    db.commit()
    auth_service.record_audit(
        db,
        action="user.deactivated",
        user_id=principal.user.id if principal.user else None,
        request=request,
        detail={"target": user.id},
    )
