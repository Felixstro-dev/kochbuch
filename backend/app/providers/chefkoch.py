from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.core.fetch import FetchBlocked, FetchFailed, FetchPipeline
from app.core.http import AsyncIntervalLimiter
from app.providers.base import (
    Ingredient,
    IngredientGroup,
    ProviderError,
    ProviderSearchResult,
    ProviderUnavailable,
    RecipeDetail,
    RecipeNotFound,
    RecipeSummary,
    SearchQuery,
)
from app.providers.scraper import fallback_recipe_from_web, scrape_url
from app.providers.utils import (
    chefkoch_id_from_url,
    chefkoch_recipe_url,
    image_from_template,
    normalize_url,
    parse_float,
    parse_int,
    parse_servings,
    split_steps,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.chefkoch.de/v2"
SOURCE = "chefkoch"
LABEL = "Chefkoch"


class ChefkochProvider:
    name = SOURCE
    label = LABEL
    can_search = True

    def __init__(
        self,
        client: httpx.AsyncClient,
        settings: Settings,
        limiter: AsyncIntervalLimiter | None = None,
        fetcher: FetchPipeline | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.limiter = limiter or AsyncIntervalLimiter(settings.chefkoch_min_interval)
        self.fetcher = fetcher or FetchPipeline(settings, client)

    async def _get_json(
        self, path: str, params: dict[str, object] | None = None
    ) -> dict[str, Any]:
        url = f"{API_BASE}{path}"
        await self.limiter.wait()
        try:
            result = await self.fetcher.fetch(
                url, kind="json", params=params, allow_flare=False
            )
        except FetchBlocked as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except FetchFailed as exc:
            raise ProviderUnavailable(
                "Chefkoch ist momentan nicht erreichbar. Bitte später erneut versuchen."
            ) from exc
        if result.status == 404:
            raise RecipeNotFound("Dieses Chefkoch-Rezept existiert nicht mehr.")
        if result.status == 429:
            raise ProviderUnavailable(
                "Chefkoch bremst gerade (HTTP 429). Bitte kurz warten und erneut versuchen."
            )
        if result.status >= 500:
            raise ProviderUnavailable(
                f"Chefkoch antwortet momentan nicht (HTTP {result.status})."
            )
        if result.status >= 400:
            raise ProviderUnavailable(
                f"Chefkoch-Anfrage fehlgeschlagen (HTTP {result.status})."
            )
        try:
            return result.json()
        except ValueError as exc:
            raise ProviderUnavailable("Chefkoch lieferte keine gültige JSON-Antwort.") from exc

    @staticmethod
    def _summary_from_result(recipe: dict[str, Any]) -> RecipeSummary | None:
        recipe_id = str(recipe.get("id") or "")
        title = (recipe.get("title") or "").strip()
        if not recipe_id or not title:
            return None
        url = normalize_url(str(recipe.get("siteUrl") or "")) or chefkoch_recipe_url(recipe_id)
        rating_data = recipe.get("rating") or {}
        image_url = image_from_template(recipe.get("previewImageUrlTemplate"), "crop-480x360")
        return RecipeSummary(
            source=SOURCE,
            external_id=recipe_id,
            cache_key=f"{SOURCE}:{recipe_id}",
            title=title,
            subtitle=(recipe.get("subtitle") or "").strip(),
            image_source_url=image_url,
            rating=parse_float(rating_data.get("rating")),
            rating_count=parse_int(rating_data.get("numVotes")) or 0,
            prep_min=parse_int(recipe.get("preparationTime")),
            total_min=parse_int(recipe.get("totalTime"))
            or parse_int(recipe.get("preparationTime")),
            difficulty=parse_int(recipe.get("difficulty")),
            category="",
            canonical_url=url,
        )

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        params: dict[str, object] = {
            "query": query.text,
            "limit": min(max(query.limit, 1), 50),
            "offset": max(query.page - 1, 0) * query.limit,
        }
        payload = await self._get_json("/recipes", params=params)
        items: list[RecipeSummary] = []
        for entry in payload.get("results") or []:
            recipe = entry.get("recipe") if isinstance(entry, dict) else None
            if not isinstance(recipe, dict):
                continue
            summary = self._summary_from_result(recipe)
            if not summary:
                continue
            if query.difficulty and summary.difficulty != query.difficulty:
                continue
            if query.max_time and summary.total_min and summary.total_min > query.max_time:
                continue
            if query.category:
                haystack = f"{summary.title} {summary.subtitle}".lower()
                if query.category.lower() not in haystack:
                    continue
            items.append(summary)

        if query.sort == "rating":
            items.sort(key=lambda item: (item.rating or 0, item.rating_count), reverse=True)
        elif query.sort == "time":
            items.sort(key=lambda item: item.total_min or 9999)

        return ProviderSearchResult(
            items=items,
            total=parse_int(payload.get("count")) or len(items),
        )

    async def _detail_from_api(self, recipe_id: str) -> RecipeDetail:
        data = await self._get_json(f"/recipes/{recipe_id}")
        rating_data = data.get("rating") or {}
        canonical = normalize_url(str(data.get("siteUrl") or "")) or chefkoch_recipe_url(
            recipe_id
        )
        groups: list[IngredientGroup] = []
        for group in data.get("ingredientGroups") or []:
            if not isinstance(group, dict):
                continue
            items: list[Ingredient] = []
            for ingredient in group.get("ingredients") or []:
                if not isinstance(ingredient, dict):
                    continue
                items.append(
                    Ingredient(
                        name=(ingredient.get("name") or "").strip(),
                        amount=(
                            parse_float(ingredient.get("amount"))
                            if parse_float(ingredient.get("amount"))
                            else None
                        ),
                        unit=(ingredient.get("unit") or "").strip(),
                        note=(ingredient.get("usageInfo") or "").strip(),
                    )
                )
            if items:
                groups.append(
                    IngredientGroup(title=(group.get("header") or "").strip(), items=items)
                )

        categories = [
            str(item.get("title"))
            for item in data.get("categoryBreadcrumb") or []
            if isinstance(item, dict) and item.get("title")
        ]
        primary_category = next(
            (category for category in categories if category.lower() != "menüart"),
            categories[0] if categories else "",
        )
        tags: list[str] = []
        for tag in data.get("tags") or []:
            if isinstance(tag, str):
                tags.append(tag)
            elif isinstance(tag, dict) and tag.get("title"):
                tags.append(str(tag["title"]))
        nutrition_raw = data.get("nutrition") or {}
        nutrition = None
        if isinstance(nutrition_raw, dict) and nutrition_raw:
            nutrition = {
                "kcal": nutrition_raw.get("kCalories"),
                "protein": nutrition_raw.get("proteinContent"),
                "carbs": nutrition_raw.get("carbohydrateContent"),
                "fat": nutrition_raw.get("fatContent"),
            }
            nutrition = {key: value for key, value in nutrition.items() if value not in (None, "")}

        prep_min = parse_int(data.get("preparationTime"))
        cook_min = parse_int(data.get("cookingTime"))
        resting_min = parse_int(data.get("restingTime"))
        total_min = parse_int(data.get("totalTime"))
        if not total_min:
            total_min = sum(value or 0 for value in (prep_min, cook_min, resting_min)) or None

        image_url = image_from_template(data.get("previewImageUrlTemplate"), "crop-1200x675")
        description = (
            (data.get("additionalDescription") or "").strip()
            or (data.get("subtitle") or "").strip()
        )
        owner = data.get("owner") or {}

        return RecipeDetail(
            source=SOURCE,
            external_id=str(data.get("id") or recipe_id),
            cache_key=f"{SOURCE}:{data.get('id') or recipe_id}",
            title=(data.get("title") or "").strip(),
            subtitle=(data.get("subtitle") or "").strip(),
            description=description,
            image_source_url=image_url,
            rating=parse_float(rating_data.get("rating")),
            rating_count=parse_int(rating_data.get("numVotes")) or 0,
            prep_min=prep_min,
            cook_min=cook_min,
            total_min=total_min,
            difficulty=parse_int(data.get("difficulty")),
            category=primary_category,
            canonical_url=canonical,
            author=(owner.get("displayName") or "").strip(),
            base_servings=parse_servings(data.get("servings")),
            ingredient_groups=groups,
            steps=split_steps(data.get("instructions")),
            nutrition=nutrition,
            tags=tags,
            categories=categories,
            image_count=parse_int(data.get("imageCount")) or 0,
        )

    async def get_recipe(self, external_id: str) -> RecipeDetail:
        recipe_id = chefkoch_id_from_url(external_id) or external_id.strip()
        if not recipe_id.isdigit():
            raise RecipeNotFound("Ungültige Chefkoch-Rezept-ID.")
        try:
            return await self._detail_from_api(recipe_id)
        except RecipeNotFound:
            raise
        except ProviderError as exc:
            logger.warning("Chefkoch-API-Fehler für %s, versuche HTML-Fallback: %s", recipe_id, exc)
            try:
                detail = await scrape_url(
                    self.fetcher, chefkoch_recipe_url(recipe_id), self.settings
                )
            except ProviderError:
                raise exc from None
            if not detail.title:
                raise RecipeNotFound("Rezept nicht gefunden.") from None
            detail = fallback_recipe_from_web(detail, source=SOURCE, external_id=recipe_id)
            detail.image_source_url = detail.image_source_url or image_from_template(
                None, "crop-1200x675"
            )
            return detail
