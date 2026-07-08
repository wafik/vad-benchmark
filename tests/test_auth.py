"""HTTP Basic Auth gate — mirrors the sibling ocr-benchmark project.

Covers the four matrix entries the middleware enforces:

- GET / without auth → 401 + WWW-Authenticate header.
- GET / with wrong password → 401.
- GET / with correct Basic header → 200.
- GET /api/health without auth → 200 (allowlisted).

We monkeypatch ``get_settings()`` so the test exercises the real middleware
code path against a known password, without touching the real .env.
"""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from src.vad_bench import api
from src.vad_bench.api import create_app


TEST_PASSWORD = "test-pass-xyz"


class _FakeSettings:
    """Stand-in for the lru_cached Settings singleton with a fixed password."""

    def __init__(self) -> None:
        self.auth_password = TEST_PASSWORD


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "get_settings", lambda: _FakeSettings())
    app = create_app()
    return TestClient(app)


def _basic(user: str, pw: str) -> str:
    raw = f"{user}:{pw}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def test_root_without_auth_returns_401(client):
    r = client.get("/")
    assert r.status_code == 401
    # Browser-native dialog is triggered by this header.
    assert r.headers.get("www-authenticate", "").lower().startswith("basic")


def test_root_with_wrong_password_returns_401(client):
    r = client.get("/", headers={"Authorization": _basic("anyone", "WRONG")})
    assert r.status_code == 401


def test_root_with_correct_password_returns_200(client):
    r = client.get("/", headers={"Authorization": _basic("anyone", TEST_PASSWORD)})
    assert r.status_code == 200


def test_health_is_allowlisted(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "vad-benchmark"


if __name__ == "__main__":  # self-check
    print("auth tests: import OK")