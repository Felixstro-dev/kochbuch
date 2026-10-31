from __future__ import annotations

from fastapi.testclient import TestClient


def test_wishes_require_auth_without_public_embed(client: TestClient) -> None:
    assert client.get("/api/v1/wishes").status_code == 401
    assert client.post("/api/v1/wishes", json={"text": "Zwetschgenknödel"}).status_code == 401


def test_wish_lifecycle_as_admin(client: TestClient, admin: dict) -> None:
    csrf = {"X-CSRF-Token": admin["csrf"]}

    created = client.post(
        "/api/v1/wishes", json={"text": "  Zwetschgenknödel  ", "note": "aus dem Garten"}, headers=csrf
    )
    assert created.status_code == 201, created.text
    wish = created.json()
    assert wish["text"] == "Zwetschgenknödel"
    assert wish["note"] == "aus dem Garten"
    assert wish["status"] == "open"
    assert wish["done_at"] is None

    listed = client.get("/api/v1/wishes")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [wish["id"]]

    # Als erledigt markieren
    done = client.patch(
        f"/api/v1/wishes/{wish['id']}", json={"status": "done"}, headers=csrf
    )
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["done_at"] is not None

    # Filter
    assert client.get("/api/v1/wishes?status=open").json() == []
    assert len(client.get("/api/v1/wishes?status=done").json()) == 1

    # Wieder öffnen
    reopened = client.patch(
        f"/api/v1/wishes/{wish['id']}", json={"status": "open"}, headers=csrf
    )
    assert reopened.json()["status"] == "open"
    assert reopened.json()["done_at"] is None

    # Löschen
    deleted = client.delete(f"/api/v1/wishes/{wish['id']}", headers=csrf)
    assert deleted.status_code == 204
    assert client.get("/api/v1/wishes").json() == []
    assert client.delete(f"/api/v1/wishes/{wish['id']}", headers=csrf).status_code == 404


def test_wish_validation(client: TestClient, admin: dict) -> None:
    csrf = {"X-CSRF-Token": admin["csrf"]}
    assert client.post("/api/v1/wishes", json={"text": "   "}, headers=csrf).status_code == 400
    assert client.post("/api/v1/wishes", json={"text": "x" * 301}, headers=csrf).status_code == 422
    assert (
        client.post("/api/v1/wishes", json={"text": "oki", "status": "done"}, headers=csrf).status_code
        == 422
    )
    # CSRF-Pflicht für Session-Schreibzugriffe
    assert client.post("/api/v1/wishes", json={"text": "ohne csrf"}).status_code == 403


def test_wishes_anonymous_when_public_embed(app) -> None:
    from fastapi.testclient import TestClient

    app.state.settings.embed_public = True
    try:
        with TestClient(app) as anon:  # frischer Client ohne Session-Cookie
            created = anon.post("/api/v1/wishes", json={"text": "Apfelstrudel"})
            assert created.status_code == 201, created.text
            wish = created.json()

            assert anon.get("/api/v1/wishes").status_code == 200

            # Anonyme Besucher dürfen Status umschalten und löschen (ohne CSRF)
            toggled = anon.patch(f"/api/v1/wishes/{wish['id']}", json={"status": "done"})
            assert toggled.status_code == 200
            assert toggled.json()["status"] == "done"
            assert anon.delete(f"/api/v1/wishes/{wish['id']}").status_code == 204
    finally:
        app.state.settings.embed_public = False


def test_read_only_api_key_cannot_write_wishes(client: TestClient, admin: dict) -> None:
    csrf = {"X-CSRF-Token": admin["csrf"]}
    created = client.post(
        "/api/v1/api-keys", json={"name": "leser", "scopes": ["read"]}, headers=csrf
    )
    assert created.status_code == 201, created.text
    key = created.json()["secret"]

    assert client.get("/api/v1/wishes", headers={"X-API-Key": key}).status_code == 200
    denied = client.post(
        "/api/v1/wishes", json={"text": "geht nicht"}, headers={"X-API-Key": key}
    )
    assert denied.status_code == 403
