from __future__ import annotations

from fastapi.testclient import TestClient


def test_recipes_api_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/search?q=lasagne").status_code == 401
    assert client.get("/api/v1/favorites").status_code == 401
    assert client.get("/api/v1/providers").status_code == 401
    assert client.get("/api/v1/images/chefkoch:1/card?exp=1&sig=x").status_code == 403


def test_empty_search_and_providers(client: TestClient, admin: dict) -> None:
    response = client.get("/api/v1/search?q=")
    assert response.status_code == 200
    assert response.json()["items"] == []

    providers = client.get("/api/v1/providers")
    assert providers.status_code == 200
    names = {item["name"] for item in providers.json()}
    assert names == {"chefkoch", "web", "local"}
    assert all(item["enabled"] for item in providers.json())


def test_settings_provider_validation(client: TestClient, admin: dict) -> None:
    csrf = admin["csrf"]
    response = client.patch(
        "/api/v1/settings",
        json={"enabled_providers": ["chefkoch", "unbekannt"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400

    response = client.patch(
        "/api/v1/settings",
        json={"enabled_providers": ["local"]},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["enabled_providers"] == ["local"]

    providers = client.get("/api/v1/providers").json()
    enabled = {item["name"] for item in providers if item["enabled"]}
    assert enabled == {"local"}


def test_embed_public_read_only(client: TestClient, admin: dict, app) -> None:
    app.state.settings.embed_public = True
    try:
        response = client.get("/api/v1/search?q=")
        assert response.status_code == 200
        assert client.post("/api/v1/recipes/resolve", json={"url": "https://example.com"}).status_code == 403
    finally:
        app.state.settings.embed_public = False
