from __future__ import annotations

from app.providers.base import RecipeDetail, RecipeSummary
from app.providers.utils import source_label
from app.schemas.recipes import (
    IngredientGroupOut,
    IngredientOut,
    RecipeDetailOut,
    RecipeSummaryOut,
    StepOut,
)
from app.services.images import ImageService


def summary_out(
    item: RecipeSummary,
    images: ImageService,
    *,
    blurhash: str | None = None,
    stale: bool = False,
) -> RecipeSummaryOut:
    image_url = (
        images.sign_url(item.cache_key, "card") if item.image_source_url else None
    )
    return RecipeSummaryOut(
        cache_key=item.cache_key,
        source=item.source,
        source_label=source_label(item.source),
        title=item.title,
        subtitle=item.subtitle,
        image_url=image_url,
        image_blurhash=blurhash or item.image_blurhash,
        rating=item.rating,
        rating_count=item.rating_count,
        prep_min=item.prep_min,
        total_min=item.total_min,
        difficulty=item.difficulty,
        category=item.category,
        url=item.canonical_url,
        is_favorite=item.is_favorite,
        is_saved=item.is_saved,
        stale=stale,
    )


def detail_out(
    item: RecipeDetail,
    images: ImageService,
    *,
    blurhash: str | None = None,
    fetched_at: str | None = None,
    stale: bool = False,
) -> RecipeDetailOut:
    base = summary_out(item, images, blurhash=blurhash, stale=stale)
    return RecipeDetailOut(
        **base.model_dump(),
        description=item.description,
        author=item.author,
        cook_min=item.cook_min,
        base_servings=item.base_servings,
        ingredient_groups=[
            IngredientGroupOut(
                title=group.title,
                items=[
                    IngredientOut(
                        name=ingredient.name,
                        amount=ingredient.amount,
                        unit=ingredient.unit,
                        note=ingredient.note,
                    )
                    for ingredient in group.items
                ],
            )
            for group in item.ingredient_groups
        ],
        steps=[
            StepOut(text=step.text, timer_seconds=step.timer_seconds)
            for step in item.steps
        ],
        nutrition=item.nutrition,
        tags=item.tags,
        categories=item.categories,
        image_count=item.image_count,
        fetched_at=fetched_at,
    )
