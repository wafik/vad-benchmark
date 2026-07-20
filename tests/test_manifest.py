import hashlib
import json
from types import SimpleNamespace

import pytest

from vad_bench.config import Settings
from vad_bench.manifest import build_manifest, sha256_file, write_manifest


def test_sha256_file_is_content_stable(tmp_path):
    path = tmp_path / "input.bin"
    path.write_bytes(b"vad")

    assert sha256_file(path) == "651bfad0aa5b42c5a5b8dad76f49c4a122fe1d1658fc55cfdd1ea9923fe3fd9e"


def test_manifest_records_inputs_config_command_and_timings(tmp_path, monkeypatch):
    import vad_bench.manifest as manifest

    audio = tmp_path / "audio.wav"
    reference = tmp_path / "reference.txt"
    models = tmp_path / "models"
    audio.write_bytes(b"audio")
    reference.write_text("reference", encoding="utf-8")
    models.mkdir()
    (models / "whisper.bin").write_bytes(b"whisper")
    (models / "vad.bin").write_bytes(b"vad")
    monkeypatch.setattr(manifest, "PODCAST_WAV", audio)
    monkeypatch.setattr(manifest, "REFERENCE_TXT", reference)
    monkeypatch.setattr(manifest, "MODELS_ROOT", models)
    monkeypatch.setattr(manifest, "_git_identity", lambda: {"revision": None, "dirty": None, "error": "git unavailable"})
    monkeypatch.setattr(manifest, "_host_identity", lambda threads: {"configured_threads": threads})
    monkeypatch.setattr(manifest, "_tool_versions", lambda _: {"whisper_cli": None, "whisper_cli_error": "unavailable"})

    settings = Settings(vad_mode="builtin", whisper_model="whisper.bin", vad_model_path="vad.bin", threads=3)
    result = build_manifest(
        "run-1",
        "2026-07-13T00:00:00Z",
        [settings],
        [{
            "config": "candidate",
            "resolved_command": ["whisper-cli", "-m", "models/whisper.bin"],
            "total_s": 5.0,
            "segment_prep_s": 1.0,
            "staging_s": 0.5,
            "transcription_s": 3.5,
        }],
    )

    config = result["configs"][0]
    assert result["run_id"] == "run-1"
    assert result["reference_quality"] == "silver"
    assert config["vad_mode"] == "builtin"
    assert config["effective_config"]["threads"] == 3
    assert config["resolved_command"] == ["whisper-cli", "-m", "models/whisper.bin"]
    assert config["inputs"]["audio"]["sha256"] == sha256_file(audio)
    assert config["inputs"]["vad_model"]["sha256"] == sha256_file(models / "vad.bin")
    assert config["timing"]["total_s"] == 5.0


def test_write_manifest_refuses_to_overwrite_history(tmp_path, monkeypatch):
    import vad_bench.manifest as manifest

    monkeypatch.setattr(manifest, "HISTORY_ROOT", tmp_path / "history")
    path = write_manifest("run-1", {"run_id": "run-1"})

    with pytest.raises(FileExistsError):
        write_manifest("run-1", {"run_id": "changed"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"run_id": "run-1"}


def test_build_manifest_records_missing_or_unreadable_hashes_without_failing(tmp_path, monkeypatch):
    import vad_bench.manifest as manifest

    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"audio")
    monkeypatch.setattr(manifest, "PODCAST_WAV", audio)
    monkeypatch.setattr(manifest, "REFERENCE_TXT", tmp_path / "missing.txt")
    monkeypatch.setattr(manifest, "MODELS_ROOT", tmp_path / "models")
    real_sha256_file = manifest.sha256_file

    def hash_file(path):
        if path == audio:
            raise PermissionError("blocked")
        return real_sha256_file(path)

    monkeypatch.setattr(manifest, "sha256_file", hash_file)
    monkeypatch.setattr(manifest, "_git_identity", lambda: {})
    monkeypatch.setattr(manifest, "_host_identity", lambda _: {})
    monkeypatch.setattr(manifest, "_tool_versions", lambda _: {})

    result = build_manifest("run-1", "2026-07-13T00:00:00Z", [Settings()], [{}])

    assert result["configs"][0]["inputs"]["audio"] == {
        "path": str(audio),
        "sha256": None,
        "sha256_error": "PermissionError: blocked",
    }
    assert result["configs"][0]["inputs"]["reference"]["sha256"] is None
    assert "FileNotFoundError" in result["configs"][0]["inputs"]["reference"]["sha256_error"]


def test_write_manifest_recovers_from_an_invalid_partial_file(tmp_path, monkeypatch):
    import vad_bench.manifest as manifest

    monkeypatch.setattr(manifest, "HISTORY_ROOT", tmp_path / "history")
    partial = manifest.HISTORY_ROOT / "run-1.manifest.json"
    partial.parent.mkdir()
    partial.write_text('{"run_id":', encoding="utf-8")

    path = write_manifest("run-1", {"run_id": "run-1"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"run_id": "run-1"}


def test_git_metadata_failure_is_recorded_without_raising(monkeypatch):
    import vad_bench.manifest as manifest

    monkeypatch.setattr(manifest, "_run_optional", lambda _: (None, "git unavailable"))

    assert manifest._git_identity() == {
        "revision": None,
        "dirty": None,
        "error": "git unavailable; git unavailable",
    }


def test_runner_writes_and_links_an_actual_manifest(tmp_path, monkeypatch):
    import vad_bench.runner as runner
    import vad_bench.manifest as manifest

    run_id = "2026-07-13_00-00-00"
    manifest_path = tmp_path / "reports" / "history" / f"{run_id}.manifest.json"
    monkeypatch.setattr(runner, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(runner, "RUN_STATUS_PATH", tmp_path / "reports" / ".run_status.json")
    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path / "reports" / "history")
    monkeypatch.setattr(runner, "CHUNKS_ROOT", tmp_path / "chunks")
    monkeypatch.setattr(manifest, "HISTORY_ROOT", tmp_path / "reports" / "history")
    monkeypatch.setattr(manifest, "_git_identity", lambda: {})
    monkeypatch.setattr(manifest, "_host_identity", lambda _: {})
    monkeypatch.setattr(manifest, "_tool_versions", lambda _: {})
    monkeypatch.setattr(runner, "ensure_wav", lambda: tmp_path / "audio.wav")
    monkeypatch.setattr(runner, "wav_duration", lambda _: 10.0)
    monkeypatch.setattr(runner, "load_reference", lambda: ("halo", []))
    monkeypatch.setattr(runner, "write_reference_artifacts", lambda _: None)
    monkeypatch.setattr(runner, "slice_wav_segments", lambda *args: None)
    monkeypatch.setattr(runner, "build_verdict", lambda *_: None)
    monkeypatch.setattr(runner, "_now_iso", lambda: "2026-07-13T00:00:00Z")
    monkeypatch.setattr(runner, "_run_id", lambda _: run_id)
    monkeypatch.setattr(
        runner,
        "ResourceMonitor",
        lambda **_: SimpleNamespace(latest={}, start=lambda: None, stop=lambda: None, summary=lambda: {}),
    )
    monkeypatch.setattr(
        runner,
        "transcribe",
        lambda *args, **kwargs: (
            kwargs["on_output_ready"](),
            SimpleNamespace(
                config="candidate", vad_mode="builtin", vad_enabled=True, transcript="halo",
                staging_s=0.0, transcription_s=1.0, speech_seconds=None, silence_removed=None,
                segments=[], cmd=["whisper-cli"],
            ),
        )[1],
    )
    monkeypatch.setattr(runner.time, "perf_counter", iter([10.0, 11.0]).__next__)

    summary = runner.run([{"name": "candidate", "overrides": {"vad_mode": "builtin"}}], verbose=False)
    per_config = json.loads((tmp_path / "reports" / "per_config" / "candidate.json").read_text(encoding="utf-8"))
    history = json.loads((tmp_path / "reports" / "history" / "2026-07-13_00-00-00.json").read_text(encoding="utf-8"))

    assert summary["run_id"] == run_id
    assert summary["manifest_path"] == str(manifest_path)
    assert per_config["run_id"] == run_id
    assert per_config["manifest_path"] == str(manifest_path)
    assert history["run_id"] == run_id
    assert history["manifest_path"] == str(manifest_path)
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["run_id"] == run_id


def test_runner_uses_input_snapshot_taken_before_the_engine_runs(tmp_path, monkeypatch):
    import vad_bench.manifest as manifest
    import vad_bench.runner as runner

    audio = tmp_path / "audio.wav"
    reference = tmp_path / "reference.txt"
    models = tmp_path / "models"
    models.mkdir()
    audio.write_bytes(b"audio-before")
    reference.write_text("reference-before", encoding="utf-8")
    (models / "ggml-tiny.id.bin").write_bytes(b"whisper-before")
    (models / "ggml-silero-v6.2.0.bin").write_bytes(b"vad-before")
    monkeypatch.setattr(runner, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(runner, "RUN_STATUS_PATH", tmp_path / "reports" / ".run_status.json")
    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path / "reports" / "history")
    monkeypatch.setattr(runner, "CHUNKS_ROOT", tmp_path / "chunks")
    monkeypatch.setattr(runner, "REFERENCE_TXT", reference)
    monkeypatch.setattr(runner, "MODELS_ROOT", models)
    monkeypatch.setattr(manifest, "HISTORY_ROOT", tmp_path / "reports" / "history")
    monkeypatch.setattr(manifest, "REFERENCE_TXT", reference)
    monkeypatch.setattr(manifest, "MODELS_ROOT", models)
    monkeypatch.setattr(manifest, "_git_identity", lambda: {})
    monkeypatch.setattr(manifest, "_host_identity", lambda _: {})
    monkeypatch.setattr(manifest, "_tool_versions", lambda _: {})
    monkeypatch.setattr(runner, "ensure_wav", lambda: audio)
    monkeypatch.setattr(runner, "wav_duration", lambda _: 10.0)
    monkeypatch.setattr(runner, "load_reference", lambda: ("halo", []))
    monkeypatch.setattr(runner, "write_reference_artifacts", lambda _: None)
    monkeypatch.setattr(runner, "slice_wav_segments", lambda *args: None)
    monkeypatch.setattr(runner, "build_verdict", lambda *_: None)
    monkeypatch.setattr(runner, "_now_iso", lambda: "2026-07-13T00:00:00Z")
    monkeypatch.setattr(runner, "_run_id", lambda _: "run-1")
    monkeypatch.setattr(
        runner,
        "ResourceMonitor",
        lambda **_: SimpleNamespace(latest={}, start=lambda: None, stop=lambda: None, summary=lambda: {}),
    )

    def transcribe(*_args, **kwargs):
        kwargs["on_output_ready"]()
        audio.write_bytes(b"audio-after")
        reference.write_text("reference-after", encoding="utf-8")
        (models / "ggml-tiny.id.bin").write_bytes(b"whisper-after")
        (models / "ggml-silero-v6.2.0.bin").write_bytes(b"vad-after")
        return SimpleNamespace(
            config="candidate", vad_mode="builtin", vad_enabled=True, transcript="halo",
            staging_s=0.0, transcription_s=1.0, speech_seconds=None, silence_removed=None,
            segments=[], cmd=["whisper-cli"],
        )

    monkeypatch.setattr(runner, "transcribe", transcribe)
    monkeypatch.setattr(runner.time, "perf_counter", iter([10.0, 11.0]).__next__)

    runner.run([{"name": "candidate", "overrides": {"vad_mode": "builtin"}}], verbose=False)

    result = json.loads((tmp_path / "reports" / "history" / "run-1.manifest.json").read_text(encoding="utf-8"))
    inputs = result["configs"][0]["inputs"]
    assert inputs["audio"]["sha256"] == hashlib.sha256(b"audio-before").hexdigest()
    assert inputs["reference"]["sha256"] == hashlib.sha256(b"reference-before").hexdigest()
    assert inputs["whisper_model"]["sha256"] == hashlib.sha256(b"whisper-before").hexdigest()
    assert inputs["vad_model"]["sha256"] == hashlib.sha256(b"vad-before").hexdigest()
