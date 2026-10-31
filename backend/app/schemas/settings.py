from __future__ import annotations

from pydantic import BaseModel, Field


class FetchConfigOut(BaseModel):
    proxy_configured: bool
    proxy_host: str | None = None
    proxy_for_images: bool
    flaresolverr_configured: bool
    flaresolverr_url: str | None = None
    flaresolverr_timeout: int
    max_retries: int
    timeout: float
    browser_impersonation: bool
    curl_cffi: bool


class FetchConfigUpdate(BaseModel):
    proxy_url: str | None = None
    proxy_for_images: bool | None = None
    flaresolverr_url: str | None = None
    flaresolverr_timeout: int | None = Field(default=None, ge=5, le=300)
    max_retries: int | None = Field(default=None, ge=1, le=8)
    timeout: float | None = Field(default=None, ge=3, le=120)
    browser_impersonation: bool | None = None


class AppSettingsOut(BaseModel):
    app_name: str
    default_theme: str
    accent_color: str
    embed_public: bool
    enabled_providers: list[str]
    fetch: FetchConfigOut


class AppSettingsUpdate(BaseModel):
    app_name: str | None = None
    default_theme: str | None = None
    accent_color: str | None = None
    enabled_providers: list[str] | None = None
    fetch: FetchConfigUpdate | None = None


class FetchTestRequest(BaseModel):
    target: str = Field(pattern="^(direct|proxy|flaresolverr)$")
    url: str | None = Field(default=None, max_length=2000)


class FetchTestOut(BaseModel):
    ok: bool
    target: str
    detail: str
    status: int | None = None
    tier: str | None = None
    elapsed_ms: int | None = None


class FetchDomainOut(BaseModel):
    domain: str
    successes: int
    failures: int
    last_tier: str | None
    last_success_at: str | None
    circuit_open_until: str | None
    rate_limited: bool


class FetchActiveOut(BaseModel):
    domain: str
    stage: str
    label: str
    tier: str
    attempt: int
    started_at: str | None


class FetchStatusOut(BaseModel):
    proxy_configured: bool
    proxy_host: str | None
    proxy_for_images: bool
    flaresolverr_configured: bool
    flaresolverr_url: str | None
    flaresolverr_timeout: int
    max_retries: int
    timeout: float
    min_interval: float
    browser_impersonation: bool
    curl_cffi: bool
    totals: dict[str, object]
    active: list[FetchActiveOut]
    domains: list[FetchDomainOut]
