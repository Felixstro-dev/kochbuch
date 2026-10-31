from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IngredientOut(BaseModel):
    name: str
    amount: float | None = None
    unit: str = ""
    note: str = ""


class IngredientGroupOut(BaseModel):
    title: str
    items: list[IngredientOut]


class StepOut(BaseModel):
    text: str
    timer_seconds: int | None = None


class RecipeSummaryOut(BaseModel):
    cache_key: str
    source: str
    source_label: str
    title: str
    subtitle: str = ""
    image_url: str | None = None
    image_blurhash: str | None = None
    rating: float | None = None
    rating_count: int = 0
    prep_min: int | None = None
    total_min: int | None = None
    difficulty: int | None = None
    category: str = ""
    url: str = ""
    is_favorite: bool = False
    is_saved: bool = False
    stale: bool = False


class RecipeDetailOut(RecipeSummaryOut):
    description: str = ""
    author: str = ""
    cook_min: int | None = None
    base_servings: int | None = None
    ingredient_groups: list[IngredientGroupOut] = Field(default_factory=list)
    steps: list[StepOut] = Field(default_factory=list)
    nutrition: dict | None = None
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    image_count: int = 0
    fetched_at: str | None = None


class SearchResponse(BaseModel):
    items: list[RecipeSummaryOut]
    total: int
    page: int
    limit: int
    providers: list[str]
    cached: bool = False
    stale: bool = False
    errors: list[str] = Field(default_factory=list)
    took_ms: int = 0


class RecipePatch(BaseModel):
    is_favorite: bool | None = None
    is_saved: bool | None = None
    tags: list[str] | None = Field(default=None, max_length=50)


class ResolveRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2000)


class ProviderOut(BaseModel):
    name: str
    label: str
    can_search: bool
    enabled: bool


class RecipeListResponse(BaseModel):
    items: list[RecipeSummaryOut]
    total: int


class ImageVariant(BaseModel):
    name: Literal["thumb", "card", "hero"]
    width: int
    height: int
