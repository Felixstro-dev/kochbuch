from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.fetch import FetchPipeline
from app.db.models import Setting
from app.schemas.settings import FetchConfigUpdate

FETCH_KEYS: tuple[str, ...] = (
    "fetch_proxy_url",
    "fetch_proxy_for_images",
    "flaresolverr_url",
    "flaresolverr_timeout",
    "fetch_max_retries",
    "fetch_timeout",
    "fetch_browser_impersonation",
)

_FIELD_TO_KEY = {
    "proxy_url": "fetch_proxy_url",
    "proxy_for_images": "fetch_proxy_for_images",
    "flaresolverr_url": "flaresolverr_url",
    "flaresolverr_timeout": "flaresolverr_timeout",
    "max_retries": "fetch_max_retries",
    "timeout": "fetch_timeout",
    "browser_impersonation": "fetch_browser_impersonation",
}


def fetch_values(db: Session) -> dict[str, object]:
    """Return only the fetch-related rows so env defaults stay untouched."""

    rows = db.query(Setting).filter(Setting.key.in_(FETCH_KEYS)).all()
    return {row.key: row.value for row in rows}


def apply_fetch_settings(
    db: Session, payload: FetchConfigUpdate, pipeline: FetchPipeline
) -> None:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        key = _FIELD_TO_KEY.get(field)
        if key is None:
            continue
        if key in {"fetch_proxy_url", "flaresolverr_url"}:
            value = (value or "").strip()
        setting = db.get(Setting, key)
        if setting:
            setting.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
    pipeline.apply_values(fetch_values(db))
