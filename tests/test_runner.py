import json
from types import SimpleNamespace

import pytest

from vad_bench.config import Settings
from vad_bench.engine import EngineResult
from vad_bench.reference import Segment
from vad_bench.runner import _record_from_metrics, _score, run


@pytest.fixture(autouse=True)
def _stub_manifest_io(tmp_path, monkeypatch):
    import vad_bench.runner as runner

    monkeypatch.setattr(runner, "build_manifest", lambda *args, **kwargs: {"run_id": args[0]})
    monkeypatch.setattr(runner, "write_manifest", lambda run_id, _: tmp_path / f"{run_id}.manifest.json")


def _result(mode: str) -> EngineResult:
    return EngineResult(
        config=mode,
        vad_mode=mode,
        vad_enabled=mode != "off",
        transcript="halo",
        staging_s=1.0,
        transcription_s=2.0,
        silence_removed=None,
        speech_seconds=None,
        cmd=["whisper-cli"],
        raw_stdout="halo",
        raw_stderr="",
    )


def test_score_uses_total_configuration_time():
    metric = _score(
        _result("presegmented"),
        "halo",
        10.0,
        vad_mode="presegmented",
        total_s=5.0,
        segment_prep_s=2.0,
    )

    assert metric.total_s == 5.0
    assert metric.rtf == 0.5
    assert metric.segment_prep_s == 2.0
    assert metric.staging_s == 1.0
    assert metric.transcription_s == 2.0
    assert metric.to_dict()["total_s"] == 5.0
    assert metric.to_dict()["segment_prep_s"] == 2.0
    assert metric.to_dict()["staging_s"] == 1.0
    assert metric.to_dict()["transcription_s"] == 2.0


def test_score_converts_reference_segments_to_metric_tuples():
    result = _result("builtin")
    result.segments = [(0.0, 1.0, "halo")]

    metric = _score(
        result,
        "halo",
        1.0,
        ref_segments=[Segment(0.0, 1.0, "halo")],
    )

    assert metric.per_region_wer[0]["wer"] == 0.0
    assert metric.metric_status == "verified"
    assert metric.metric_error is None
    assert metric.to_dict()["metric_status"] == "verified"
    assert metric.to_dict()["metric_error"] is None


def test_score_records_region_metric_failure_without_losing_overall_scores(monkeypatch):
    import vad_bench.runner as runner

    def fail_regions(*_args):
        raise ValueError("bad regions")

    monkeypatch.setattr(runner, "per_region_wer", fail_regions)

    metric = _score(
        _result("builtin"),
        "halo",
        1.0,
        ref_segments=[Segment(0.0, 1.0, "halo")],
    )

    assert metric.wer == 0.0
    assert metric.cer == 0.0
    assert metric.per_region_wer == []
    assert metric.metric_status == "error"
    assert metric.metric_error == "bad regions"
    assert metric.to_dict()["metric_error"] == "bad regions"


def test_runner_record_captures_every_non_secret_effective_setting():
    settings = Settings(auth_password="secret", serve_host="0.0.0.0", serve_port=9000, run_stale_after_s=42)
    record = _record_from_metrics(_score(_result("builtin"), "halo", 1.0), settings)

    assert record["effective_settings"] == settings.model_dump(exclude={"auth_password"})
    assert "auth_password" not in record["effective_settings"]
    assert "legacy_vad_enabled" in record["effective_settings"]


def test_history_index_keeps_all_runs_for_pagination(tmp_path, monkeypatch):
    import vad_bench.runner as runner

    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path)
    for index in range(51):
        runner._save_to_history(
            {"resources": {"cpu_peak_percent": 10.0}},
            [], f"2026-07-13T00:00:{index:02d}Z", f"run-{index}", "manifest.json",
        )

    assert len(json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))) == 51


@pytest.mark.parametrize(
    ("mode", "clock_values", "expected_total_s", "expected_prep_s"),
    [
        ("off", [10.0, 15.0], 5.0, 0.0),
        ("builtin", [10.0, 15.0], 5.0, 0.0),
        ("presegmented", [10.0, 11.0, 13.0, 16.0], 6.0, 2.0),
    ],
)
def test_run_times_each_mode_before_work_until_transcription_result(
    tmp_path, monkeypatch, mode, clock_values, expected_total_s, expected_prep_s
):
    import vad_bench.runner as runner

    monkeypatch.setattr(runner, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(runner, "RUN_STATUS_PATH", tmp_path / "reports" / ".run_status.json")
    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path / "history")
    monkeypatch.setattr(runner, "CHUNKS_ROOT", tmp_path / "chunks")
    monkeypatch.setattr(runner, "ensure_wav", lambda: tmp_path / "audio.wav")
    monkeypatch.setattr(runner, "wav_duration", lambda _: 10.0)
    monkeypatch.setattr(runner, "load_reference", lambda: ("halo", []))
    monkeypatch.setattr(runner, "write_reference_artifacts", lambda _: None)
    monkeypatch.setattr(
        runner,
        "transcribe",
        lambda *args, **kwargs: (kwargs["on_output_ready"](), _result(mode))[1],
    )
    monkeypatch.setattr(
        runner,
        "compute_vad_segments",
        lambda *args, **kwargs: (
            kwargs["timings"].update(segment_prep_s=expected_prep_s, staging_s=0.0),
            [(0.0, 1.0)],
        )[1],
    )
    monkeypatch.setattr(runner, "slice_wav_segments", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "build_verdict", lambda *_: None)
    monkeypatch.setattr(
        runner,
        "ResourceMonitor",
        lambda **_: SimpleNamespace(
            latest={}, start=lambda: None, stop=lambda: None, summary=lambda: {}
        ),
    )
    clock = iter([clock_values[0], clock_values[-1]])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(clock))

    summary = run([{"name": mode, "overrides": {"vad_mode": mode}}], verbose=False)
    metric = summary["configs"][0]

    assert metric["total_s"] == expected_total_s
    assert metric["segment_prep_s"] == expected_prep_s
    assert metric["rtf"] == expected_total_s / 10.0
    assert metric["effective_settings"]["vad_mode"] == mode
    assert metric["whisper_model"] == "ggml-tiny.id.bin"
    assert summary["control_name"] is None
    assert summary["candidate_name"] is None
    assert summary["verdict"] is None
    assert summary["reference_quality"] == "silver"


def test_run_stops_total_when_whisper_output_is_ready(tmp_path, monkeypatch):
    import vad_bench.runner as runner

    monkeypatch.setattr(runner, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(runner, "RUN_STATUS_PATH", tmp_path / "reports" / ".run_status.json")
    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path / "history")
    monkeypatch.setattr(runner, "CHUNKS_ROOT", tmp_path / "chunks")
    monkeypatch.setattr(runner, "ensure_wav", lambda: tmp_path / "audio.wav")
    monkeypatch.setattr(runner, "wav_duration", lambda _: 10.0)
    monkeypatch.setattr(runner, "load_reference", lambda: ("halo", []))
    monkeypatch.setattr(runner, "write_reference_artifacts", lambda _: None)
    monkeypatch.setattr(runner, "slice_wav_segments", lambda *args: None)
    monkeypatch.setattr(runner, "build_verdict", lambda *_: None)
    monkeypatch.setattr(
        runner,
        "ResourceMonitor",
        lambda **_: SimpleNamespace(
            latest={}, start=lambda: None, stop=lambda: None, summary=lambda: {}
        ),
    )

    def fake_transcribe(*args, **kwargs):
        kwargs["on_output_ready"]()
        runner.time.perf_counter()  # Simulate cleanup after output is available.
        return _result("builtin")

    monkeypatch.setattr(runner, "transcribe", fake_transcribe)
    clock = iter([10.0, 15.0, 100.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(clock))

    summary = run([{"name": "builtin", "overrides": {"vad_mode": "builtin"}}], verbose=False)

    assert summary["configs"][0]["total_s"] == 5.0


def test_run_reports_remote_presegmented_staging_separately(tmp_path, monkeypatch):
    import vad_bench.runner as runner

    monkeypatch.setattr(runner, "REPORTS_ROOT", tmp_path / "reports")
    monkeypatch.setattr(runner, "RUN_STATUS_PATH", tmp_path / "reports" / ".run_status.json")
    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path / "history")
    monkeypatch.setattr(runner, "CHUNKS_ROOT", tmp_path / "chunks")
    monkeypatch.setattr(runner, "ensure_wav", lambda: tmp_path / "audio.wav")
    monkeypatch.setattr(runner, "wav_duration", lambda _: 10.0)
    monkeypatch.setattr(runner, "load_reference", lambda: ("halo", []))
    monkeypatch.setattr(runner, "write_reference_artifacts", lambda _: None)
    monkeypatch.setattr(runner, "slice_wav_segments", lambda *args: None)
    monkeypatch.setattr(runner, "build_verdict", lambda *_: None)
    monkeypatch.setattr(
        runner,
        "ResourceMonitor",
        lambda **_: SimpleNamespace(
            latest={}, start=lambda: None, stop=lambda: None, summary=lambda: {}
        ),
    )

    def fake_segments(*args, **kwargs):
        kwargs["timings"].update(staging_s=2.0, segment_prep_s=3.0)
        return [(0.0, 1.0)]

    def fake_transcribe(*args, **kwargs):
        kwargs["on_output_ready"]()
        return _result("presegmented")

    monkeypatch.setattr(runner, "compute_vad_segments", fake_segments)
    monkeypatch.setattr(runner, "transcribe", fake_transcribe)
    clock = iter([10.0, 22.0])
    monkeypatch.setattr(runner.time, "perf_counter", lambda: next(clock))

    summary = run(
        [{"name": "segments", "overrides": {"vad_mode": "presegmented"}}],
        verbose=False,
    )
    metric = summary["configs"][0]

    assert metric["total_s"] == 12.0
    assert metric["segment_prep_s"] == 3.0
    assert metric["staging_s"] == 3.0


def test_run_reraises_transcription_staging_errors(tmp_path, monkeypatch):
    import vad_bench.runner as runner

    statuses = []
    monkeypatch.setattr(runner, "ensure_wav", lambda: tmp_path / "audio.wav")
    monkeypatch.setattr(runner, "wav_duration", lambda _: 10.0)
    monkeypatch.setattr(runner, "load_reference", lambda: ("halo", []))
    monkeypatch.setattr(runner, "write_reference_artifacts", lambda _: None)
    monkeypatch.setattr(runner, "_write_status", statuses.append)
    monkeypatch.setattr(runner, "transcribe", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("remote staging failed")))
    monkeypatch.setattr(
        runner,
        "ResourceMonitor",
        lambda **_: SimpleNamespace(
            latest={}, start=lambda: None, stop=lambda: None, summary=lambda: {}
        ),
    )

    with pytest.raises(RuntimeError, match="remote staging failed"):
        run([{"name": "builtin", "overrides": {"vad_mode": "builtin"}}], verbose=False)

    assert "remote staging failed" in statuses[-1]["error"]
