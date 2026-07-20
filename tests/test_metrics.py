"""Smoke tests for the WER/CER/alignment module."""
from pathlib import Path

from vad_bench.metrics import RunMetrics, aggregate, cer, normalize, wer, word_alignment
from vad_bench.runner import _record_from_metrics, _score
from vad_bench.config import Settings
from vad_bench.engine import EngineResult


def test_normalize():
    assert normalize("  HELLO   world  ") == "hello world"
    assert normalize("") == ""
    assert normalize("½") == normalize("½")  # NFKC stable


def test_cer():
    assert cer("HELLO world", "hello  WORLD") == 0.0
    assert abs(cer("abc", "axc") - 1 / 3) < 1e-9
    assert cer("", "anything") == 1.0
    assert cer("anything", "") == 1.0


def test_wer():
    assert wer("the cat sat", "the cat sit") == 1 / 3
    assert wer("", "anything") == 1.0


def test_word_alignment_equal():
    parts = word_alignment("satu dua tiga", "satu dua tiga")
    assert all(p["kind"] == "equal" for p in parts)


def test_word_alignment_delete():
    parts = word_alignment("satu dua tiga", "satu tiga")
    kinds = [p["kind"] for p in parts]
    assert "equal" in kinds
    assert "delete" in kinds


def test_word_alignment_insert():
    parts = word_alignment("satu tiga", "satu dua tiga")
    kinds = [p["kind"] for p in parts]
    assert "insert" in kinds


def test_word_alignment_substitute():
    parts = word_alignment("satu dua", "satu tiga")
    kinds = [p["kind"] for p in parts]
    assert "substitute" in kinds


def test_word_alignment_empty():
    assert word_alignment("", "") == []
    assert all(p["kind"] == "insert" for p in word_alignment("", "hello"))
    assert all(p["kind"] == "delete" for p in word_alignment("hello", ""))


def test_run_metrics_chunks_available_default_and_serialization():
    rm = RunMetrics(
        config="c", vad_mode="builtin", vad_enabled=True,
        transcript_raw="", transcript_normalized="", reference_normalized="",
        wer=0.0, cer=0.0, rtf=0.0, runtime_s=0.0, audio_duration_s=0.0,
    )
    assert rm.chunks_available is False
    assert rm.to_dict()["chunks_available"] is False

    rm2 = RunMetrics(
        config="c", vad_mode="builtin", vad_enabled=True,
        transcript_raw="", transcript_normalized="", reference_normalized="",
        wer=0.0, cer=0.0, rtf=0.0, runtime_s=0.0, audio_duration_s=0.0,
        chunks_available=True,
    )
    assert rm2.to_dict()["chunks_available"] is True


def test_results_and_runner_records_retain_each_vad_mode():
    modes = ("off", "builtin", "presegmented")
    metrics = [
        RunMetrics(
            config=mode,
            vad_mode=mode,
            vad_enabled=mode != "off",
            transcript_raw="",
            transcript_normalized="",
            reference_normalized="",
            wer=0.0,
            cer=0.0,
            rtf=0.0,
            runtime_s=0.0,
            audio_duration_s=0.0,
        )
        for mode in modes
    ]

    assert [row["vad_mode"] for row in aggregate(metrics)["configs"]] == list(modes)
    assert [
        _record_from_metrics(metric, Settings(vad_mode=metric.vad_mode))["vad_mode"]
        for metric in metrics
    ] == list(modes)
    runner_source = (Path(__file__).resolve().parents[1] / "src" / "vad_bench" / "runner.py").read_text(encoding="utf-8")
    completed = runner_source[runner_source.index("completed.append({"):runner_source.index("_write_status({", runner_source.index("completed.append({"))]
    assert '"vad_mode": s.vad_mode' in completed


def test_aggregate_exposes_dashboard_facts_without_client_reconstruction():
    runs = [
        RunMetrics(
            config="off", vad_mode="off", vad_enabled=False,
            transcript_raw="", transcript_normalized="", reference_normalized="",
            wer=0.4, cer=0.3, rtf=0.8, runtime_s=8.0, total_s=8.0, audio_duration_s=10.0,
        ),
        RunMetrics(
            config="builtin", vad_mode="builtin", vad_enabled=True,
            transcript_raw="", transcript_normalized="", reference_normalized="",
            wer=0.2, cer=0.1, rtf=0.6, runtime_s=6.0, total_s=6.0, audio_duration_s=10.0,
            speech_seconds=4.0, n_segments=2, avg_seg_duration=2.0,
        ),
    ]

    result = aggregate(runs)

    assert result["best_wer"] == 0.2
    assert result["best_cer"] == 0.1
    assert result["fastest_rtf"] == 0.6
    assert result["vad_summary"] == {
        "total_segments": 2,
        "avg_segment_duration": 2.0,
        "speech_coverage": 0.4,
    }


def test_aggregate_leaves_missing_vad_timing_facts_unavailable():
    run = RunMetrics(
        config="builtin", vad_mode="builtin", vad_enabled=True,
        transcript_raw="", transcript_normalized="", reference_normalized="",
        wer=0.2, cer=0.1, rtf=0.6, runtime_s=6.0, total_s=6.0, audio_duration_s=10.0,
        n_segments=2,
    )

    result = aggregate([run])

    assert result["vad_summary"] == {
        "total_segments": 2,
        "avg_segment_duration": None,
        "speech_coverage": None,
    }


def test_scoring_retains_presegmented_mode():
    result = EngineResult(
        config="segments",
        vad_mode="presegmented",
        vad_enabled=True,
        transcript="halo",
        staging_s=0.0,
        transcription_s=1.0,
        silence_removed=0.5,
        speech_seconds=1.0,
        cmd=["whisper-cli"],
        raw_stdout="halo",
        raw_stderr="",
    )

    assert _score(result, "halo", 2.0).to_dict()["vad_mode"] == "presegmented"
