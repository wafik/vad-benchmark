"""POST /api/run must fail synchronously (no background task scheduled) when
required model files or the whisper-cli binary are missing — see
_readiness_issues in api.py."""
from __future__ import annotations

import base64
import sys

from fastapi.testclient import TestClient

from vad_bench import api
from vad_bench.api import create_app
from vad_bench.config import Settings

TEST_PASSWORD = "test-pass-xyz"
AUTH = {
    "Authorization": "Basic "
    + base64.b64encode(f"anyone:{TEST_PASSWORD}".encode()).decode()
}


def _patch_common(tmp_path, monkeypatch, settings):
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(api, "MODELS_ROOT", tmp_path)
    monkeypatch.setattr(api, "RUN_STATUS_PATH", tmp_path / ".run_status.json")


def test_run_not_ready_when_models_missing(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD, whisper_cli_cmd="nonexistent-binary-xyz")
    _patch_common(tmp_path, monkeypatch, settings)
    client = TestClient(create_app())

    r = client.post("/api/run", headers=AUTH)

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["not_ready"] is True
    assert body["issues"]  # missing whisper model, VAD model, and binary
    assert not (tmp_path / ".run_status.json").exists()


def test_run_started_when_models_and_binary_present(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD, whisper_cli_cmd=sys.executable)
    (tmp_path / settings.whisper_model).write_bytes(b"stub")
    (tmp_path / settings.vad_model_path).write_bytes(b"stub")
    _patch_common(tmp_path, monkeypatch, settings)
    monkeypatch.setattr(api, "run_benchmark", lambda *a, **k: None)  # skip real transcribe
    client = TestClient(create_app())

    r = client.post("/api/run", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == {"ok": True, "started": True}
