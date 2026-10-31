from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import utcnow
from app.db.models import Recipe, SearchCache
from app.providers.base import ProviderError, RecipeSummary, SearchQuery
from app.providers.registry import ProviderRegistry
from app.providers.utils import normalize_url
from app.services import settings as settings_service
from app.services.recipe_store import (
    apply_summary,
    summary_from_dict,
    summary_from_row,
    summary_to_dict,
)

logger = logging.getLogger(__name__)


class SearchServiceError(Exception):
    pass


@dataclass(slots=True)
class SearchResult:
    items: list[RecipeSummary]
    total: int
    page: int
    limit: int
    providers: list[str]
    cached: bool = False
    stale: bool = False
    errors: list[str] = field(default_factory=list)
    took_ms: int = 0


class SearchService:
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

    def _cache_key(self, query: SearchQuery, providers: list[str]) -> str:
        payload = {
            "q": query.text.strip().lower(),
            "page": query.page,
            "limit": query.limit,
            "max_time": query.max_time,
            "difficulty": query.difficulty,
            "category": query.category,
            "sort": query.sort,
            "providers": sorted(providers),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    async def _search_web_recipes(
        self, db: Session, query: SearchQuery, enabled_providers: list[str]
    ) -> tuple[list[RecipeSummary], int]:
        """Search for web recipes in the local database."""
        from app.providers.utils import normalize_url as norm_url

        pattern = f"%{query.text.strip().lower()}%" if query.text.strip() else ""
        stmt = select(Recipe).where(Recipe.source == "web")
        if query.text.strip():
            stmt = stmt.where(
                or_(
                    Recipe.title.ilike(pattern),
                    Recipe.subtitle.ilike(pattern),
                    Recipe.description.ilike(pattern),
                )
            )
        if query.difficulty is not None:
            stmt = stmt.where(Recipe.difficulty == query.difficulty)
        if query.max_time is not None:
            stmt = stmt.where(or_(Recipe.total_min.is_(None), Recipe.total_min <= query.max_time))
        stmt = stmt.order_by(Recipe.title)
        rows = list(db.scalars(stmt))
        items = [summary_from_row(row) for row in rows]
        total = len(items)
        return items, total

    async def search(
        self,
        db: Session,
        query: SearchQuery,
        *,
        sources: list[str] | None = None,
        background: BackgroundTasks | None = None,
        refresh: bool = False,
    ) -> SearchResult:
        started = time.perf_counter()
        enabled = settings_service.get_enabled_providers(
            db, self.settings.enabled_provider_list
        )
        if sources:
            enabled = [name for name in enabled if name in sources]
        providers = self.registry.searchable(enabled)
        if not providers:
            raise SearchServiceError("Keine durchsuchbare Quelle ist aktiv.")
        provider_names = [provider.name for provider in providers]
        cache_key = self._cache_key(query, provider_names)

        cached = None if refresh else db.get(SearchCache, cache_key)
        if cached:
            stale = cached.expires_at <= utcnow()
            payload = cached.payload
            result = self._materialize(db, payload, query, provider_names)
            result.cached = True
            result.stale = stale
            result.took_ms = int((time.perf_counter() - started) * 1000)
            if stale and background:
                self._schedule_refresh(background, cache_key, query, provider_names)
            return result

        items, total, errors = await self._fetch(providers, query)
        items = self._dedupe(items)

        # Also include web recipes from the database
        db_items, db_total = await self._search_web_recipes(db, query, enabled)
        items.extend(db_items)
        total += db_total

        self._store_summaries(db, items)
        self._save_cache(db, cache_key, items, total, errors)
        result = self._materialize(
            db,
            {"items": [summary_to_dict(item) for item in items], "total": total, "errors": errors},
            query,
            provider_names,
        )
        result.took_ms = int((time.perf_counter() - started) * 1000)
        return result

    async def _fetch(self, providers, query: SearchQuery) -> tuple[list[RecipeSummary], int, list[str]]:
        tasks = [
            asyncio.wait_for(
                provider.search(query), timeout=self.settings.provider_timeout_seconds + 2
            )
            for provider in providers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: list[RecipeSummary] = []
        total = 0
        errors: list[str] = []
        for provider, result in zip(providers, results, strict=False):
            if isinstance(result, BaseException):
                message = str(result) if isinstance(result, ProviderError) else "Quelle nicht erreichbar."
                logger.warning("Suche bei %s fehlgeschlagen: %s", provider.name, result)
                errors.append(f"{provider.label}: {message}")
                continue
            items.extend(result.items)
            total += result.total
        return items, total, errors

    @staticmethod
    def _dedupe(items: list[RecipeSummary]) -> list[RecipeSummary]:
        seen_keys: set[str] = set()
        seen_urls: set[str] = set()
        result: list[RecipeSummary] = []
        for item in items:
            url = normalize_url(item.canonical_url) if item.canonical_url else ""
            if item.cache_key in seen_keys or (url and url in seen_urls):
                continue
            seen_keys.add(item.cache_key)
            if url:
                seen_urls.add(url)
            result.append(item)
        return result

    def _save_cache(
        self,
        db: Session,
        cache_key: str,
        items: list[RecipeSummary],
        total: int,
        errors: list[str],
    ) -> None:
        payload = {
            "items": [summary_to_dict(item) for item in items],
            "total": total,
            "errors": errors,
        }
        now = utcnow()
        entry = db.get(SearchCache, cache_key)
        if entry:
            entry.payload = payload
            entry.created_at = now
            entry.expires_at = now + timedelta(seconds=self.settings.search_cache_seconds)
        else:
            db.add(
                SearchCache(
                    key=cache_key,
                    payload=payload,
                    created_at=now,
                    expires_at=now + timedelta(seconds=self.settings.search_cache_seconds),
                )
            )
        db.commit()

    def _store_summaries(self, db: Session, items: list[RecipeSummary]) -> None:
        if not items:
            return
        keys = [item.cache_key for item in items]
        existing = {
            row.cache_key: row
            for row in db.scalars(select(Recipe).where(Recipe.cache_key.in_(keys)))
        }
        for item in items:
            row = existing.get(item.cache_key)
            if not row:
                row = Recipe(
                    cache_key=item.cache_key,
                    source=item.source,
                    external_id=item.external_id,
                    title=item.title,
                )
                db.add(row)
            apply_summary(row, item, stale_day_offset=self.settings.recipe_stale_days)
        db.commit()

    def _materialize(
        self,
        db: Session,
        payload: dict,
        query: SearchQuery,
        provider_names: list[str],
    ) -> SearchResult:
        items = [
            summary_from_dict(raw)
            for raw in payload.get("items") or []
            if isinstance(raw, dict)
        ]
        self._apply_favorites(db, items)
        self._sort(items, query.sort)
        return SearchResult(
            items=items,
            total=int(payload.get("total") or len(items)),
            page=query.page,
            limit=query.limit,
            providers=provider_names,
            errors=list(payload.get("errors") or []),
        )

    @staticmethod
    def _apply_favorites(db: Session, items: list[RecipeSummary]) -> None:
        if not items:
            return
        keys = [item.cache_key for item in items]
        urls = [normalize_url(item.canonical_url) for item in items if item.canonical_url]
        conditions = [Recipe.cache_key.in_(keys)]
        if urls:
            conditions.append(Recipe.canonical_url.in_(urls))
        rows = list(db.scalars(select(Recipe).where(or_(*conditions))))
        by_key = {row.cache_key: row for row in rows}
        by_url = {normalize_url(row.canonical_url): row for row in rows if row.canonical_url}
        for item in items:
            row = by_key.get(item.cache_key) or by_url.get(normalize_url(item.canonical_url))
            if not row:
                continue
            item.is_favorite = row.is_favorite
            item.is_saved = row.is_saved
            item.image_blurhash = row.image_blurhash
            if not item.category and row.categories:
                item.category = str(row.categories[0])

    @staticmethod
    def _sort(items: list[RecipeSummary], sort: str) -> None:
        def rank(index: int, item: RecipeSummary) -> tuple:
            if sort == "rating":
                score = (item.rating or 0) * 10 + min(item.rating_count, 500) / 500
            elif sort == "time":
                score = -(item.total_min or 9999)
            else:
                score = 1 / (index + 1) + (item.rating or 0) / 25
            return (0 if item.is_favorite else 1, -score, index)

        decorated = [(index, item) for index, item in enumerate(items)]
        decorated.sort(key=lambda pair: rank(*pair))
        items[:] = [item for _, item in decorated]

    def _schedule_refresh(
        self,
        background: BackgroundTasks,
        cache_key: str,
        query: SearchQuery,
        provider_names: list[str],
    ) -> None:
        if cache_key in self._refreshing:
            return
        self._refreshing.add(cache_key)
        background.add_task(self._refresh, cache_key, query, provider_names)

    async def _refresh(
        self, cache_key: str, query: SearchQuery, provider_names: list[str]
    ) -> None:
        try:
            providers = [
                provider
                for name in provider_names
                if (provider := self.registry.get(name)) is not None
            ]
            items, total, errors = await self._fetch(providers, query)
            items = self._dedupe(items)
            with self.session_factory() as db:
                self._store_summaries(db, items)
                self._save_cache(db, cache_key, items, total, errors)
        except Exception:
            logger.exception("Hintergrund-Aktualisierung der Suche fehlgeschlagen")
        finally:
            self._refreshing.discard(cache_key)
