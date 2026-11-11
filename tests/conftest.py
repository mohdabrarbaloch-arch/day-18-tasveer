"""Shared pytest fixtures: an isolated app with a throwaway database."""

import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a temp DB and storage dir BEFORE importing it, so the
# module-level engine binds to the test database.
_TMP = Path(tempfile.mkdtemp(prefix="tasveer-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_TMP / "generated")
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ENVIRONMENT"] = "test"
os.environ["RATE_LIMIT_GENERATE"] = "1000/minute"
os.environ["RATE_LIMIT_DEFAULT"] = "1000/minute"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_payload():
    return {
        "email": "tester@example.com",
        "display_name": "Test User",
        "password": "secret123",
    }


@pytest.fixture
def auth_headers(client, user_payload):
    """Register a fresh user and return bearer headers."""
    res = client.post("/api/auth/register", json=user_payload)
    if res.status_code == 409:
        res = client.post(
            "/api/auth/login",
            json={"email": user_payload["email"], "password": user_payload["password"]},
        )
    assert res.status_code in (200, 201), res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
