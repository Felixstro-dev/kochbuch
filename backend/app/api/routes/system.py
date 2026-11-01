from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import Principal, require_admin
from app.schemas.settings import (
    FetchActiveOut,
    FetchDomainOut,
    FetchStatusOut,
    FetchTestOut,
    FetchTestRequest,
)

router = APIRouter(prefix="/system", tags=["system"])


def _checker(request: Request):
    checker = getattr(request.app.state, "update_checker", None)
    if checker is None:
        # Testing/Deaktiviert: Endpunkt antwortet trotzdem mit „aus".
        from app.services.update_check import UpdateChecker

        checker = UpdateChecker(image="", git_sha="unknown", interval_seconds=3600)
    return checker


@router.get("/update-status")
def update_status(
    request: Request,
    _: Principal = Depends(require_admin),
) -> dict[str, object]:
    settings = request.app.state.settings
    return _checker(request).state(dokploy_url=settings.dokploy_url)


@router.post("/update-check")
async def trigger_update_check(
    request: Request,
    _: Principal = Depends(require_admin),
) -> dict[str, object]:
    settings = request.app.state.settings
    return await _checker(request).check() | {"dokploy_url": settings.dokploy_url}


@router.get("/fetch-status", response_model=FetchStatusOut)
def fetch_status(
    request: Request,
    _: Principal = Depends(require_admin),
) -> FetchStatusOut:
    data = request.app.state.fetch_pipeline.status()
    config = data["config"]
    capabilities = data["capabilities"]
    return FetchStatusOut(
        proxy_configured=config["proxy_configured"],
        proxy_host=config["proxy_host"],
        proxy_for_images=config["proxy_for_images"],
        flaresolverr_configured=config["flaresolverr_configured"],
        flaresolverr_url=config["flaresolverr_url"],
        flaresolverr_timeout=config["flaresolverr_timeout"],
        max_retries=config["max_retries"],
        timeout=config["timeout"],
        min_interval=config["min_interval"],
        browser_impersonation=config["browser_impersonation"],
        curl_cffi=capabilities["curl_cffi"],
        totals=data["totals"],
        active=[FetchActiveOut(**item) for item in data["active"]],
        domains=[FetchDomainOut(**item) for item in data["domains"]],
    )


@router.post("/fetch/test", response_model=FetchTestOut)
async def test_fetch(
    payload: FetchTestRequest,
    request: Request,
    _: Principal = Depends(require_admin),
) -> FetchTestOut:
    url = payload.url.strip() if payload.url else None
    if url:
        from urllib.parse import urlsplit

        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Test-URLs müssen mit http:// oder https:// beginnen.",
            )
    result = await request.app.state.fetch_pipeline.test_connection(payload.target, url)
    return FetchTestOut(**result)
