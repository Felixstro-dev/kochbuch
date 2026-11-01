from __future__ import annotations

import asyncio

import httpx
import respx
from fastapi.testclient import TestClient

from app.services.update_check import UpdateChecker


def test_update_status_requires_admin(client: TestClient) -> None:
    assert client.get("/api/v1/system/update-status").status_code in {401, 403}
    assert client.post("/api/v1/system/update-check").status_code in {401, 403}


def test_update_status_reports_disabled_without_git_sha(client: TestClient, admin: dict) -> None:
    response = client.get(
        "/api/v1/system/update-status", headers={"X-CSRF-Token": admin["csrf"]}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    # Im Test-Mode läuft kein Hintergrund-Check und GIT_SHA ist unbekannt.
    assert data["enabled"] is False
    assert data["update_available"] is False
    assert data["current_sha"] is None


@respx.mock
def test_admin_can_trigger_update_check(client: TestClient, admin: dict, app) -> None:
    # Einen Checker mit bekannter GIT_SHA wie im Docker-Image hinterlegen.
    from app.services.update_check import UpdateChecker

    app.state.update_checker = UpdateChecker(
        "ghcr.io/example/app", "1234567890abcdef", 3600
    )
    respx.get("https://ghcr.io/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get("https://ghcr.io/v2/example/app/manifests/latest").mock(
        return_value=httpx.Response(
            200, headers={"docker-content-digest": "sha256:neu"}, json={}
        )
    )
    respx.get("https://ghcr.io/v2/example/app/manifests/sha-1234567").mock(
        return_value=httpx.Response(
            200, headers={"docker-content-digest": "sha256:alt"}, json={}
        )
    )

    csrf = {"X-CSRF-Token": admin["csrf"]}
    response = client.post("/api/v1/system/update-check", headers=csrf)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["enabled"] is True
    assert data["update_available"] is True
    assert data["current_short"] == "1234567"
    assert data["dokploy_url"] == ""

    # GET liefert denselben Zustand ohne erneuten Netzwerkzugriff
    status = client.get("/api/v1/system/update-status", headers=csrf)
    assert status.status_code == 200
    assert status.json()["update_available"] is True


@respx.mock
def test_checker_detects_newer_latest_digest() -> None:
    respx.get("https://ghcr.io/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get("https://ghcr.io/v2/example/app/manifests/latest").mock(
        return_value=httpx.Response(
            200, headers={"docker-content-digest": "sha256:neu"}, json={}
        )
    )
    respx.get("https://ghcr.io/v2/example/app/manifests/sha-1234567").mock(
        return_value=httpx.Response(
            200, headers={"docker-content-digest": "sha256:alt"}, json={}
        )
    )

    checker = UpdateChecker("ghcr.io/example/app", "1234567890abcdef", 3600)
    assert checker.enabled
    state = asyncio.run(checker.check())
    assert state["update_available"] is True
    assert state["latest_digest"] == "sha256:neu"
    assert state["last_error"] is None
    assert state["checked_at"] is not None


@respx.mock
def test_checker_up_to_date_when_digests_match() -> None:
    respx.get("https://ghcr.io/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    respx.get("https://ghcr.io/v2/example/app/manifests/latest").mock(
        return_value=httpx.Response(
            200, headers={"docker-content-digest": "sha256:same"}, json={}
        )
    )
    respx.get("https://ghcr.io/v2/example/app/manifests/sha-1234567").mock(
        return_value=httpx.Response(
            200, headers={"docker-content-digest": "sha256:same"}, json={}
        )
    )

    checker = UpdateChecker("ghcr.io/example/app", "1234567890abcdef", 3600)
    state = asyncio.run(checker.check())
    assert state["update_available"] is False
    assert state["last_error"] is None


@respx.mock
def test_checker_survives_registry_errors() -> None:
    respx.get("https://ghcr.io/token").mock(return_value=httpx.Response(500))

    checker = UpdateChecker("ghcr.io/example/app", "1234567890abcdef", 3600)
    state = asyncio.run(checker.check())
    assert state["update_available"] is False
    assert state["last_error"] is not None
    assert state["checked_at"] is not None
