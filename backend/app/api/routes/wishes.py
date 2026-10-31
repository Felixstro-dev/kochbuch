from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, require_contributor
from app.db.base import utcnow
from app.db.models import Wish
from app.db.session import get_db
from app.schemas.wishes import WishCreate, WishOut, WishUpdate

router = APIRouter(prefix="/wishes", tags=["wishes"])


def _iso(value) -> str | None:
    return value.isoformat() + "Z" if value else None


def _out(wish: Wish) -> WishOut:
    return WishOut(
        id=wish.id,
        text=wish.text,
        note=wish.note,
        status=wish.status,
        created_by=wish.created_by,
        created_at=_iso(wish.created_at) or "",
        updated_at=_iso(wish.updated_at) or "",
        done_at=_iso(wish.done_at),
    )


@router.get("", response_model=list[WishOut])
def list_wishes(
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|done|all)$"),
    limit: int = Query(default=200, ge=1, le=500),
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[WishOut]:
    stmt = select(Wish)
    if status_filter in {"open", "done"}:
        stmt = stmt.where(Wish.status == status_filter)
    stmt = stmt.order_by(Wish.status.desc(), Wish.created_at.desc()).limit(limit)
    return [_out(wish) for wish in db.scalars(stmt).all()]


@router.post("", response_model=WishOut, status_code=status.HTTP_201_CREATED)
def create_wish(
    payload: WishCreate,
    _: Principal = Depends(require_contributor),
    db: Session = Depends(get_db),
) -> WishOut:
    text = payload.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Wunsch darf nicht leer sein.",
        )
    wish = Wish(text=text, note=payload.note.strip())
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return _out(wish)


@router.patch("/{wish_id}", response_model=WishOut)
def update_wish(
    wish_id: str,
    payload: WishUpdate,
    _: Principal = Depends(require_contributor),
    db: Session = Depends(get_db),
) -> WishOut:
    wish = db.get(Wish, wish_id)
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wunsch nicht gefunden.")
    if payload.text is not None:
        text = payload.text.strip()
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Der Wunsch darf nicht leer sein.",
            )
        wish.text = text
    if payload.note is not None:
        wish.note = payload.note.strip()
    if payload.status is not None:
        wish.status = payload.status
        wish.done_at = utcnow() if payload.status == "done" else None
    db.commit()
    db.refresh(wish)
    return _out(wish)


@router.delete("/{wish_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wish(
    wish_id: str,
    _: Principal = Depends(require_contributor),
    db: Session = Depends(get_db),
) -> None:
    wish = db.get(Wish, wish_id)
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wunsch nicht gefunden.")
    db.delete(wish)
    db.commit()
