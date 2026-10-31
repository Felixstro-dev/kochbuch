from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Kochbuch"
    environment: str = "development"
    log_level: str = "INFO"

    data_dir: Path = Path("./data")
    database_url: str | None = None
    auto_migrate: bool = True
    testing: bool = False

    # Auth
    secret_key: str = "dev-insecure-change-me"
    api_key_pepper: str | None = None
    session_cookie_name: str = "kochbuch_session"
    csrf_cookie_name: str = "kochbuch_csrf"
    session_ttl_days: int = 30
    cookie_secure: bool = False
    cookie_domain: str | None = None
    admin_username: str | None = None
    admin_password: str | None = None
    login_rate_limit: int = 5
    login_rate_window: int = 60

    # Proxy / integrations
    cors_origins: str = ""
    frame_ancestors: str = "'self'"
    embed_public: bool = False

    # Providers / caching
    enabled_providers: str = "chefkoch,web,local"
    http_user_agent: str = (
        "Kochbuch/0.1 (self-hosted recipe manager; "
        "+https://github.com/kochbuch-app/kochbuch)"
    )
    provider_timeout_seconds: float = 10.0
    chefkoch_min_interval: float = 1.0

    # Fetch pipeline (escalating HTTP client)
    fetch_proxy_url: str = ""
    fetch_proxy_for_images: bool = True
    flaresolverr_url: str = ""
    flaresolverr_timeout: int = 60
    fetch_max_retries: int = 3
    fetch_timeout: float = 15.0
    fetch_min_interval: float = 0.4
    fetch_circuit_threshold: int = 4
    fetch_circuit_cooldown: float = 60.0
    fetch_browser_impersonation: bool = True
    search_cache_seconds: int = 600
    recipe_stale_days: int = 7
    image_max_bytes: int = 20 * 1024 * 1024
    allow_private_urls: bool = False

    # Feature defaults (overridable via settings table later)
    default_theme: str = "dark"
    accent_color: str = "#e6a15c"

    frontend_dir: Path | None = Field(default=None)

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{self.data_dir / 'kochbuch.db'}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def enabled_provider_list(self) -> list[str]:
        return [
            provider.strip().lower()
            for provider in self.enabled_providers.split(",")
            if provider.strip()
        ]

    @property
    def token_pepper(self) -> str:
        return self.api_key_pepper or self.secret_key

    @property
    def data_path(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()
