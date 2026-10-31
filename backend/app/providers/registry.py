from __future__ import annotations

import logging

import httpx

from app.core.config import Settings
from app.core.fetch import FetchPipeline
from app.core.http import AsyncIntervalLimiter, make_http_client
from app.providers.base import RecipeProvider
from app.providers.chefkoch import ChefkochProvider
from app.providers.local import LocalProvider
from app.providers.web import WebProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self, settings: Settings, session_factory) -> None:
        self.settings = settings
        self.client: httpx.AsyncClient = make_http_client(settings)
        self.fetcher = FetchPipeline(settings, self.client)
        chefkoch_limiter = AsyncIntervalLimiter(settings.chefkoch_min_interval)
        self.providers: dict[str, RecipeProvider] = {
            "chefkoch": ChefkochProvider(
                self.client, settings, chefkoch_limiter, fetcher=self.fetcher
            ),
            "web": WebProvider(self.fetcher, settings),
            "local": LocalProvider(session_factory),
        }

    def active(self, enabled: list[str] | None = None) -> list[RecipeProvider]:
        names = enabled if enabled is not None else self.settings.enabled_provider_list
        return [
            self.providers[name]
            for name in names
            if name in self.providers
        ]

    def get(self, name: str) -> RecipeProvider | None:
        return self.providers.get(name)

    def searchable(self, enabled: list[str] | None = None) -> list[RecipeProvider]:
        return [provider for provider in self.active(enabled) if provider.can_search]

    async def close(self) -> None:
        await self.fetcher.close()
        await self.client.aclose()
