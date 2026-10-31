from __future__ import annotations

from app.core.config import Settings
from app.core.fetch import FetchPipeline
from app.providers.base import ProviderSearchResult, RecipeDetail, SearchQuery
from app.providers.scraper import scrape_url


class WebProvider:
    name = "web"
    label = "Web"
    can_search = True

    def __init__(
        self,
        fetcher: FetchPipeline,
        settings: Settings,
        client: object | None = None,
    ) -> None:
        self.fetcher = fetcher
        self.settings = settings

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        return ProviderSearchResult(items=[], total=0)

    async def get_recipe(self, external_id: str) -> RecipeDetail:
        return await scrape_url(self.fetcher, external_id, self.settings)
