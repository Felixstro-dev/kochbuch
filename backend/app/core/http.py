from __future__ import annotations

import asyncio

import httpx

from app.core.config import Settings

_IMAGE_ACCEPT = "image/avif,image/webp,image/jpeg,image/png;q=0.9,*/*;q=0.5"


def make_http_client(settings: Settings) -> httpx.AsyncClient:
    headers = {
        "User-Agent": settings.http_user_agent,
        "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
    }
    return httpx.AsyncClient(
        headers=headers,
        timeout=httpx.Timeout(settings.provider_timeout_seconds),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


def image_headers() -> dict[str, str]:
    return {"Accept": _IMAGE_ACCEPT}


class AsyncIntervalLimiter:
    """Serialize calls so a provider sees at most one request per interval."""

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval = min_interval_seconds
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            delay = self.min_interval - (now - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = loop.time()
