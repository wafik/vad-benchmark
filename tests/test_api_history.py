import base64
import json

from fastapi.testclient import TestClient

from vad_bench import api
from vad_bench.api import create_app
from vad_bench.config import Settings


PASSWORD = "test-history-password"
AUTH = {
    "Authorization": "Basic " + base64.b64encode(f"user:{PASSWORD}".encode()).decode(),
}


def _client_with_history(tmp_path, monkeypatch, runs):
    (tmp_path / "index.json").write_text(json.dumps(runs), encoding="utf-8")
    monkeypatch.setattr(api, "HISTORY_ROOT", tmp_path)
    monkeypatch.setattr(api, "get_settings", lambda: Settings(auth_password=PASSWORD))
    return TestClient(create_app())


def test_history_returns_newest_page_and_metadata(tmp_path, monkeypatch):
    client = _client_with_history(tmp_path, monkeypatch, [{"id": "old"}, {"id": "new"}])

    response = client.get("/api/history?page=1&page_size=1", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {
        "runs": [{"id": "new"}],
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }


def test_history_returns_empty_page_with_metadata(tmp_path, monkeypatch):
    client = _client_with_history(tmp_path, monkeypatch, [{"id": "only"}])

    response = client.get("/api/history?page=9&page_size=20", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {
        "runs": [],
        "page": 9,
        "page_size": 20,
        "total": 1,
        "total_pages": 1,
    }


def test_history_rejects_nonpositive_page_inputs(tmp_path, monkeypatch):
    client = _client_with_history(tmp_path, monkeypatch, [])

    response = client.get("/api/history?page=0", headers=AUTH)

    assert response.status_code == 422
