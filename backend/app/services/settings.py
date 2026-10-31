from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.fetch import FetchPipeline, _redact_proxy
from app.db.models import Setting
from app.schemas.settings import AppSettingsOut, AppSettingsUpdate, FetchConfigOut
from app.services.fetch_settings import FETCH_KEYS, apply_fetch_settings, fetch_values

DEFAULTS: dict[str, object] = {
    "app_name": "Kochbuch",
    "default_theme": "dark",
    "accent_color": "#e6a15c",
}


def get_values(db: Session) -> dict[str, object]:
    values = dict(DEFAULTS)
    for setting in db.query(Setting).all():
        values[setting.key] = setting.value
    return values


def get_enabled_providers(db: Session, fallback: list[str]) -> list[str]:
    values = get_values(db)
    configured = values.get("enabled_providers")
    if isinstance(configured, list) and configured:
        return [str(name) for name in configured]
    return fallback


def update_values(db: Session, payload: AppSettingsUpdate) -> dict[str, object]:
    updates = payload.model_dump(
        exclude_unset=True, exclude_none=True, exclude={"fetch"}
    )
    for key, value in updates.items():
        setting = db.get(Setting, key)
        if setting:
            setting.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
    return get_values(db)


def fetch_out(pipeline: FetchPipeline) -> FetchConfigOut:
    config = pipeline.config
    capabilities = pipeline.status()["capabilities"]
    return FetchConfigOut(
        proxy_configured=bool(config.proxy_url),
        proxy_host=_redact_proxy(config.proxy_url),
        proxy_for_images=config.proxy_for_images,
        flaresolverr_configured=bool(config.flaresolverr_url),
        flaresolverr_url=config.flaresolverr_url,
        flaresolverr_timeout=config.flaresolverr_timeout,
        max_retries=config.max_retries,
        timeout=config.timeout,
        browser_impersonation=config.use_browser_impersonation,
        curl_cffi=bool(capabilities.get("curl_cffi")),
    )


def as_out(
    db: Session,
    *,
    embed_public: bool,
    enabled_providers: list[str],
    pipeline: FetchPipeline,
) -> AppSettingsOut:
    values = get_values(db)
    return AppSettingsOut(
        app_name=str(values["app_name"]),
        default_theme=str(values["default_theme"]),
        accent_color=str(values["accent_color"]),
        embed_public=embed_public,
        enabled_providers=enabled_providers,
        fetch=fetch_out(pipeline),
    )


__all__ = [
    "DEFAULTS",
    "FETCH_KEYS",
    "apply_fetch_settings",
    "as_out",
    "fetch_out",
    "fetch_values",
    "get_enabled_providers",
    "get_values",
    "update_values",
]
