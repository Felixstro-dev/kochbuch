from __future__ import annotations

import asyncio

import httpx
import respx

from app.core.config import Settings
from app.providers.base import SearchQuery
from app.providers.chefkoch import ChefkochProvider
from app.providers.scraper import parse_recipe_html
from app.providers.utils import detect_timer, parse_ingredient_text, split_steps

DETAIL = {
    "id": "123456",
    "title": "Test-Lasagne",
    "subtitle": "Schnelle Test-Lasagne",
    "owner": {"displayName": "Testköchin"},
    "rating": {"rating": 4.5, "numVotes": 42},
    "difficulty": 2,
    "preparationTime": 20,
    "cookingTime": 30,
    "restingTime": 10,
    "totalTime": 60,
    "servings": 4,
    "imageCount": 2,
    "previewImageUrlTemplate": "https://img.example/rezept/<format>/bild.jpg",
    "siteUrl": "https://www.chefkoch.de/rezepte/123456/Test-Lasagne.html",
    "categoryBreadcrumb": [
        {"title": "Menüart"},
        {"title": "Hauptspeise"},
        {"title": "Pasta"},
    ],
    "tags": ["Hauptspeise", "Pasta"],
    "nutrition": {"kCalories": 500, "proteinContent": 20, "fatContent": 18},
    "instructions": (
        "Zwiebeln würfeln.\n\n"
        "Hackfleisch 5 - 7 Min. anbraten.\n\n"
        "Alles 30 Min. backen."
    ),
    "ingredientGroups": [
        {
            "header": "Für die Sauce:",
            "ingredients": [
                {"name": "Zwiebel(n)", "amount": 2, "unit": "", "usageInfo": ""},
                {"name": "Hackfleisch", "amount": 500, "unit": "g", "usageInfo": ""},
                {"name": "Fett", "amount": 0, "unit": "", "usageInfo": ""},
            ],
        }
    ],
}

SEARCH = {
    "count": 1,
    "results": [
        {
            "recipe": {
                "id": "123456",
                "title": "Test-Lasagne",
                "subtitle": "Schnelle Test-Lasagne",
                "rating": {"rating": 4.5, "numVotes": 42},
                "difficulty": 2,
                "preparationTime": 20,
                "totalTime": 60,
                "previewImageUrlTemplate": "https://img.example/rezept/<format>/bild.jpg",
                "siteUrl": "https://www.chefkoch.de/rezepte/123456/Test-Lasagne.html",
            }
        }
    ],
}


def _settings() -> Settings:
    return Settings(
        testing=True,
        chefkoch_min_interval=0,
        provider_timeout_seconds=5,
    )


def test_chefkoch_search_and_detail_mapping() -> None:
    settings = _settings()

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            provider = ChefkochProvider(client, settings)
            with respx.mock:
                respx.get("https://api.chefkoch.de/v2/recipes").mock(
                    return_value=httpx.Response(200, json=SEARCH)
                )
                result = await provider.search(SearchQuery(text="lasagne", limit=5))
                assert result.total == 1
                item = result.items[0]
                assert item.cache_key == "chefkoch:123456"
                assert item.image_source_url.endswith("crop-480x360/bild.jpg")
                assert item.rating == 4.5

            with respx.mock:
                respx.get("https://api.chefkoch.de/v2/recipes/123456").mock(
                    return_value=httpx.Response(200, json=DETAIL)
                )
                detail = await provider.get_recipe("123456")
                assert detail.title == "Test-Lasagne"
                assert detail.author == "Testköchin"
                assert detail.base_servings == 4
                assert detail.total_min == 60
                assert detail.category == "Hauptspeise"
                assert detail.nutrition == {"kcal": 500, "protein": 20, "fat": 18}
                assert len(detail.steps) == 3
                assert detail.steps[1].timer_seconds == 420
                group = detail.ingredient_groups[0]
                assert group.title == "Für die Sauce:"
                assert group.items[1].name == "Hackfleisch"
                assert group.items[1].amount == 500
                assert group.items[2].amount is None

    asyncio.run(run())


def test_web_jsonld_fallback_parses_arrays_and_amounts() -> None:
    html = """
    <html><head>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Recipe",
      "name": "Testkuchen",
      "image": {"@type": "ImageObject", "url": "https://example.com/kuchen.jpg"},
      "author": {"@type": "Person", "name": "Test"},
      "recipeYield": "8 Stück",
      "prepTime": "PT15M",
      "cookTime": "PT45M",
      "recipeIngredient": ["200 g Mehl", "2 Eier", "1 Prise Salz"],
      "recipeInstructions": [
        {"@type": "HowToStep", "text": ["Teig rühren", "und 10 Min. ruhen lassen."]},
        {"@type": "HowToStep", "text": "Bei 180 Grad 45 Min. backen."}
      ],
      "recipeCategory": "Kuchen",
      "aggregateRating": {"ratingValue": "4,5", "ratingCount": "12"}
    }
    </script></head><body></body></html>
    """
    detail = parse_recipe_html(html, "https://example.com/rezept")
    assert detail.title == "Testkuchen"
    assert detail.base_servings == 8
    assert detail.prep_min == 15
    assert detail.total_min == 60
    assert detail.rating == 4.5
    assert detail.rating_count == 12
    assert len(detail.ingredient_groups[0].items) == 3
    assert detail.ingredient_groups[0].items[0].amount == 200
    assert detail.ingredient_groups[0].items[0].unit == "g"
    assert len(detail.steps) == 2
    assert detail.steps[0].text == "Teig rühren und 10 Min. ruhen lassen."
    assert detail.steps[0].timer_seconds == 600


def test_step_and_timer_edge_cases() -> None:
    steps = split_steps("1. Zwiebeln würfeln.\n2. 5-7 Min. anbraten.\n3. Servieren.")
    assert len(steps) == 3
    assert steps[1].timer_seconds == 420
    assert detect_timer("1 - 2 EL Öl") is None
    assert detect_timer("30 Sekunden warten") == 30
    assert parse_ingredient_text("1 1/2 Tassen Mehl") == (1.5, "Tassen", "Mehl")
    assert parse_ingredient_text("Salz") == (None, "", "Salz")
