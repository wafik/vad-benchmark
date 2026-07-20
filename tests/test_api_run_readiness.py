"""POST /api/run must fail synchronously (no background task scheduled) when
required model files or the whisper-cli binary are missing — see
_readiness_issues in api.py."""
from __future__ import annotations

import base64
import json
import sys
from types import SimpleNamespace

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


def write_summary(tmp_path, summary):
    (tmp_path / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_summary_result_exposes_run_identity_mode_timings_and_status(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD)
    _patch_common(tmp_path, monkeypatch, settings)
    monkeypatch.setattr(api, "REPORTS_ROOT", tmp_path)
    write_summary(tmp_path, {
        "run_id": "run-1",
        "manifest_path": "reports/history/run-1.manifest.json",
        "reference_quality": "silver",
        "resources": {"gpu_memory_peak_mib": None},
        "configs": [{
            "vad_mode": "builtin",
            "total_s": 1.0,
            "segment_prep_s": 0.0,
            "staging_s": 0.1,
            "transcription_s": 0.9,
            "metric_status": "verified",
        }],
    })
    client = TestClient(create_app())

    body = client.get("/api/summary", headers=AUTH).json()

    assert body["run_id"] == "run-1"
    assert body["manifest_path"] == "reports/history/run-1.manifest.json"
    assert body["reference_quality"] == "silver"
    assert body["resources"]["gpu_memory_peak_mib"] is None
    assert body["configs"][0] == {
        "vad_mode": "builtin",
        "total_s": 1.0,
        "segment_prep_s": 0.0,
        "staging_s": 0.1,
        "transcription_s": 0.9,
        "metric_status": "verified",
    }


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


def test_run_forwards_explicit_pair_names(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD, whisper_cli_cmd=sys.executable)
    (tmp_path / settings.whisper_model).write_bytes(b"stub")
    (tmp_path / settings.vad_model_path).write_bytes(b"stub")
    _patch_common(tmp_path, monkeypatch, settings)
    calls = []
    monkeypatch.setattr(api, "run_benchmark", lambda *args, **kwargs: calls.append((args, kwargs)))
    client = TestClient(create_app())
    configs = [
        {"name": "off", "overrides": {"vad_mode": "off"}},
        {"name": "on", "overrides": {"vad_mode": "builtin"}},
    ]

    response = client.post(
        "/api/run",
        headers=AUTH,
        params={
            "configs": json.dumps(configs),
            "control_name": "off",
            "candidate_name": "on",
        },
    )

    assert response.json() == {"ok": True, "started": True}
    assert calls == [((configs,), {
        "verbose": True,
        "control_name": "off",
        "candidate_name": "on",
    })]


def test_run_rejects_incomplete_explicit_pair(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD, whisper_cli_cmd=sys.executable)
    _patch_common(tmp_path, monkeypatch, settings)
    client = TestClient(create_app())

    response = client.post(
        "/api/run",
        headers=AUTH,
        params={"control_name": "off"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "control_name and candidate_name must be supplied together"


def test_presegmented_mode_requires_segment_binary(tmp_path, monkeypatch):
    whisper_cli = tmp_path / "whisper-cli"
    whisper_cli.write_bytes(b"stub")
    settings = Settings(
        whisper_cli_cmd=str(whisper_cli),
        vad_mode="presegmented",
    )
    (tmp_path / settings.whisper_model).write_bytes(b"stub")
    (tmp_path / settings.vad_model_path).write_bytes(b"stub")
    monkeypatch.setattr(api, "MODELS_ROOT", tmp_path)

    issues = api._readiness_issues(
        [{"name": "segments", "overrides": {"vad_mode": "presegmented"}}],
        settings,
    )

    assert issues == [
        f"segments: VAD segmenter not found: {tmp_path / 'whisper-vad-speech-segments'}"
    ]


def test_presegmented_ssh_readiness_checks_remote_segmenter(tmp_path, monkeypatch):
    settings = Settings(
        whisper_cli_cmd="ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'",
        vad_mode="presegmented",
    )
    (tmp_path / settings.whisper_model).write_bytes(b"stub")
    (tmp_path / settings.vad_model_path).write_bytes(b"stub")
    monkeypatch.setattr(api, "MODELS_ROOT", tmp_path)
    monkeypatch.setattr(api.shutil, "which", lambda _: "/usr/bin/ssh")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=1, stderr="command not found")

    monkeypatch.setattr(api, "subprocess", SimpleNamespace(run=fake_run), raising=False)
    issues = api._readiness_issues(
        [{"name": "segments", "overrides": {"vad_mode": "presegmented"}}],
        settings,
    )

    assert calls == [(
        "ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-vad-speech-segments' --help",
        {"capture_output": True, "text": True, "timeout": 15, "shell": True},
    )]
    assert issues == [
        "segments: remote VAD segmenter not ready: "
        "ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-vad-speech-segments'"
    ]


def test_rms_energy_mode_needs_no_silero_model_or_segmenter_binary(tmp_path, monkeypatch):
    # rms_energy is pure Python: no Silero .bin, no external segmenter
    # binary — only the whisper model and whisper-cli itself are required.
    whisper_cli = tmp_path / "whisper-cli"
    whisper_cli.write_bytes(b"stub")
    settings = Settings(
        whisper_cli_cmd=str(whisper_cli),
        vad_mode="rms_energy",
    )
    (tmp_path / settings.whisper_model).write_bytes(b"stub")
    monkeypatch.setattr(api, "MODELS_ROOT", tmp_path)

    issues = api._readiness_issues(
        [{"name": "rms", "overrides": {"vad_mode": "rms_energy"}}],
        settings,
    )

    assert issues == []


def test_run_rejects_legacy_vad_enabled_override(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD, whisper_cli_cmd=sys.executable)
    _patch_common(tmp_path, monkeypatch, settings)
    client = TestClient(create_app())

    r = client.post(
        "/api/run",
        headers=AUTH,
        params={
            "configs": '[{"name": "legacy", "overrides": {"vad_enabled": false}}]',
        },
    )

    assert r.status_code == 400
    assert r.json()["detail"] == "vad_enabled has been replaced by vad_mode"


def test_run_rejects_invalid_vad_mode(tmp_path, monkeypatch):
    settings = Settings(auth_password=TEST_PASSWORD, whisper_cli_cmd=sys.executable)
    _patch_common(tmp_path, monkeypatch, settings)
    client = TestClient(create_app())

    r = client.post(
        "/api/run",
        headers=AUTH,
        params={
            "configs": '[{"name": "invalid", "overrides": {"vad_mode": "fallback"}}]',
        },
    )

    assert r.status_code == 400
    assert "Input should be 'off', 'builtin', 'presegmented' or 'rms_energy'" in r.json()["detail"]
