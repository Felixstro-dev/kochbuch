from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from app.db.base import utcnow
from app.db.models import Recipe
from app.providers.base import (
    Ingredient,
    IngredientGroup,
    RecipeDetail,
    RecipeSummary,
    Step,
)
from app.providers.utils import source_label


def groups_to_json(groups: list[IngredientGroup]) -> list[dict[str, Any]]:
    return [asdict(group) for group in groups]


def groups_from_json(value: object) -> list[IngredientGroup]:
    groups: list[IngredientGroup] = []
    if not isinstance(value, list):
        return groups
    for raw_group in value:
        if not isinstance(raw_group, dict):
            continue
        items = [
            Ingredient(
                name=str(item.get("name") or ""),
                amount=item.get("amount"),
                unit=str(item.get("unit") or ""),
                note=str(item.get("note") or ""),
            )
            for item in raw_group.get("items") or []
            if isinstance(item, dict)
        ]
        groups.append(IngredientGroup(title=str(raw_group.get("title") or ""), items=items))
    return groups


def steps_to_json(steps: list[Step]) -> list[dict[str, Any]]:
    return [asdict(step) for step in steps]


def steps_from_json(value: object) -> list[Step]:
    steps: list[Step] = []
    if not isinstance(value, list):
        return steps
    for raw in value:
        if isinstance(raw, dict) and raw.get("text"):
            steps.append(
                Step(
                    text=str(raw["text"]),
                    timer_seconds=raw.get("timer_seconds"),
                )
            )
    return steps


def summary_to_dict(summary: RecipeSummary) -> dict[str, Any]:
    return asdict(summary)


def summary_from_dict(data: dict[str, Any]) -> RecipeSummary:
    allowed = {
        "source",
        "external_id",
        "cache_key",
        "title",
        "subtitle",
        "image_source_url",
        "rating",
        "rating_count",
        "prep_min",
        "total_min",
        "difficulty",
        "category",
        "canonical_url",
        "is_favorite",
        "is_saved",
        "image_blurhash",
    }
    return RecipeSummary(**{key: value for key, value in data.items() if key in allowed})


def summary_from_row(row: Recipe) -> RecipeSummary:
    return RecipeSummary(
        source=row.source,
        external_id=row.external_id,
        cache_key=row.cache_key,
        title=row.title,
        subtitle=row.subtitle,
        image_source_url=row.image_source_url,
        rating=row.rating,
        rating_count=row.rating_count,
        prep_min=row.prep_min,
        total_min=row.total_min,
        difficulty=row.difficulty,
        category=(row.categories[0] if row.categories else ""),
        canonical_url=row.canonical_url,
        is_favorite=row.is_favorite,
        is_saved=row.is_saved,
        image_blurhash=row.image_blurhash,
    )


def detail_from_row(row: Recipe) -> RecipeDetail:
    return RecipeDetail(
        source=row.source,
        external_id=row.external_id,
        cache_key=row.cache_key,
        title=row.title,
        subtitle=row.subtitle,
        image_source_url=row.image_source_url,
        rating=row.rating,
        rating_count=row.rating_count,
        prep_min=row.prep_min,
        total_min=row.total_min,
        difficulty=row.difficulty,
        category=(row.categories[0] if row.categories else ""),
        canonical_url=row.canonical_url,
        is_favorite=row.is_favorite,
        is_saved=row.is_saved,
        image_blurhash=row.image_blurhash,
        description=row.description,
        author=row.author,
        cook_min=row.cook_min,
        base_servings=row.base_servings,
        ingredient_groups=groups_from_json(row.ingredients),
        steps=steps_from_json(row.steps),
        nutrition=row.nutrition,
        tags=list(row.tags or []),
        categories=list(row.categories or []),
        image_count=row.image_count,
    )


def apply_summary(row: Recipe, summary: RecipeSummary, *, stale_day_offset: int) -> None:
    """Fill a cache row from a search hit without degrading an existing detail."""
    row.cache_key = summary.cache_key
    row.source = summary.source
    row.external_id = summary.external_id
    row.canonical_url = summary.canonical_url or row.canonical_url
    row.title = summary.title
    row.subtitle = summary.subtitle or row.subtitle
    row.image_source_url = summary.image_source_url or row.image_source_url
    row.rating = summary.rating if summary.rating is not None else row.rating
    row.rating_count = summary.rating_count or row.rating_count
    row.prep_min = summary.prep_min if summary.prep_min is not None else row.prep_min
    row.total_min = summary.total_min if summary.total_min is not None else row.total_min
    row.difficulty = summary.difficulty if summary.difficulty is not None else row.difficulty
    if not row.has_detail:
        row.fetched_at = utcnow()
        row.stale_at = utcnow() + timedelta(days=stale_day_offset)
    row.updated_at = utcnow()


def apply_detail(row: Recipe, detail: RecipeDetail, *, stale_day_offset: int) -> None:
    row.cache_key = detail.cache_key
    row.source = detail.source
    row.external_id = detail.external_id
    row.canonical_url = detail.canonical_url
    row.title = detail.title
    row.subtitle = detail.subtitle
    row.description = detail.description
    row.image_source_url = detail.image_source_url or row.image_source_url
    row.author = detail.author
    row.rating = detail.rating
    row.rating_count = detail.rating_count
    row.prep_min = detail.prep_min
    row.cook_min = detail.cook_min
    row.total_min = detail.total_min
    row.difficulty = detail.difficulty
    row.base_servings = detail.base_servings
    row.ingredients = groups_to_json(detail.ingredient_groups)
    row.steps = steps_to_json(detail.steps)
    row.nutrition = detail.nutrition
    row.tags = detail.tags
    row.categories = detail.categories
    row.image_count = detail.image_count
    row.has_detail = True
    row.fetched_at = utcnow()
    row.stale_at = utcnow() + timedelta(days=stale_day_offset)
    row.updated_at = utcnow()


def label_for(source: str) -> str:
    return source_label(source)
