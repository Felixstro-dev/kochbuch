from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


class UpdateChecker:
    """Vergleicht das laufende Image mit dem neuesten GHCR-`latest`-Digest.

    Der CI brennt die Git-SHA als `GIT_SHA` ins Image und vergleichsweise als
    `sha-<kurz>`-Tag ins Registry. Stimmen die Digests von `latest` und dem
    eigenen Tag überein, läuft die neueste Version.
    """

    def __init__(self, image: str, git_sha: str, interval_seconds: int) -> None:
        self.image = image.strip().lower().removeprefix("ghcr.io/")
        self.git_sha = (git_sha or "unknown").strip().lower()
        self.interval_seconds = max(60, interval_seconds)
        self.update_available = False
        self.latest_digest: str | None = None
        self.own_digest: str | None = None
        self.checked_at: datetime | None = None
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return self.git_sha not in {"", "unknown"} and "/" in self.image

    @property
    def short_sha(self) -> str:
        return self.git_sha[:7]

    def state(self, dokploy_url: str = "") -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "current_sha": self.git_sha if self.enabled else None,
            "current_short": self.short_sha if self.enabled else None,
            "update_available": self.update_available if self.enabled else False,
            "latest_digest": self.latest_digest,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
            "last_error": self.last_error,
            "interval_seconds": self.interval_seconds,
            "dokploy_url": dokploy_url,
        }

    async def _token(self, client: httpx.AsyncClient) -> str | None:
        response = await client.get(
            "https://ghcr.io/token",
            params={"service": "ghcr.io", "scope": f"repository:{self.image}:pull"},
        )
        if response.status_code != 200:
            return None
        return response.json().get("token")

    async def _digest(
        self, client: httpx.AsyncClient, token: str | None, tag: str
    ) -> str | None:
        headers = {"Accept": _ACCEPT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = await client.get(
            f"https://ghcr.io/v2/{self.image}/manifests/{tag}", headers=headers
        )
        if response.status_code != 200:
            return None
        return response.headers.get("docker-content-digest")

    async def check(self) -> dict[str, object]:
        """Einmalig prüfen. Aktualisiert den Zustand und liefert ihn."""
        if not self.enabled:
            return self.state()

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                token = await self._token(client)
                latest = await self._digest(client, token, "latest")
                own = None
                for tag in (f"sha-{self.short_sha}", f"sha-{self.git_sha}"):
                    own = await self._digest(client, token, tag)
                    if own:
                        break

            self.latest_digest = latest
            self.own_digest = own
            if latest and own:
                self.update_available = latest != own
                self.last_error = None
            else:
                self.update_available = False
                self.last_error = "Vergleich nicht möglich (Tag nicht gefunden)."
        except Exception as exc:  # noqa: BLE001 - Check darf den Dienst nicht stören
            self.update_available = False
            self.last_error = f"Update-Check fehlgeschlagen: {exc}"
            logger.warning("Update-Check fehlgeschlagen: %s", exc)

        self.checked_at = datetime.now(timezone.utc)
        return self.state()

    async def run_loop(self) -> None:
        """Hintergrund-Task: sofort prüfen, dann im Stundenrhythmus."""
        while True:
            await self.check()
            await asyncio.sleep(self.interval_seconds)


def start_update_loop(checker: UpdateChecker) -> asyncio.Task:
    task = asyncio.create_task(checker.run_loop())
    task.add_done_callback(_log_task_end)
    return task


def _log_task_end(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    with contextlib.suppress(Exception):
        exc = task.exception()
        if exc:
            logger.warning("Update-Check-Task endete: %s", exc)
