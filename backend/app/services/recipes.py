from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import utcnow
from app.db.models import Recipe
from app.providers.base import (
    ProviderError,
    RecipeDetail,
    RecipeNotFound,
    RecipeSummary,
)
from app.providers.registry import ProviderRegistry
from app.providers.utils import (
    chefkoch_id_from_url,
    is_chefkoch_url,
    normalize_url,
)
from app.services import settings as settings_service
from app.services.recipe_store import (
    apply_detail,
    detail_from_row,
    summary_from_row,
)

logger = logging.getLogger(__name__)


class RecipeServiceError(Exception):
    pass


@dataclass(slots=True)
class RecipeResult:
    detail: RecipeDetail
    stale: bool = False
    fetched_at: datetime | None = None


class RecipeService:
    def __init__(
        self,
        registry: ProviderRegistry,
        session_factory,
        settings: Settings,
    ) -> None:
        self.registry = registry
        self.session_factory = session_factory
        self.settings = settings
        self._refreshing: set[str] = set()

    async def get(
        self,
        db: Session,
        cache_key: str,
        *,
        background: BackgroundTasks | None = None,
    ) -> RecipeResult:
        row = db.scalar(select(Recipe).where(Recipe.cache_key == cache_key))
        if row and row.has_detail:
            stale = row.stale_at <= utcnow()
            self._touch(db, row)
            if stale and row.source != "local" and background:
                self._schedule_refresh(background, row.cache_key, row.external_id, row.source)
            return RecipeResult(
                detail=detail_from_row(row),
                stale=stale,
                fetched_at=row.fetched_at,
            )

        source, external_id = self._split_key(cache_key)
        if row:
            external_id = row.external_id
            source = row.source
        if source == "web" and not row:
            raise RecipeServiceError(
                "Für dieses Web-Rezept fehlt die Quell-URL. Bitte die Rezept-URL erneut einfügen."
            )

        provider = await self._get_provider(db, source)
        try:
            detail = await provider.get_recipe(external_id)
        except RecipeNotFound as exc:
            raise RecipeServiceError(str(exc)) from exc
        except ProviderError as exc:
            raise RecipeServiceError(str(exc)) from exc

        if detail.cache_key != cache_key and source != "web":
            detail.cache_key = cache_key
            detail.external_id = external_id
        row = self._upsert_detail(db, detail)
        self._touch(db, row)
        return RecipeResult(
            detail=detail_from_row(row),
            stale=False,
            fetched_at=row.fetched_at,
        )

    async def resolve_url(
        self,
        db: Session,
        url: str,
        *,
        background: BackgroundTasks | None = None,
    ) -> RecipeResult:
        normalized = normalize_url(url)
        parts = urlsplit(normalized)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise RecipeServiceError("Bitte eine gültige http(s)-Rezept-URL angeben.")

        existing = db.scalar(
            select(Recipe).where(
                (Recipe.canonical_url == normalized) | (Recipe.external_id == normalized)
            )
        )
        if existing:
            return await self.get(db, existing.cache_key, background=background)

        if is_chefkoch_url(normalized):
            recipe_id = chefkoch_id_from_url(normalized)
            if recipe_id:
                enabled = settings_service.get_enabled_providers(
                    db, self.settings.enabled_provider_list
                )
                if "chefkoch" in enabled:
                    return await self.get(db, f"chefkoch:{recipe_id}", background=background)

        enabled = settings_service.get_enabled_providers(db, self.settings.enabled_provider_list)
        if "web" not in enabled:
            raise RecipeServiceError("Die Web-Quelle ist deaktiviert.")
        provider = self.registry.get("web")
        if not provider:
            raise RecipeServiceError("Die Web-Quelle ist nicht verfügbar.")
        try:
            detail = await provider.get_recipe(normalized)
        except RecipeNotFound as exc:
            raise RecipeServiceError(str(exc)) from exc
        except ProviderError as exc:
            raise RecipeServiceError(str(exc)) from exc
        row = self._upsert_detail(db, detail)
        self._touch(db, row)
        return RecipeResult(detail=detail_from_row(row), fetched_at=row.fetched_at)

    async def _get_provider(self, db: Session, source: str):
        enabled = settings_service.get_enabled_providers(
            db, self.settings.enabled_provider_list
        )
        if source not in enabled:
            raise RecipeServiceError("Diese Quelle ist deaktiviert.")
        provider = self.registry.get(source)
        if not provider:
            raise RecipeServiceError("Unbekannte Quelle.")
        return provider

    @staticmethod
    def _split_key(cache_key: str) -> tuple[str, str]:
        if ":" not in cache_key:
            raise RecipeServiceError("Ungültiger Rezept-Schlüssel.")
        source, external_id = cache_key.split(":", 1)
        if not source or not external_id:
            raise RecipeServiceError("Ungültiger Rezept-Schlüssel.")
        return source, external_id

    def _upsert_detail(self, db: Session, detail: RecipeDetail) -> Recipe:
        row = db.scalar(select(Recipe).where(Recipe.cache_key == detail.cache_key))
        if not row:
            row = Recipe(
                cache_key=detail.cache_key,
                source=detail.source,
                external_id=detail.external_id,
                title=detail.title,
            )
            db.add(row)
        apply_detail(row, detail, stale_day_offset=self.settings.recipe_stale_days)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def _touch(db: Session, row: Recipe) -> None:
        row.access_count = (row.access_count or 0) + 1
        row.last_accessed_at = utcnow()
        db.commit()

    def _schedule_refresh(
        self,
        background: BackgroundTasks,
        cache_key: str,
        external_id: str,
        source: str,
    ) -> None:
        if cache_key in self._refreshing:
            return
        self._refreshing.add(cache_key)
        background.add_task(self._refresh, cache_key, external_id, source)

    async def _refresh(self, cache_key: str, external_id: str, source: str) -> None:
        try:
            with self.session_factory() as db:
                provider = await self._get_provider(db, source)
                detail = await provider.get_recipe(external_id)
                row = db.scalar(select(Recipe).where(Recipe.cache_key == cache_key))
                if not row:
                    return
                apply_detail(row, detail, stale_day_offset=self.settings.recipe_stale_days)
                db.commit()
        except Exception:
            logger.warning("Hintergrund-Aktualisierung für %s fehlgeschlagen", cache_key, exc_info=True)
        finally:
            self._refreshing.discard(cache_key)

    def ensure_detail(
        self, db: Session, cache_key: str, background: BackgroundTasks
    ) -> None:
        row = db.scalar(select(Recipe).where(Recipe.cache_key == cache_key))
        if row and not row.has_detail and row.source != "web":
            self._schedule_refresh(background, row.cache_key, row.external_id, row.source)

    def update(
        self,
        db: Session,
        cache_key: str,
        *,
        is_favorite: bool | None = None,
        is_saved: bool | None = None,
        tags: list[str] | None = None,
        background: BackgroundTasks | None = None,
    ) -> Recipe:
        row = db.scalar(select(Recipe).where(Recipe.cache_key == cache_key))
        if not row:
            raise RecipeNotFound("Rezept nicht gefunden.")
        if is_favorite is not None:
            row.is_favorite = is_favorite
            if is_favorite:
                row.is_saved = True
        if is_saved is not None:
            row.is_saved = is_saved
        if tags is not None:
            cleaned: list[str] = []
            for tag in tags:
                value = tag.strip()[:40]
                if value and value.lower() not in {existing.lower() for existing in cleaned}:
                    cleaned.append(value)
            row.tags = cleaned[:50]
        db.commit()
        db.refresh(row)
        if background and row.is_favorite and not row.has_detail and row.source != "web":
            self._schedule_refresh(background, row.cache_key, row.external_id, row.source)
        return row

    def list_favorites(self, db: Session, limit: int = 100) -> list[RecipeSummary]:
        rows = db.scalars(
            select(Recipe)
            .where(Recipe.is_favorite.is_(True))
            .order_by(Recipe.last_accessed_at.desc(), Recipe.fetched_at.desc())
            .limit(limit)
        )
        return [summary_from_row(row) for row in rows]

    def list_saved(self, db: Session, limit: int = 100) -> list[RecipeSummary]:
        rows = db.scalars(
            select(Recipe)
            .where(Recipe.is_saved.is_(True))
            .order_by(Recipe.last_accessed_at.desc(), Recipe.fetched_at.desc())
            .limit(limit)
        )
        return [summary_from_row(row) for row in rows]
