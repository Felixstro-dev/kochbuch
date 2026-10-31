from __future__ import annotations

from dataclasses import dataclass, field


class ProviderError(Exception):
    """Base error for recipe providers. Messages are safe for API responses."""


class RecipeNotFound(ProviderError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class InvalidRecipeURL(ProviderError):
    pass


@dataclass(slots=True)
class SearchQuery:
    text: str
    page: int = 1
    limit: int = 24
    max_time: int | None = None
    difficulty: int | None = None
    category: str | None = None
    sort: str = "relevance"


@dataclass(slots=True)
class Ingredient:
    name: str
    amount: float | None = None
    unit: str = ""
    note: str = ""


@dataclass(slots=True)
class IngredientGroup:
    title: str
    items: list[Ingredient] = field(default_factory=list)


@dataclass(slots=True)
class Step:
    text: str
    timer_seconds: int | None = None


@dataclass(slots=True)
class RecipeSummary:
    source: str
    external_id: str
    cache_key: str
    title: str
    subtitle: str = ""
    image_source_url: str | None = None
    rating: float | None = None
    rating_count: int = 0
    prep_min: int | None = None
    total_min: int | None = None
    difficulty: int | None = None
    category: str = ""
    canonical_url: str = ""
    is_favorite: bool = False
    is_saved: bool = False
    image_blurhash: str | None = None


@dataclass(slots=True)
class RecipeDetail(RecipeSummary):
    description: str = ""
    author: str = ""
    cook_min: int | None = None
    base_servings: int | None = None
    ingredient_groups: list[IngredientGroup] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    nutrition: dict[str, object] | None = None
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    image_count: int = 0


@dataclass(slots=True)
class ProviderSearchResult:
    items: list[RecipeSummary] = field(default_factory=list)
    total: int = 0


class RecipeProvider:
    name: str = "base"
    label: str = "Basis"
    can_search: bool = False

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        return ProviderSearchResult()

    async def get_recipe(self, external_id: str) -> RecipeDetail:
        raise RecipeNotFound("Rezept nicht gefunden.")
