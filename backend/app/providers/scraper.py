from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html

from app.core.config import Settings
from app.core.fetch import FetchBlocked, FetchFailed, FetchPipeline
from app.core.net import ensure_public_url
from app.providers.base import (
    Ingredient,
    IngredientGroup,
    ProviderUnavailable,
    RecipeDetail,
)
from app.providers.utils import (
    absolute_image_url,
    canonical_cache_key,
    clean_text,
    normalize_url,
    parse_float,
    parse_ingredient_text,
    parse_int,
    parse_iso_duration,
    parse_servings,
    split_steps,
    web_cache_key,
)


def _find_recipe_jsonld(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text()
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        candidates: list[Any] = []
        if isinstance(data, list):
            candidates.extend(data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                candidates.extend(data["@graph"])
            else:
                candidates.append(data)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            types = candidate.get("@type")
            if isinstance(types, str):
                types = [types]
            if types and any(str(item).lower() == "recipe" for item in types):
                return candidate
    return None


def _jsonld_image(value: object, base_url: str) -> str | None:
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    return absolute_image_url(value, base_url)


def _jsonld_ingredients(value: object) -> list[Ingredient]:
    if not isinstance(value, list):
        value = [value] if value else []
    ingredients: list[Ingredient] = []
    for item in value:
        if not isinstance(item, str):
            continue
        amount, unit, name = parse_ingredient_text(item)
        ingredients.append(Ingredient(name=name, amount=amount, unit=unit))
    return ingredients


def _flatten_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(
            part for part in (_flatten_text(item) for item in value) if part
        )
    if isinstance(value, dict):
        return _flatten_text(value.get("text") or value.get("name") or "")
    return ""


def _jsonld_instructions(value: object) -> list:
    if isinstance(value, str):
        return split_steps(value)
    if isinstance(value, list):
        parts: list[dict[str, str]] = []
        for item in value:
            if isinstance(item, str):
                parts.append({"text": item})
            elif isinstance(item, dict):
                if item.get("@type") == "HowToSection":
                    for child in item.get("itemListElement") or []:
                        if isinstance(child, dict):
                            text = _flatten_text(child.get("text"))
                            if text:
                                parts.append({"text": text})
                else:
                    text = _flatten_text(item.get("text"))
                    if text:
                        parts.append({"text": text})
        return split_steps(parts)
    return []


def _jsonld_category(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if value:
        return [clean_text(value)]
    return []


def _normalize_nutrition(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    mapping = {
        "kcal": ("calories", "kCalories", "energy"),
        "protein": ("proteinContent", "protein"),
        "carbs": ("carbohydrateContent", "carbohydrates"),
        "fat": ("fatContent", "fat"),
        "fiber": ("fiberContent", "fiber"),
        "sugar": ("sugarContent", "sugar"),
        "sodium": ("sodiumContent", "sodium"),
    }
    result: dict[str, object] = {}
    for target, sources in mapping.items():
        for source in sources:
            if raw.get(source) not in (None, ""):
                result[target] = raw[source]
                break
    return result or None


def parse_recipe_html(html: str, url: str) -> RecipeDetail:
    soup = BeautifulSoup(html, "html.parser")
    ld = _find_recipe_jsonld(soup) or {}

    scraper = None
    try:
        scraper = scrape_html(html, org_url=url)
    except Exception:
        scraper = None

    def safe(name: str, default: object = None) -> object:
        if not scraper:
            return default
        try:
            value = getattr(scraper, name)()
            return default if value in (None, "") else value
        except Exception:
            return default

    canonical = str(safe("canonical_url", "")) or str(ld.get("url") or url)
    canonical = normalize_url(canonical) or normalize_url(url)
    image = _jsonld_image(ld.get("image"), canonical)
    if not image:
        image = absolute_image_url(safe("image"), canonical)

    title = clean_text(safe("title", "")) or clean_text(ld.get("name"))
    if not title:
        raise ProviderUnavailable("Auf dieser Seite wurde kein Rezept gefunden.")

    description = clean_text(safe("description", "")) or clean_text(ld.get("description"))
    author_value = safe("author", "") or ld.get("author")
    if isinstance(author_value, dict):
        author_value = author_value.get("name")
    author = clean_text(author_value)

    ingredient_lines: list[str] = []
    raw_ingredients = safe("ingredients", [])
    if isinstance(raw_ingredients, list):
        ingredient_lines = [clean_text(item) for item in raw_ingredients if clean_text(item)]
    if ingredient_lines:
        ingredients = []
        for line in ingredient_lines:
            amount, unit, name = parse_ingredient_text(line)
            ingredients.append(Ingredient(name=name, amount=amount, unit=unit))
    else:
        ingredients = _jsonld_ingredients(ld.get("recipeIngredient"))

    steps = split_steps(safe("instructions", []))
    if not steps:
        steps = _jsonld_instructions(ld.get("recipeInstructions"))

    rating = parse_float(safe("ratings")) or parse_float(
        (ld.get("aggregateRating") or {}).get("ratingValue")
        if isinstance(ld.get("aggregateRating"), dict)
        else None
    )
    rating_count = (
        parse_int(safe("ratings_count"))
        or parse_int(
            (ld.get("aggregateRating") or {}).get("ratingCount")
            if isinstance(ld.get("aggregateRating"), dict)
            else None
        )
        or 0
    )
    servings = parse_servings(safe("yields")) or parse_servings(ld.get("recipeYield"))
    prep_min = parse_int(safe("prep_time")) or parse_iso_duration(ld.get("prepTime"))
    cook_min = parse_int(safe("cook_time")) or parse_iso_duration(ld.get("cookTime"))
    total_min = parse_int(safe("total_time")) or parse_iso_duration(ld.get("totalTime"))
    if not total_min and (prep_min or cook_min):
        total_min = (prep_min or 0) + (cook_min or 0)

    nutrition = _normalize_nutrition(safe("nutrients")) or _normalize_nutrition(
        ld.get("nutrition")
    )
    categories = _jsonld_category(ld.get("recipeCategory")) or _jsonld_category(
        safe("category")
    )
    tags = []
    keywords = ld.get("keywords")
    if isinstance(keywords, str):
        tags = [clean_text(item) for item in re.split(r"[,;]", keywords) if clean_text(item)]
    elif isinstance(keywords, list):
        tags = [clean_text(item) for item in keywords if clean_text(item)]

    return RecipeDetail(
        source="web",
        external_id=canonical,
        cache_key=web_cache_key(canonical),
        title=title,
        subtitle=description[:500],
        description=description,
        image_source_url=image,
        rating=rating,
        rating_count=rating_count,
        prep_min=prep_min,
        cook_min=cook_min,
        total_min=total_min,
        difficulty=None,
        category=categories[0] if categories else "",
        canonical_url=canonical,
        author=author,
        base_servings=servings,
        ingredient_groups=[IngredientGroup(title="", items=ingredients)] if ingredients else [],
        steps=steps,
        nutrition=nutrition,
        tags=tags,
        categories=categories,
        image_count=1 if image else 0,
    )


async def scrape_url(fetcher: FetchPipeline, url: str, settings: Settings) -> RecipeDetail:
    normalized = normalize_url(url)
    await ensure_public_url(normalized, allow_private=settings.allow_private_urls)
    try:
        result = await fetcher.fetch(normalized, kind="html")
    except FetchBlocked as exc:
        raise ProviderUnavailable(
            f"{exc} Falls die Seite dauerhaft blockt, hilft ein Proxy oder FlareSolverr "
            "in den Einstellungen."
        ) from exc
    except FetchFailed as exc:
        raise ProviderUnavailable(str(exc)) from exc
    if result.status == 404:
        raise ProviderUnavailable("Die Rezeptseite wurde nicht gefunden.")
    if result.blocked:
        raise ProviderUnavailable(
            "Die Rezeptseite blockiert automatisierte Zugriffe. Ein Proxy oder "
            "FlareSolverr in den Einstellungen kann helfen – alternativ kannst du "
            "den Rezepttext manuell einfügen."
        )
    if result.status >= 400:
        raise ProviderUnavailable(
            f"Die Rezeptseite antwortet mit HTTP {result.status}."
        )
    content_type = result.content_type
    if "html" not in content_type and "xml" not in content_type:
        raise ProviderUnavailable("Die URL liefert keine HTML-Seite.")
    try:
        return await asyncio.to_thread(parse_recipe_html, result.text, result.url)
    except ProviderUnavailable:
        raise
    except Exception as exc:
        raise ProviderUnavailable("Das Rezept konnte nicht ausgelesen werden.") from exc


def fallback_recipe_from_web(detail: RecipeDetail, *, source: str, external_id: str) -> RecipeDetail:
    detail.source = source
    detail.external_id = external_id
    detail.cache_key = canonical_cache_key(source, external_id)
    return detail
