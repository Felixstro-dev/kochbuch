from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_setup_required_and_admin_creation(client: TestClient) -> None:
    status = client.get("/api/v1/auth/status").json()
    assert status["setup_required"] is True
    assert status["authenticated"] is False

    response = client.post(
        "/api/v1/auth/setup",
        json={"username": "Admin", "password": "correct horse battery"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["username"] == "admin"
    assert body["csrf_token"]

    status = client.get("/api/v1/auth/status").json()
    assert status["setup_required"] is False
    assert status["authenticated"] is True

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    second = client.post(
        "/api/v1/auth/setup",
        json={"username": "other", "password": "correct horse battery"},
    )
    assert second.status_code == 409


def test_login_logout_and_csrf(client: TestClient, admin: dict) -> None:
    csrf = admin["csrf"]
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401

    wrong = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong password"}
    )
    assert wrong.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "correct horse battery"},
    )
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    assert client.get("/api/v1/auth/me").status_code == 200

    assert client.patch("/api/v1/settings", json={"app_name": "Neu"}).status_code == 403
    patched = client.patch(
        "/api/v1/settings",
        json={"app_name": "Neu"},
        headers={"X-CSRF-Token": csrf},
    )
    assert patched.status_code == 200
    assert patched.json()["app_name"] == "Neu"


def test_password_change_revokes_other_sessions(client: TestClient) -> None:
    setup = client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "correct horse battery"},
    )
    csrf = setup.json()["csrf_token"]

    second = TestClient(client.app)
    second.__enter__()
    try:
        login = second.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "correct horse battery"},
        )
        assert login.status_code == 200

        changed = client.post(
            "/api/v1/auth/password",
            json={
                "current_password": "correct horse battery",
                "new_password": "a new very secret phrase",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert changed.status_code == 204, changed.text
        assert second.get("/api/v1/auth/me").status_code == 401
        assert client.get("/api/v1/auth/me").status_code == 200
    finally:
        second.__exit__(None, None, None)
