from __future__ import annotations

from fastapi.testclient import TestClient


def _create_key(client: TestClient, csrf: str, scopes: list[str], name: str = "Test") -> dict:
    response = client.post(
        "/api/v1/api-keys",
        json={"name": name, "scopes": scopes},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_api_key_lifecycle(client: TestClient, admin: dict) -> None:
    created = _create_key(client, admin["csrf"], ["read", "write"])
    secret = created["secret"]
    assert secret.startswith("kb_")
    assert created["prefix"] == secret[:12]

    listed = client.get("/api/v1/api-keys")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "secret" not in listed.json()[0]

    anonymous = TestClient(client.app)
    anonymous.__enter__()
    try:
        headers = {"Authorization": f"Bearer {secret}"}
        me = anonymous.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["username"] == "admin"

        # API keys bypass CSRF, but need the write scope for mutations.
        created_key = anonymous.post(
            "/api/v1/api-keys",
            json={"name": "Zweiter", "scopes": ["read"]},
            headers=headers,
        )
        assert created_key.status_code == 201
    finally:
        anonymous.__exit__(None, None, None)

    revoked = client.delete(
        f"/api/v1/api-keys/{created['id']}", headers={"X-CSRF-Token": admin["csrf"]}
    )
    assert revoked.status_code == 204
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {secret}"}).status_code
        == 401
    )


def test_read_only_key_cannot_write(client: TestClient, admin: dict) -> None:
    created = _create_key(client, admin["csrf"], ["read"])
    with TestClient(client.app) as read_only:
        headers = {"X-API-Key": created["secret"]}
        assert read_only.get("/api/v1/settings", headers=headers).status_code == 200
        response = read_only.patch(
            "/api/v1/settings", json={"app_name": "Nope"}, headers=headers
        )
        assert response.status_code == 403


def test_admin_scope_required_for_admin_routes(client: TestClient, admin: dict) -> None:
    created = _create_key(client, admin["csrf"], ["read", "write"])
    with TestClient(client.app) as writer:
        response = writer.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {created['secret']}"}
        )
        assert response.status_code == 403


def test_member_management(client: TestClient, admin: dict) -> None:
    csrf = admin["csrf"]
    created = client.post(
        "/api/v1/users",
        json={
            "username": "mara",
            "display_name": "Mara",
            "password": "a good long password",
            "role": "member",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 201, created.text
    member_id = created.json()["id"]

    users = client.get("/api/v1/users")
    assert users.status_code == 200
    assert len(users.json()["items"]) == 2

    with TestClient(client.app) as member:
        login = member.post(
            "/api/v1/auth/login",
            json={"username": "mara", "password": "a good long password"},
        )
        assert login.status_code == 200
        assert member.get("/api/v1/users").status_code == 403

    deactivated = client.delete(
        f"/api/v1/users/{member_id}", headers={"X-CSRF-Token": csrf}
    )
    assert deactivated.status_code == 204

    with TestClient(client.app) as member:
        login = member.post(
            "/api/v1/auth/login",
            json={"username": "mara", "password": "a good long password"},
        )
        assert login.status_code == 401

    self_disable = client.delete(
        f"/api/v1/users/{admin['user']['id']}", headers={"X-CSRF-Token": csrf}
    )
    assert self_disable.status_code == 400
