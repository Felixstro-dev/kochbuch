from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings
from app.db.base import Base, make_engine, make_session_factory
from app.db.models import Recipe
from app.providers.base import (
    Ingredient,
    IngredientGroup,
    ProviderSearchResult,
    RecipeDetail,
    RecipeSummary,
    SearchQuery,
)
from app.providers.utils import split_steps
from app.services.recipe_store import apply_detail, summary_from_row
from app.services.search import SearchService


class FakeProvider:
    name = "fake"
    label = "Fake"
    can_search = True

    def __init__(self) -> None:
        self.calls = 0
        self.detail_calls = 0

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        self.calls += 1
        return ProviderSearchResult(
            items=[
                RecipeSummary(
                    source="fake",
                    external_id="1",
                    cache_key="fake:1",
                    title="Apfelkuchen",
                    rating=4.0,
                    total_min=60,
                    canonical_url="https://example.com/1",
                ),
                RecipeSummary(
                    source="fake",
                    external_id="2",
                    cache_key="fake:2",
                    title="Brot",
                    rating=4.8,
                    total_min=120,
                    canonical_url="https://example.com/2",
                ),
            ],
            total=2,
        )

    async def get_recipe(self, external_id: str) -> RecipeDetail:
        self.detail_calls += 1
        return RecipeDetail(
            source="fake",
            external_id=external_id,
            cache_key=f"fake:{external_id}",
            title="Apfelkuchen",
            canonical_url="https://example.com/1",
            base_servings=4,
            ingredient_groups=[
                IngredientGroup(title="", items=[Ingredient(name="Mehl", amount=200, unit="g")])
            ],
            steps=split_steps("Teig machen. 30 Min. backen."),
        )


class FakeRegistry:
    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider
        self.providers = {"fake": provider}

    def searchable(self, enabled=None):
        return [self.provider]

    def get(self, name):
        return self.provider if name == "fake" else None


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'cache.db'}",
        testing=True,
        auto_migrate=False,
        search_cache_seconds=600,
    )


def test_search_cache_favorites_boost_and_sort(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    engine = make_engine(settings.resolved_database_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    provider = FakeProvider()
    service = SearchService(FakeRegistry(provider), session_factory, settings)

    async def run() -> None:
        with session_factory() as db:
            first = await service.search(db, SearchQuery(text="kuchen"))
            assert first.cached is False
            assert [item.title for item in first.items] == ["Apfelkuchen", "Brot"]
            second = await service.search(db, SearchQuery(text="kuchen"))
            assert second.cached is True
            assert provider.calls == 1

            row = db.scalar(select(Recipe).where(Recipe.cache_key == "fake:2"))
            row.is_favorite = True
            db.commit()
            boosted = await service.search(db, SearchQuery(text="kuchen"))
            assert boosted.items[0].cache_key == "fake:2"
            assert boosted.items[0].is_favorite is True

            by_rating = await service.search(db, SearchQuery(text="kuchen", sort="rating"))
            assert by_rating.items[0].cache_key == "fake:2"

    asyncio.run(run())
    engine.dispose()


def test_recipe_detail_is_cached(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    engine = make_engine(settings.resolved_database_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    provider = FakeProvider()
    from app.services.recipes import RecipeService

    service = RecipeService(FakeRegistry(provider), session_factory, settings)
    with session_factory() as db:
        row = Recipe(
            cache_key="fake:1",
            source="fake",
            external_id="1",
            title="Apfelkuchen",
        )
        apply_detail(
            row,
            asyncio.run(provider.get_recipe("1")),
            stale_day_offset=settings.recipe_stale_days,
        )
        db.add(row)
        db.commit()

        async def run() -> None:
            result = await service.get(db, "fake:1")
            assert result.detail.title == "Apfelkuchen"
            assert result.detail.base_servings == 4
            again = await service.get(db, "fake:1")
            assert again.detail.cache_key == "fake:1"

        asyncio.run(run())
        assert provider.detail_calls == 1
        row = db.scalar(select(Recipe).where(Recipe.cache_key == "fake:1"))
        assert row.access_count == 2
        assert summary_from_row(row).title == "Apfelkuchen"

    engine.dispose()
