from __future__ import annotations

from fastapi.testclient import TestClient


def test_fetch_settings_roundtrip(client: TestClient, admin: dict) -> None:
    csrf = admin["csrf"]
    headers = {"X-CSRF-Token": csrf}

    before = client.get("/api/v1/settings").json()
    assert before["fetch"]["proxy_configured"] is False
    assert before["fetch"]["flaresolverr_configured"] is False
    assert before["fetch"]["max_retries"] >= 1

    response = client.patch(
        "/api/v1/settings",
        json={
            "fetch": {
                "proxy_url": "socks5://user:secret@127.0.0.1:1080",
                "proxy_for_images": False,
                "flaresolverr_url": "http://flaresolverr:8191",
                "flaresolverr_timeout": 30,
                "max_retries": 2,
                "timeout": 20,
            }
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    fetch = response.json()["fetch"]
    assert fetch["proxy_configured"] is True
    assert fetch["proxy_host"] == "socks5://***@127.0.0.1:1080"
    assert "secret" not in response.text
    assert fetch["proxy_for_images"] is False
    assert fetch["flaresolverr_configured"] is True
    assert fetch["flaresolverr_timeout"] == 30
    assert fetch["max_retries"] == 2
    assert fetch["timeout"] == 20

    status = client.get("/api/v1/system/fetch-status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["proxy_configured"] is True
    assert payload["proxy_host"] == "socks5://***@127.0.0.1:1080"
    assert payload["flaresolverr_url"] == "http://flaresolverr:8191"
    assert "totals" in payload and "active" in payload and "domains" in payload

    cleared = client.patch(
        "/api/v1/settings",
        json={"fetch": {"proxy_url": ""}},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["fetch"]["proxy_configured"] is False


def test_fetch_settings_validation(client: TestClient, admin: dict) -> None:
    csrf = admin["csrf"]
    response = client.patch(
        "/api/v1/settings",
        json={"fetch": {"proxy_url": "ftp://example.com"}},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400

    response = client.patch(
        "/api/v1/settings",
        json={"fetch": {"max_retries": 99}},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422


def test_fetch_test_endpoint_without_proxy(client: TestClient, admin: dict) -> None:
    response = client.post(
        "/api/v1/system/fetch/test",
        json={"target": "proxy"},
        headers={"X-CSRF-Token": admin["csrf"]},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "Proxy" in payload["detail"]


def test_fetch_endpoints_require_admin(client: TestClient) -> None:
    assert client.get("/api/v1/system/fetch-status").status_code == 401
    assert client.post("/api/v1/system/fetch/test", json={"target": "direct"}).status_code == 401
