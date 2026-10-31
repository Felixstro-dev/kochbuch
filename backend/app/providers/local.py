from __future__ import annotations

from sqlalchemy import func, or_, select

from app.db.models import Recipe
from app.providers.base import (
    ProviderSearchResult,
    RecipeDetail,
    RecipeNotFound,
    RecipeSummary,
    SearchQuery,
)
from app.services.recipe_store import detail_from_row, summary_from_row


class LocalProvider:
    name = "local"
    label = "Eigene"
    can_search = True

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def search(self, query: SearchQuery) -> ProviderSearchResult:
        with self.session_factory() as db:
            stmt = select(Recipe).where(Recipe.source == "local")
            if query.text.strip():
                pattern = f"%{query.text.strip()}%"
                stmt = stmt.where(
                    or_(
                        Recipe.title.ilike(pattern),
                        Recipe.subtitle.ilike(pattern),
                        Recipe.description.ilike(pattern),
                    )
                )
            if query.difficulty:
                stmt = stmt.where(Recipe.difficulty == query.difficulty)
            if query.max_time:
                stmt = stmt.where(
                    or_(Recipe.total_min.is_(None), Recipe.total_min <= query.max_time)
                )
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total = int(db.scalar(count_stmt) or 0)
            if query.sort == "rating":
                stmt = stmt.order_by(Recipe.rating.desc().nullslast(), Recipe.title)
            elif query.sort == "time":
                stmt = stmt.order_by(Recipe.total_min.asc().nullslast(), Recipe.title)
            else:
                stmt = stmt.order_by(Recipe.title)
            stmt = stmt.offset(max(query.page - 1, 0) * query.limit).limit(query.limit)
            rows = list(db.scalars(stmt))
            return ProviderSearchResult(
                items=[summary_from_row(row) for row in rows],
                total=total,
            )

    async def get_recipe(self, external_id: str) -> RecipeDetail:
        cache_key = (
            external_id if external_id.startswith("local:") else f"local:{external_id}"
        )
        with self.session_factory() as db:
            row = db.scalar(select(Recipe).where(Recipe.cache_key == cache_key))
            if not row:
                raise RecipeNotFound("Das lokale Rezept wurde nicht gefunden.")
            return detail_from_row(row)
