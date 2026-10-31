from __future__ import annotations

import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, get_principal, require_admin
from app.db.session import get_db
from app.schemas.settings import AppSettingsOut, AppSettingsUpdate
from app.services import settings as settings_service
from app.services.fetch_settings import apply_fetch_settings

router = APIRouter(prefix="/settings", tags=["settings"])

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_KNOWN_PROVIDERS = {"chefkoch", "web", "local"}
_PROXY_SCHEMES = {"http", "https", "socks4", "socks5", "socks5h"}
_WEB_SCHEMES = {"http", "https"}


def _validate_url(value: str, schemes: set[str], label: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme.lower() not in schemes or not parts.hostname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{label} muss eine gültige URL sein ({', '.join(sorted(schemes))}).",
        )
    return value


@router.get("", response_model=AppSettingsOut)
def get_settings(
    request: Request,
    _: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> AppSettingsOut:
    env = request.app.state.settings
    pipeline = request.app.state.fetch_pipeline
    enabled = settings_service.get_enabled_providers(db, env.enabled_provider_list)
    return settings_service.as_out(
        db,
        embed_public=env.embed_public,
        enabled_providers=enabled,
        pipeline=pipeline,
    )


@router.patch("", response_model=AppSettingsOut)
def update_settings(
    payload: AppSettingsUpdate,
    request: Request,
    _: Principal = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AppSettingsOut:
    if payload.accent_color is not None and not _HEX_COLOR.match(payload.accent_color):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Die Akzentfarbe muss ein Hex-Wert wie #e6a15c sein.",
        )
    if payload.default_theme is not None and payload.default_theme not in {
        "dark",
        "light",
        "system",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Theme muss dark, light oder system sein.",
        )
    if payload.app_name is not None:
        name = payload.app_name.strip()
        if not 1 <= len(name) <= 60:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Der App-Name muss 1 bis 60 Zeichen lang sein.",
            )
        payload.app_name = name
    if payload.enabled_providers is not None:
        cleaned = list(dict.fromkeys(name.lower() for name in payload.enabled_providers))
        unknown = set(cleaned) - _KNOWN_PROVIDERS
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unbekannte Quellen: {', '.join(sorted(unknown))}.",
            )
        if not cleaned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mindestens eine Quelle muss aktiv bleiben.",
            )
        payload.enabled_providers = cleaned

    if payload.fetch is not None:
        if payload.fetch.proxy_url is not None:
            payload.fetch.proxy_url = _validate_url(
                payload.fetch.proxy_url, _PROXY_SCHEMES, "Die Proxy-URL"
            )
        if payload.fetch.flaresolverr_url is not None:
            payload.fetch.flaresolverr_url = _validate_url(
                payload.fetch.flaresolverr_url, _WEB_SCHEMES, "Die FlareSolverr-URL"
            )

    env = request.app.state.settings
    pipeline = request.app.state.fetch_pipeline
    settings_service.update_values(db, payload)
    if payload.fetch is not None:
        apply_fetch_settings(db, payload.fetch, pipeline)
    enabled = settings_service.get_enabled_providers(db, env.enabled_provider_list)
    return settings_service.as_out(
        db,
        embed_public=env.embed_public,
        enabled_providers=enabled,
        pipeline=pipeline,
    )
