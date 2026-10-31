from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import logging
import time
from pathlib import Path
from urllib.parse import quote

import blurhash
from fastapi import HTTPException, status
from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.fetch import FetchPipeline
from app.core.net import ensure_public_url
from app.db.base import utcnow
from app.db.models import Image, Recipe
from app.providers.base import ProviderUnavailable

logger = logging.getLogger(__name__)

VARIANTS: dict[str, tuple[int, int]] = {
    "thumb": (320, 240),
    "card": (640, 480),
    "hero": (1200, 900),
}

IMAGE_TTL_SECONDS = 7 * 24 * 60 * 60


class ImageError(Exception):
    pass


class ImageService:
    def __init__(self, settings: Settings, fetcher: FetchPipeline) -> None:
        self.settings = settings
        self.fetcher = fetcher
        self.image_dir = settings.data_path / "images"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    def sign_url(
        self, cache_key: str, variant: str = "card", ttl: int = IMAGE_TTL_SECONDS
    ) -> str:
        expires = int(time.time()) + ttl
        signature = hmac.new(
            self.settings.secret_key.encode(),
            f"{cache_key}:{variant}:{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()[:40]
        return (
            f"/api/v1/images/{quote(cache_key, safe=':')}/{variant}"
            f"?exp={expires}&sig={signature}"
        )

    def verify(self, cache_key: str, variant: str, expires: int, signature: str) -> bool:
        if expires < int(time.time()):
            return False
        expected = hmac.new(
            self.settings.secret_key.encode(),
            f"{cache_key}:{variant}:{expires}".encode(),
            hashlib.sha256,
        ).hexdigest()[:40]
        return hmac.compare_digest(expected, signature)

    async def get(
        self, db: Session, cache_key: str, variant: str
    ) -> tuple[Path, str, str]:
        if variant not in VARIANTS:
            raise ImageError("Unbekannte Bildgröße.")
        recipe = db.scalar(select(Recipe).where(Recipe.cache_key == cache_key))
        if not recipe:
            raise ImageError("Rezept nicht gefunden.")
        source_url = recipe.image_source_url
        if not source_url:
            raise ImageError("Für dieses Rezept ist kein Bild hinterlegt.")

        source_hash = hashlib.sha256(source_url.encode()).hexdigest()
        key = f"{source_hash}:{variant}"
        cached = self._find_cached(db, key)
        if cached:
            return cached

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = self._find_cached(db, key)
            if cached:
                return cached
            try:
                path, width, height, byte_size, blur = await self._build(
                    source_url, source_hash, variant
                )
            except Exception as exc:
                logger.warning("Bild konnte nicht geladen werden (%s): %s", source_url, exc)
                raise ImageError("Bild konnte nicht geladen werden.") from exc

            rel_path = str(path.relative_to(self.settings.data_path))
            image = Image(
                key=key,
                recipe_id=recipe.id,
                source_url_hash=source_hash,
                variant=variant,
                rel_path=rel_path,
                width=width,
                height=height,
                byte_size=byte_size,
                mime_type="image/webp",
                etag=f'"{source_hash[:24]}-{variant}"',
                blurhash=blur,
            )
            db.add(image)
            if not recipe.image_blurhash and blur:
                recipe.image_blurhash = blur
            db.commit()
            return path, image.etag, image.mime_type

    def _find_cached(self, db: Session, key: str) -> tuple[Path, str, str] | None:
        image = db.get(Image, key)
        if not image:
            return None
        path = self.settings.data_path / image.rel_path
        if not path.exists():
            db.delete(image)
            db.commit()
            return None
        image.last_used_at = utcnow()
        db.commit()
        return path, image.etag, image.mime_type

    async def _build(
        self, source_url: str, source_hash: str, variant: str
    ) -> tuple[Path, int, int, int, str | None]:
        await ensure_public_url(
            source_url, allow_private=self.settings.allow_private_urls
        )
        try:
            response = await self.fetcher.fetch(
                source_url, kind="image", allow_flare=False
            )
        except Exception as exc:
            raise ProviderUnavailable("Bild konnte nicht geladen werden.") from exc
        if response.status >= 400:
            raise ProviderUnavailable(f"HTTP {response.status}")
        content_type = response.content_type
        if not content_type.startswith("image/"):
            raise ProviderUnavailable("Quelle ist kein Bild.")
        content = response.content
        if len(content) > self.settings.image_max_bytes:
            raise ProviderUnavailable("Bild ist zu groß.")

        width, height = VARIANTS[variant]
        return await asyncio.to_thread(
            self._process, content, source_hash, variant, width, height
        )

    def _process(
        self, content: bytes, source_hash: str, variant: str, width: int, height: int
    ) -> tuple[Path, int, int, int, str | None]:
        with PILImage.open(io.BytesIO(content)) as original:
            original = ImageOps.exif_transpose(original).convert("RGB")
            fitted = ImageOps.fit(
                original, (width, height), method=PILImage.Resampling.LANCZOS
            )
            folder = self.image_dir / source_hash[:2]
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{source_hash[:20]}-{variant}.webp"
            fitted.save(path, format="WEBP", quality=84, method=6)
            small = fitted.copy()
            small.thumbnail((32, 32))
            pixels = list(small.getdata())
            small_width, small_height = small.size
            rows = [
                pixels[y * small_width : (y + 1) * small_width]
                for y in range(small_height)
            ]
            blur = blurhash.encode(rows, components_x=4, components_y=3)
            size = path.stat().st_size
            return path, fitted.width, fitted.height, size, blur


def raise_image_http_error(exc: ImageError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
