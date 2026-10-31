from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        testing=True,
        auto_migrate=False,
        secret_key="test-secret-key",
        login_rate_limit=100,
        cookie_secure=False,
        embed_public=False,
    )
    return create_app(settings)


@pytest.fixture
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/auth/setup",
        json={
            "username": "admin",
            "password": "correct horse battery",
            "display_name": "Admin",
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    data["csrf"] = data["csrf_token"]
    return data
