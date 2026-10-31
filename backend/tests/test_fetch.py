from __future__ import annotations

import asyncio

import httpx
import pytest
import respx

from app.core.config import Settings
from app.core.fetch import (
    FetchBlocked,
    FetchConfig,
    FetchPipeline,
    looks_blocked,
)

BLOCK_HTML = "<html><title>Just a moment...</title><body>Checking your browser</body></html>"
RECIPE_HTML = "<html><body><h1>Rezept</h1></body></html>"


def _settings() -> Settings:
    return Settings(_env_file=None, testing=True, provider_timeout_seconds=5)


def test_looks_blocked_detects_status_and_markers() -> None:
    assert looks_blocked(403, "")
    assert looks_blocked(429, "")
    assert looks_blocked(200, BLOCK_HTML)
    assert not looks_blocked(200, RECIPE_HTML)
    assert not looks_blocked(404, "")


def test_direct_fetch_succeeds() -> None:
    settings = _settings()
    config = FetchConfig(max_retries=1, min_interval=0, timeout=5)

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            pipeline = FetchPipeline(settings, client, config)
            with respx.mock:
                route = respx.get("https://example.com/rezept").mock(
                    return_value=httpx.Response(
                        200, text=RECIPE_HTML, headers={"content-type": "text/html"}
                    )
                )
                result = await pipeline.fetch("https://example.com/rezept")
                assert route.called
                assert result.ok
                assert result.tier == "direct"
                assert result.text == RECIPE_HTML
                status = pipeline.status()
                assert status["totals"]["successes"] == 1
                assert status["domains"][0]["successes"] == 1
                assert status["active"] == []
            await pipeline.close()

    asyncio.run(run())


def test_direct_block_escalates_to_flaresolverr() -> None:
    settings = _settings()
    config = FetchConfig(
        flaresolverr_url="http://flaresolverr:8191",
        flaresolverr_timeout=10,
        max_retries=1,
        min_interval=0,
        timeout=5,
    )

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            pipeline = FetchPipeline(settings, client, config)
            with respx.mock:
                respx.get("https://protected.example/rezept").mock(
                    return_value=httpx.Response(
                        403, text=BLOCK_HTML, headers={"content-type": "text/html"}
                    )
                )
                def flare(request: httpx.Request) -> httpx.Response:
                    payload = __import__("json").loads(request.content)
                    if payload.get("cmd") == "sessions.create":
                        return httpx.Response(200, json={"status": "ok", "session": "kb-test"})
                    return httpx.Response(
                        200,
                        json={
                            "status": "ok",
                            "solution": {
                                "url": "https://protected.example/rezept",
                                "status": 200,
                                "response": RECIPE_HTML,
                                "headers": {"content-type": "text/html"},
                            },
                        },
                    )

                respx.post("http://flaresolverr:8191/v1").mock(side_effect=flare)
                result = await pipeline.fetch("https://protected.example/rezept")
                assert result.ok
                assert result.tier == "flaresolverr"
                assert result.text == RECIPE_HTML

                # The successful tier is remembered for this domain.
                respx.calls.clear()
                second = await pipeline.fetch("https://protected.example/rezept")
                assert second.tier == "flaresolverr"
                assert len(respx.calls) == 1
                assert respx.calls[0].request.method == "POST"
            assert pipeline.status()["config"]["flaresolverr_configured"] is True
            await pipeline.close()

    asyncio.run(run())


def test_circuit_breaker_pauses_domain() -> None:
    settings = _settings()
    config = FetchConfig(
        max_retries=1,
        min_interval=0,
        timeout=5,
        circuit_threshold=1,
        circuit_cooldown=120,
    )

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            pipeline = FetchPipeline(settings, client, config)
            with respx.mock:
                respx.get("https://blocked.example/rezept").mock(
                    return_value=httpx.Response(
                        403, text=BLOCK_HTML, headers={"content-type": "text/html"}
                    )
                )
                first = await pipeline.fetch("https://blocked.example/rezept")
                assert first.blocked
                domains = pipeline.status()["domains"]
                assert domains[0]["rate_limited"] is True
                with pytest.raises(FetchBlocked):
                    await pipeline.fetch("https://blocked.example/rezept")
            await pipeline.close()

    asyncio.run(run())


def test_proxy_tier_is_used_after_direct_block() -> None:
    settings = _settings()
    config = FetchConfig(
        proxy_url="http://proxy.local:8080",
        max_retries=1,
        min_interval=0,
        timeout=5,
    )

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            pipeline = FetchPipeline(settings, client, config)
            with respx.mock:
                respx.get("https://example.com/rezept").mock(
                    side_effect=[
                        httpx.Response(
                            403, text=BLOCK_HTML, headers={"content-type": "text/html"}
                        ),
                        httpx.Response(
                            200, text=RECIPE_HTML, headers={"content-type": "text/html"}
                        ),
                    ]
                )
                result = await pipeline.fetch("https://example.com/rezept")
                assert result.ok
                status = pipeline.status()
                assert status["config"]["proxy_configured"] is True
                assert status["config"]["proxy_host"] == "http://proxy.local:8080"
            await pipeline.close()

    asyncio.run(run(), debug=False)
