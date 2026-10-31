from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request):
    session: Session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
