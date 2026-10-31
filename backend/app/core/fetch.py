"""Central fetch pipeline with staged escalation.

All outbound HTTP traffic (Chefkoch API, recipe pages, images) goes through
:class:`FetchPipeline`. It tries the cheapest strategy first and only escalates
when the target actually blocks us:

1. direct request with a rotation of consistent browser signatures,
2. optional HTTP/SOCKS proxy,
3. optional FlareSolverr instance for challenge-protected HTML pages.

The pipeline also remembers the tier that worked per domain, keeps a circuit
breaker per domain and exposes its state for the settings UI.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

TIER_DIRECT = "direct"
TIER_PROXY = "proxy"
TIER_FLARESOLVERR = "flaresolverr"
TIERS = (TIER_DIRECT, TIER_PROXY, TIER_FLARESOLVERR)

IMAGE_ACCEPT = "image/avif,image/webp,image/jpeg,image/png;q=0.9,*/*;q=0.5"
HTML_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,*/*;q=0.8"
)
JSON_ACCEPT = "application/json, text/plain;q=0.9, */*;q=0.8"

BLOCKED_STATUS = {403, 429, 503}
CHALLENGE_MARKERS = (
    "just a moment",
    "cf-challenge",
    "challenge-platform",
    "attention required",
    "access denied",
    "captcha",
    "checking your browser",
    "are you a robot",
    "ddos protection",
    "unusual traffic",
)

# Stage labels shown by the UI while a fetch is escalated.
STAGE_LABELS = {
    "direct": "Seite wird geladen…",
    "retry": "Zweiter Versuch…",
    "proxy": "Proxy wird versucht…",
    "flaresolverr": "Schutzabfrage wird umgangen…",
}

try:  # pragma: no cover - optional dependency
    from curl_cffi.requests import AsyncSession as CurlAsyncSession

    HAS_CURL_CFFI = True
except Exception:  # pragma: no cover - import failures are non-fatal
    CurlAsyncSession = None  # type: ignore[assignment,misc]
    HAS_CURL_CFFI = False


@dataclass(frozen=True, slots=True)
class BrowserProfile:
    name: str
    user_agent: str
    accept_language: str
    sec_ch_ua: str | None = None
    sec_ch_ua_platform: str | None = None
    impersonate: str = "chrome"

    def headers(self, accept: str) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept,
            "Accept-Language": self.accept_language,
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
        if self.sec_ch_ua:
            headers["Sec-CH-UA"] = self.sec_ch_ua
            headers["Sec-CH-UA-Mobile"] = "?0"
        if self.sec_ch_ua_platform:
            headers["Sec-CH-UA-Platform"] = self.sec_ch_ua_platform
        return headers


PROFILES: tuple[BrowserProfile, ...] = (
    BrowserProfile(
        name="chrome-linux",
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        accept_language="de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        sec_ch_ua='"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
        sec_ch_ua_platform='"Linux"',
        impersonate="chrome",
    ),
    BrowserProfile(
        name="chrome-windows",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        accept_language="de-DE,de;q=0.8,en-US;q=0.6,en;q=0.5",
        sec_ch_ua='"Chromium";v="130", "Not_A Brand";v="24", "Google Chrome";v="130"',
        sec_ch_ua_platform='"Windows"',
        impersonate="chrome",
    ),
    BrowserProfile(
        name="firefox-linux",
        user_agent="Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
        accept_language="de,en-US;q=0.9,en;q=0.8",
        impersonate="firefox",
    ),
    BrowserProfile(
        name="safari-macos",
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.1 Safari/605.1.15"
        ),
        accept_language="de-DE,de;q=0.9",
        impersonate="safari",
    ),
)


@dataclass(slots=True)
class FetchConfig:
    proxy_url: str | None = None
    proxy_for_images: bool = True
    flaresolverr_url: str | None = None
    flaresolverr_timeout: int = 60
    max_retries: int = 3
    timeout: float = 15.0
    min_interval: float = 0.4
    circuit_threshold: int = 4
    circuit_cooldown: float = 60.0
    use_browser_impersonation: bool = True

    @classmethod
    def from_settings(cls, settings: Settings) -> FetchConfig:
        return cls(
            proxy_url=settings.fetch_proxy_url or None,
            proxy_for_images=settings.fetch_proxy_for_images,
            flaresolverr_url=settings.flaresolverr_url or None,
            flaresolverr_timeout=settings.flaresolverr_timeout,
            max_retries=settings.fetch_max_retries,
            timeout=settings.fetch_timeout,
            min_interval=settings.fetch_min_interval,
            circuit_threshold=settings.fetch_circuit_threshold,
            circuit_cooldown=settings.fetch_circuit_cooldown,
            use_browser_impersonation=settings.fetch_browser_impersonation,
        )

    def apply_values(self, values: dict[str, Any]) -> None:
        """Merge values stored in the settings table over the env defaults."""

        def flag(key: str) -> bool | None:
            value = values.get(key)
            if value is None:
                return None
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)

        def text(key: str) -> str | None:
            value = values.get(key)
            if value is None:
                return None
            return str(value).strip()

        proxy = text("fetch_proxy_url")
        if proxy is not None:
            self.proxy_url = proxy or None
        flare = text("flaresolverr_url")
        if flare is not None:
            self.flaresolverr_url = flare or None
        if (value := flag("fetch_proxy_for_images")) is not None:
            self.proxy_for_images = value
        if (value := flag("fetch_browser_impersonation")) is not None:
            self.use_browser_impersonation = value
        for key, attribute, cast, minimum, maximum in (
            ("flaresolverr_timeout", "flaresolverr_timeout", int, 5, 300),
            ("fetch_max_retries", "max_retries", int, 1, 8),
            ("fetch_timeout", "timeout", float, 3.0, 120.0),
        ):
            raw = values.get(key)
            if raw in (None, ""):
                continue
            try:
                parsed = cast(raw)
            except (TypeError, ValueError):
                continue
            setattr(self, attribute, max(minimum, min(maximum, parsed)))


class FetchError(Exception):
    """Base error for the fetch pipeline. Messages are safe for API responses."""


class FetchBlocked(FetchError):
    """The domain is temporarily paused by the circuit breaker."""


class FetchFailed(FetchError):
    """All escalation tiers failed."""


@dataclass(slots=True)
class FetchResult:
    url: str
    status: int
    text: str
    content: bytes
    headers: dict[str, str]
    tier: str
    attempts: int
    elapsed_ms: int
    blocked: bool = False

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300 and not self.blocked

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "")

    def json(self) -> Any:
        import json

        return json.loads(self.text)


@dataclass(slots=True)
class _DomainState:
    domain: str
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_request_at: float = 0.0
    last_tier: str | None = None
    last_tier_at: float = 0.0
    failures: int = 0
    successes: int = 0
    circuit_until: float = 0.0
    flare_session: str | None = None
    stage: str = ""
    active_tier: str = ""
    active_attempt: int = 0
    active_started_at: float = 0.0


def _now_iso(timestamp: float | None = None) -> str | None:
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())


def looks_blocked(status: int, body: str) -> bool:
    if status in BLOCKED_STATUS:
        return True
    head = body[:20000].lower()
    return any(marker in head for marker in CHALLENGE_MARKERS)


def _redact_proxy(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    auth = "***@" if parts.username or parts.password else ""
    return f"{parts.scheme}://{auth}{host}{port}"


class FetchPipeline:
    """Shared, stateful HTTP client used by every provider."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        config: FetchConfig | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.config = config or FetchConfig.from_settings(settings)
        self._proxy_client: httpx.AsyncClient | None = None
        self._proxy_client_url: str | None = None
        self._curl_sessions: dict[str, Any] = {}
        self._domains: dict[str, _DomainState] = {}
        self._totals: dict[str, Any] = {
            "requests": 0,
            "successes": 0,
            "failures": 0,
            "blocked": 0,
            "by_tier": {tier: 0 for tier in TIERS},
        }

    # -- configuration -------------------------------------------------
    def update_config(self, config: FetchConfig) -> None:
        if config.proxy_url != self.config.proxy_url:
            self._proxy_client_url = None
        self.config = config

    def apply_values(self, values: dict[str, Any]) -> None:
        self.config.apply_values(values)
        if self.config.proxy_url != self._proxy_client_url:
            self._proxy_client_url = None

    def status(self) -> dict[str, Any]:
        active = [
            {
                "domain": state.domain,
                "stage": state.stage,
                "label": STAGE_LABELS.get(state.stage, "Seite wird geladen…"),
                "tier": state.active_tier,
                "attempt": state.active_attempt,
                "started_at": _now_iso(state.active_started_at),
            }
            for state in self._domains.values()
            if state.stage
        ]
        domains = sorted(
            (state for state in self._domains.values() if state.last_request_at),
            key=lambda item: item.last_request_at,
            reverse=True,
        )[:50]
        return {
            "config": {
                "proxy_configured": bool(self.config.proxy_url),
                "proxy_host": _redact_proxy(self.config.proxy_url),
                "proxy_for_images": self.config.proxy_for_images,
                "flaresolverr_configured": bool(self.config.flaresolverr_url),
                "flaresolverr_url": self.config.flaresolverr_url,
                "flaresolverr_timeout": self.config.flaresolverr_timeout,
                "max_retries": self.config.max_retries,
                "timeout": self.config.timeout,
                "min_interval": self.config.min_interval,
                "browser_impersonation": self.config.use_browser_impersonation,
            },
            "capabilities": {"curl_cffi": HAS_CURL_CFFI},
            "totals": dict(self._totals),
            "active": active,
            "domains": [
                {
                    "domain": state.domain,
                    "successes": state.successes,
                    "failures": state.failures,
                    "last_tier": state.last_tier,
                    "last_success_at": _now_iso(state.last_tier_at),
                    "circuit_open_until": _now_iso(
                        state.circuit_until if state.circuit_until > time.time() else None
                    ),
                    "rate_limited": state.circuit_until > time.time(),
                }
                for state in domains
            ],
        }

    # -- public API ----------------------------------------------------
    async def fetch(
        self,
        url: str,
        *,
        kind: str = "html",
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        allow_proxy: bool | None = None,
        allow_flare: bool | None = None,
        timeout: float | None = None,
    ) -> FetchResult:
        domain = urlsplit(url).netloc.lower()
        state = self._domains.setdefault(domain, _DomainState(domain=domain))
        use_proxy = self.config.proxy_url is not None if allow_proxy is None else allow_proxy
        use_proxy = bool(use_proxy and self.config.proxy_url)
        if kind == "image":
            use_proxy = use_proxy and self.config.proxy_for_images
        if allow_flare is None:
            allow_flare = kind == "html"
        use_flare = bool(allow_flare and self.config.flaresolverr_url and kind == "html")

        tiers = self._tier_order(state, use_proxy, use_flare)
        start = time.perf_counter()
        last_result: FetchResult | None = None
        last_error: Exception | None = None
        attempts = 0

        if kind != "image":
            await self._guard(domain, state)

        for tier in tiers:
            self._set_stage(state, tier, attempts + 1)
            try:
                if tier == TIER_DIRECT:
                    result, used = await self._direct(
                        url, kind, headers, params, timeout, state
                    )
                    attempts += used
                elif tier == TIER_PROXY:
                    self._set_stage(state, "proxy", attempts + 1)
                    result, used = await self._via_proxy(
                        url, kind, headers, params, timeout
                    )
                    attempts += used
                else:
                    self._set_stage(state, "flaresolverr", attempts + 1)
                    result = await self._via_flaresolverr(url, timeout)
                    attempts += 1
            except FetchError as exc:
                last_error = exc
                logger.info("Fetch %s über %s fehlgeschlagen: %s", url, tier, exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                logger.warning("Unerwarteter Fetch-Fehler (%s, %s): %s", url, tier, exc)
                continue

            last_result = result
            if result.ok:
                state.successes += 1
                state.failures = 0
                state.last_tier = tier
                state.last_tier_at = time.time()
                state.circuit_until = 0.0
                self._totals["successes"] += 1
                self._totals["by_tier"][tier] += 1
                self._clear_stage(state)
                return FetchResult(
                    url=str(result.url),
                    status=result.status,
                    text=result.text,
                    content=result.content,
                    headers=result.headers,
                    tier=tier,
                    attempts=attempts,
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                )
            if result.status == 404:
                self._clear_stage(state)
                return FetchResult(
                    url=str(result.url),
                    status=404,
                    text=result.text,
                    content=result.content,
                    headers=result.headers,
                    tier=tier,
                    attempts=attempts,
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                )
            if not looks_blocked(result.status, result.text):
                self._clear_stage(state)
                return FetchResult(
                    url=str(result.url),
                    status=result.status,
                    text=result.text,
                    content=result.content,
                    headers=result.headers,
                    tier=tier,
                    attempts=attempts,
                    elapsed_ms=int((time.perf_counter() - start) * 1000),
                )
            logger.info(
                "Fetch %s wurde über %s blockiert (HTTP %s)", url, tier, result.status
            )

        self._clear_stage(state)
        state.failures += 1
        state.last_request_at = time.time()
        self._totals["failures"] += 1
        if state.failures >= self.config.circuit_threshold:
            cooldown = min(
                self.config.circuit_cooldown * (2 ** (state.failures - self.config.circuit_threshold)),
                900.0,
            )
            state.circuit_until = time.time() + cooldown
            self._totals["blocked"] += 1
            logger.warning(
                "Circuit Breaker für %s aktiv: %ss Pause nach %s Fehlschlägen",
                domain,
                int(cooldown),
                state.failures,
            )

        if last_result is not None:
            last_result.blocked = True
            last_result.attempts = attempts
            last_result.elapsed_ms = int((time.perf_counter() - start) * 1000)
            last_result.tier = last_result.tier or tiers[-1]
            return last_result

        message = "Die Seite konnte nicht geladen werden."
        if self.config.flaresolverr_url and not use_flare:
            message += " FlareSolverr ist konfiguriert, wird für diesen Inhalt aber nicht genutzt."
        elif not self.config.flaresolverr_url and not use_proxy:
            message += (
                " Die Seite blockiert vermutlich automatisierte Zugriffe – "
                "ein Proxy oder FlareSolverr in den Einstellungen kann helfen."
            )
        raise FetchFailed(message) from last_error

    async def test_connection(
        self, target: str, url: str | None = None
    ) -> dict[str, Any]:
        """Test direct access, the proxy or FlareSolverr from the settings UI."""
        started = time.perf_counter()
        probe = url or "https://api.chefkoch.de/v2/recipes?query=lasagne&limit=1"
        if target == "proxy":
            if not self.config.proxy_url:
                return {"ok": False, "target": target, "detail": "Kein Proxy konfiguriert."}
            try:
                response = await self._request_proxy(probe, "json", {}, None, None)
            except Exception as exc:
                return {
                    "ok": False,
                    "target": target,
                    "detail": f"Proxy-Test fehlgeschlagen: {exc}",
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                }
            return {
                "ok": response.status < 400,
                "target": target,
                "status": response.status,
                "detail": (
                    "Proxy antwortet."
                    if response.status < 400
                    else f"Proxy antwortet mit HTTP {response.status}."
                ),
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }
        if target == "flaresolverr":
            if not self.config.flaresolverr_url:
                return {
                    "ok": False,
                    "target": target,
                    "detail": "FlareSolverr ist nicht konfiguriert.",
                }
            try:
                result = await self._via_flaresolverr(probe, None)
            except Exception as exc:
                return {
                    "ok": False,
                    "target": target,
                    "detail": f"FlareSolverr-Test fehlgeschlagen: {exc}",
                    "elapsed_ms": int((time.perf_counter() - started) * 1000),
                }
            return {
                "ok": result.status < 400,
                "target": target,
                "status": result.status,
                "tier": result.tier,
                "detail": "FlareSolverr liefert Inhalte."
                if result.status < 400
                else f"FlareSolverr antwortet mit HTTP {result.status}.",
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }
        try:
            response = await self._request_direct(probe, "json", {}, None, None, PROFILES[0])
        except Exception as exc:
            return {
                "ok": False,
                "target": "direct",
                "detail": f"Direkter Abruf fehlgeschlagen: {exc}",
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }
        return {
            "ok": response.status < 400,
            "target": "direct",
            "status": response.status,
            "tier": TIER_DIRECT,
            "detail": "Direkter Abruf funktioniert."
            if response.status < 400
            else f"Direkter Abruf antwortet mit HTTP {response.status}.",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }

    async def close(self) -> None:
        if self._proxy_client is not None:
            await self._proxy_client.aclose()
            self._proxy_client = None
        for session in self._curl_sessions.values():  # pragma: no cover - optional
            try:
                await session.close()
            except Exception:
                pass
        self._curl_sessions.clear()

    # -- internals -----------------------------------------------------
    def _tier_order(
        self, state: _DomainState, use_proxy: bool, use_flare: bool
    ) -> list[str]:
        available = [TIER_DIRECT]
        if use_proxy:
            available.append(TIER_PROXY)
        if use_flare:
            available.append(TIER_FLARESOLVERR)

        # Remember what worked recently, but never skip the cheapest option
        # forever: the memory is intentionally short-lived.
        if state.last_tier in available and time.time() - state.last_tier_at < 600:
            remembered = state.last_tier
            if remembered == TIER_FLARESOLVERR:
                return [TIER_FLARESOLVERR]
            if remembered == TIER_PROXY:
                return [TIER_PROXY, TIER_FLARESOLVERR] if TIER_FLARESOLVERR in available else [TIER_PROXY]
        return available

    async def _guard(self, domain: str, state: _DomainState) -> None:
        if state.circuit_until and state.circuit_until > time.time():
            remaining = int(state.circuit_until - time.time())
            raise FetchBlocked(
                f"{domain} wird gerade pausiert. Bitte in {remaining} Sekunden erneut versuchen."
            )
        if self.config.min_interval > 0:
            wait = self.config.min_interval - (time.time() - state.last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
        state.last_request_at = time.time()

    def _set_stage(self, state: _DomainState, stage: str, attempt: int) -> None:
        state.stage = stage
        state.active_tier = stage
        state.active_attempt = attempt
        state.active_started_at = time.time()

    @staticmethod
    def _clear_stage(state: _DomainState) -> None:
        state.stage = ""
        state.active_tier = ""
        state.active_attempt = 0
        state.active_started_at = 0.0

    @staticmethod
    def _accept_for(kind: str) -> str:
        if kind == "image":
            return IMAGE_ACCEPT
        if kind == "json":
            return JSON_ACCEPT
        return HTML_ACCEPT

    async def _direct(
        self,
        url: str,
        kind: str,
        headers: dict[str, str] | None,
        params: dict[str, Any] | None,
        timeout: float | None,
        state: _DomainState,
    ) -> tuple[FetchResult, int]:
        attempts = 0
        last: FetchResult | None = None
        retries = max(1, self.config.max_retries)
        offset = random.randrange(len(PROFILES))
        for attempt in range(retries):
            attempts += 1
            profile = PROFILES[(offset + attempt) % len(PROFILES)]
            state.stage = "direct" if attempt == 0 else "retry"
            state.active_attempt = attempts
            try:
                result = await self._request_direct(
                    url, kind, headers or {}, params, timeout, profile
                )
            except FetchError:
                if attempt == retries - 1:
                    raise
                await self._sleep_backoff(attempt)
                continue
            last = result
            if result.ok or not looks_blocked(result.status, result.text):
                return result, attempts
            if attempt < retries - 1:
                delay = self._retry_delay(result.headers.get("retry-after"), attempt)
                await asyncio.sleep(delay)
        assert last is not None
        return last, attempts

    async def _request_direct(
        self,
        url: str,
        kind: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        timeout: float | None,
        profile: BrowserProfile,
    ) -> FetchResult:
        merged = profile.headers(self._accept_for(kind))
        merged.update(headers)
        effective_timeout = timeout or self.config.timeout
        if (
            self.config.use_browser_impersonation
            and HAS_CURL_CFFI
            and kind != "image"
        ):  # pragma: no cover - optional dependency
            try:
                session = self._curl_session(profile)
                response = await session.get(
                    url,
                    headers=merged,
                    params=params,
                    timeout=effective_timeout,
                )
                content = response.content or b""
                text = content.decode(response.encoding or "utf-8", errors="replace")
                return FetchResult(
                    url=str(response.url),
                    status=int(response.status_code),
                    text=text,
                    content=content,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    tier=TIER_DIRECT,
                    attempts=1,
                    elapsed_ms=0,
                )
            except Exception as exc:
                logger.debug("curl_cffi fehlgeschlagen, fallback auf httpx: %s", exc)
        try:
            response = await self.client.get(
                url,
                headers=merged,
                params=params,
                timeout=httpx.Timeout(effective_timeout),
            )
        except httpx.HTTPError as exc:
            raise FetchFailed("Die Seite konnte nicht erreicht werden.") from exc
        content = response.content
        return FetchResult(
            url=str(response.url),
            status=response.status_code,
            text=response.text,
            content=content,
            headers={key.lower(): value for key, value in response.headers.items()},
            tier=TIER_DIRECT,
            attempts=1,
            elapsed_ms=0,
        )

    async def _via_proxy(
        self,
        url: str,
        kind: str,
        headers: dict[str, str] | None,
        params: dict[str, Any] | None,
        timeout: float | None,
    ) -> tuple[FetchResult, int]:
        response = await self._request_proxy(url, kind, headers or {}, params, timeout)
        return response, 1

    async def _request_proxy(
        self,
        url: str,
        kind: str,
        headers: dict[str, str],
        params: dict[str, Any] | None,
        timeout: float | None,
    ) -> FetchResult:
        client = self._get_proxy_client()
        profile = PROFILES[random.randrange(len(PROFILES))]
        merged = profile.headers(self._accept_for(kind))
        merged.update(headers)
        try:
            response = await client.get(
                url,
                headers=merged,
                params=params,
                timeout=httpx.Timeout(timeout or self.config.timeout),
            )
        except httpx.HTTPError as exc:
            raise FetchFailed("Der Proxy konnte die Seite nicht laden.") from exc
        return FetchResult(
            url=str(response.url),
            status=response.status_code,
            text=response.text,
            content=response.content,
            headers={key.lower(): value for key, value in response.headers.items()},
            tier=TIER_PROXY,
            attempts=1,
            elapsed_ms=0,
            blocked=looks_blocked(response.status_code, response.text),
        )

    def _get_proxy_client(self) -> httpx.AsyncClient:
        if (
            self._proxy_client is None
            or self._proxy_client_url != self.config.proxy_url
            or self._proxy_client.is_closed
        ):
            self._proxy_client = httpx.AsyncClient(
                proxy=self.config.proxy_url,
                timeout=httpx.Timeout(self.config.timeout),
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
            self._proxy_client_url = self.config.proxy_url
        return self._proxy_client

    async def _via_flaresolverr(
        self, url: str, timeout: float | None
    ) -> FetchResult:
        if not self.config.flaresolverr_url:
            raise FetchFailed("FlareSolverr ist nicht konfiguriert.")
        domain = urlsplit(url).netloc.lower()
        state = self._domains.setdefault(domain, _DomainState(domain=domain))
        session_id = state.flare_session or (
            "kb-" + hashlib.sha256(domain.encode()).hexdigest()[:12]
        )
        if state.flare_session is None:
            await self._flare_command(
                {"cmd": "sessions.create", "session": session_id},
                ignore_errors=True,
            )
            state.flare_session = session_id

        payload = {
            "cmd": "request.get",
            "url": url,
            "session": session_id,
            "maxTimeout": int(min(240, (timeout or self.config.flaresolverr_timeout)) * 1000),
        }
        data = await self._flare_command(payload)
        solution = data.get("solution") or {}
        body = solution.get("response") or ""
        status = int(solution.get("status") or 200)
        headers = {
            str(key).lower(): str(value)
            for key, value in (solution.get("headers") or {}).items()
        }
        if headers and "content-type" not in headers:
            headers["content-type"] = "text/html; charset=utf-8"
        return FetchResult(
            url=solution.get("url") or url,
            status=status,
            text=body,
            content=body.encode("utf-8"),
            headers=headers,
            tier=TIER_FLARESOLVERR,
            attempts=1,
            elapsed_ms=0,
            blocked=looks_blocked(status, body),
        )

    async def _flare_command(
        self, payload: dict[str, Any], *, ignore_errors: bool = False
    ) -> dict[str, Any]:
        base = (self.config.flaresolverr_url or "").rstrip("/")
        endpoint = base if base.endswith("/v1") else f"{base}/v1"
        try:
            response = await self.client.post(
                endpoint,
                json=payload,
                timeout=httpx.Timeout(self.config.flaresolverr_timeout),
            )
        except httpx.HTTPError as exc:
            raise FetchFailed("FlareSolverr ist nicht erreichbar.") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise FetchFailed("FlareSolverr lieferte eine ungültige Antwort.") from exc
        if data.get("status") != "ok" and not ignore_errors:
            message = str(data.get("message") or "FlareSolverr konnte die Seite nicht laden.")
            raise FetchFailed(message[:300])
        return data

    def _curl_session(self, profile: BrowserProfile) -> Any:  # pragma: no cover
        session = self._curl_sessions.get(profile.name)
        if session is None:
            session = CurlAsyncSession(impersonate=profile.impersonate)
            self._curl_sessions[profile.name] = session
        return session

    @staticmethod
    def _retry_delay(retry_after: str | None, attempt: int) -> float:
        parsed = _retry_after_seconds(retry_after)
        if parsed is not None:
            return min(parsed, 10.0)
        return min(2.0**attempt + random.uniform(0, 0.6), 6.0)

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        await asyncio.sleep(min(0.8 * (attempt + 1) + random.uniform(0, 0.4), 4.0))


def fetch_stage_label(stage: str) -> str:
    return STAGE_LABELS.get(stage, "Seite wird geladen…")


def quote_url(url: str) -> str:
    """Small helper used in log messages and error hints."""
    return quote(url, safe=":/?&=%#")
