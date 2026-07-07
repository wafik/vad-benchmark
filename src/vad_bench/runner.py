"""Benchmark runner — runs each requested config, scores against the
reference, writes reports/ + history/ snapshots, streams progress via the
``.run_status.json`` sidecar.

The structure mirrors the sibling ``ocr-benchmark`` exactly so the dashboard
patterns are portable:

- ``RUN_STATUS_PATH``   — atomic-write sidecar read by ``/api/progress``
- ``_RUN_GEN``          — in-process counter; a new run supersedes the old
- ``_Superseded``       — raised when a newer run is in flight
- ``_save_to_history``  — full config snapshot so future runs can diff
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from .audio import ensure_wav, wav_duration
from .config import Settings
from .engine import EngineResult, parse_settings_overrides, transcribe
from .metrics import RunMetrics, aggregate, cer, normalize, wer, word_alignment
from .paths import HISTORY_ROOT, MODELS_ROOT, REPORTS_ROOT
from .reference import load_reference, write_reference_artifacts
from .sysmon import ResourceMonitor

log = logging.getLogger(__name__)

RUN_STATUS_PATH = REPORTS_ROOT / ".run_status.json"

_RUN_GEN = 0


def _next_gen() -> int:
    global _RUN_GEN
    _RUN_GEN += 1
    return _RUN_GEN


class _Superseded(Exception):
    """Raised inside the loop when a newer run has started."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()


def _write_status(status: dict) -> None:
    """Atomically write the progress sidecar.

    ``os.replace`` on Windows can fail with WinError 5 when the target is
    briefly held by an AV scanner; retry a few times before falling back.
    """
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    status = {**status, "updated_at": _now_iso()}
    payload = json.dumps(status, ensure_ascii=False)
    tmp = RUN_STATUS_PATH.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")

    last_err: Exception | None = None
    for attempt in range(8):
        try:
            os.replace(tmp, RUN_STATUS_PATH)
            return
        except PermissionError as e:
            last_err = e
            time.sleep(0.05 * (attempt + 1))
    RUN_STATUS_PATH.write_text(payload, encoding="utf-8")
    try:
        tmp.unlink()
    except OSError:
        pass
    if last_err is not None:
        import warnings
        warnings.warn(f"_write_status fell back to non-atomic write: {last_err}")


def run(
    configs: list[dict] | None = None,
    *,
    verbose: bool = True,
) -> dict:
    """Top-level entrypoint.

    ``configs`` is a list of ``{name, overrides}`` dicts. ``overrides`` is
    a partial Settings dict (any field from config.Settings). If omitted,
    runs the canonical 2-config comparison: ``baseline_novad`` vs
    ``silero_vad``.

    Returns the aggregated summary dict.
    """
    if configs is None:
        configs = [
            {"name": "baseline_novad", "overrides": {"vad_enabled": False}},
            {"name": "silero_vad",     "overrides": {"vad_enabled": True}},
        ]

    # 1. Ensure audio + reference are ready.
    wav = ensure_wav()
    audio_duration = wav_duration(wav)
    reference_text, segments = load_reference()
    refs_dir = REPORTS_ROOT / "reference"
    write_reference_artifacts(refs_dir)

    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    per_config_dir = REPORTS_ROOT / "per_config"
    per_config_dir.mkdir(parents=True, exist_ok=True)

    base = Settings()

    monitor = ResourceMonitor(interval_s=2.0)
    monitor.start()

    started_at = _now_iso()
    completed: list[dict] = []
    gen = _next_gen()

    _write_status({
        "running": True,
        "started_at": started_at,
        "total": len(configs),
        "completed": completed,
        "current": None,
        "system": monitor.latest,
    })

    run_metrics: list[RunMetrics] = []
    run_records: list[dict] = []

    try:
        for idx, cfg in enumerate(configs, 1):
            if gen != _RUN_GEN:
                raise _Superseded()

            name = cfg.get("name") or f"config_{idx}"
            overrides = cfg.get("overrides") or {}
            s = parse_settings_overrides(overrides, base)

            _write_status({
                "running": True,
                "started_at": started_at,
                "total": len(configs),
                "completed": completed,
                "current": {"name": name, "index": idx, "vad_enabled": s.vad_enabled},
                "system": monitor.latest,
            })

            log.info("=== Config %d/%d: %s (vad=%s) ===", idx, len(configs), name, s.vad_enabled)
            print(f"[{idx}/{len(configs)}] {name}: vad={s.vad_enabled}", flush=True)

            try:
                result: EngineResult = transcribe(
                    wav,
                    config=name,
                    settings=s,
                    models_root=MODELS_ROOT,
                    audio_duration_s=audio_duration,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("Config %s failed", name)
                _write_status({
                    "running": False,
                    "started_at": started_at,
                    "finished_at": _now_iso(),
                    "error": f"{name}: {type(exc).__name__}: {exc}",
                    "current": None,
                })
                raise

            rm = _score(result, reference_text, audio_duration)
            run_metrics.append(rm)
            run_records.append(_record_from_metrics(rm, s))

            # Per-config JSON artifact (transcript, alignment, metrics).
            (per_config_dir / f"{_slug(name)}.json").write_text(
                json.dumps(rm.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            completed.append({
                "name": name,
                "vad_enabled": s.vad_enabled,
                "runtime_s": round(result.runtime_s, 3),
                "wer": round(rm.wer, 4),
                "cer": round(rm.cer, 4),
            })

            _write_status({
                "running": True,
                "started_at": started_at,
                "total": len(configs),
                "completed": completed,
                "current": {"name": name, "index": idx, "vad_enabled": s.vad_enabled},
                "system": monitor.latest,
            })

            if verbose:
                tag = f"WER={rm.wer:.3f} CER={rm.cer:.3f} RTF={rm.rtf:.3f} " \
                      f"runtime={rm.runtime_s:.1f}s"
                if rm.silence_removed is not None:
                    tag += f" silence_removed={rm.silence_removed:.1%} segs={rm.n_segments}"
                print(f"  {name}: {tag}", flush=True)

        if gen != _RUN_GEN:
            raise _Superseded()

        summary = aggregate(run_metrics)
        summary["audio_duration_s"] = audio_duration
        summary["reference_segments"] = len(segments)
        summary["last_run"] = _now_iso()
        summary["total_runtime_s"] = round(sum(r.runtime_s for r in run_metrics), 3)

        resource_summary = monitor.summary()
        summary["resources"] = resource_summary

        # Write summary.json + .csv.
        (REPORTS_ROOT / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_summary_csv(run_records)

        # History snapshot.
        _save_to_history(summary, run_records, started_at)

        _write_status({
            "running": False,
            "started_at": started_at,
            "finished_at": _now_iso(),
            "total": len(configs),
            "completed": completed,
            "current": None,
            "system": monitor.latest,
            "resources": resource_summary,
        })

        log.info("=== Benchmark done: %d configs, %s ===",
                 len(configs),
                 ", ".join(f"{r.config} WER={r.wer:.3f}" for r in run_metrics))
        if verbose:
            _print_overall(summary, run_metrics)

        return summary

    except _Superseded:
        log.info("Run %d superseded by a newer run; bailing", gen)
        return {}
    except BaseException as e:  # noqa: BLE001
        log.exception("Benchmark failed; clearing run status")
        if gen == _RUN_GEN:
            _write_status({
                "running": False,
                "started_at": started_at,
                "finished_at": _now_iso(),
                "error": f"{type(e).__name__}: {e}",
                "current": None,
            })
        raise
    finally:
        monitor.stop()


def _score(result: EngineResult, reference_norm: str, audio_duration_s: float) -> RunMetrics:
    hyp_norm = normalize(result.transcript)
    return RunMetrics(
        config=result.config,
        vad_enabled=result.vad_enabled,
        transcript_raw=result.transcript,
        transcript_normalized=hyp_norm,
        reference_normalized=reference_norm,
        wer=wer(reference_norm, hyp_norm),
        cer=cer(reference_norm, hyp_norm),
        rtf=result.runtime_s / audio_duration_s if audio_duration_s > 0 else 0.0,
        runtime_s=result.runtime_s,
        audio_duration_s=audio_duration_s,
        speech_seconds=result.speech_seconds,
        silence_removed=result.silence_removed if result.vad_enabled else None,
        n_segments=None,
        alignment=word_alignment(reference_norm, hyp_norm),
    )


def _record_from_metrics(rm: RunMetrics, s: Settings) -> dict:
    return {
        "config": rm.config,
        "vad_enabled": rm.vad_enabled,
        "wer": rm.wer,
        "cer": rm.cer,
        "rtf": rm.rtf,
        "runtime_s": rm.runtime_s,
        "audio_duration_s": rm.audio_duration_s,
        "speech_seconds": rm.speech_seconds,
        "silence_removed": rm.silence_removed,
        "n_segments": rm.n_segments,
        "vad_threshold": s.vad_threshold,
        "vad_min_speech_ms": s.vad_min_speech_ms,
        "vad_min_silence_ms": s.vad_min_silence_ms,
        "vad_speech_pad_ms": s.vad_speech_pad_ms,
        "vad_max_speech_s": s.vad_max_speech_s,
        "whisper_model": s.whisper_model,
        "language": s.language,
        "threads": s.threads,
    }


def _write_summary_csv(records: list[dict]) -> None:
    import csv
    csv_path = REPORTS_ROOT / "summary.csv"
    if not records:
        csv_path.write_text("config,wer,cer,rtf,runtime_s\n", encoding="utf-8")
        return
    fields = [
        "config", "vad_enabled", "wer", "cer", "rtf", "runtime_s",
        "audio_duration_s", "speech_seconds", "silence_removed", "n_segments",
        "whisper_model", "language", "threads",
        "vad_threshold", "vad_min_speech_ms", "vad_min_silence_ms",
        "vad_speech_pad_ms", "vad_max_speech_s",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow(r)


def _save_to_history(summary: dict, records: list[dict], started_at: str) -> None:
    HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = started_at.replace(":", "-").replace("T", "_").replace("Z", "")
    snapshot = {
        "id": run_id,
        "timestamp": started_at,
        "audio_duration_s": summary.get("audio_duration_s"),
        "total_runtime_s": summary.get("total_runtime_s"),
        "resources": summary.get("resources", {}),
        "overall": {
            "best_wer_config": summary.get("best_wer_config"),
            "best_cer_config": summary.get("best_cer_config"),
            "fastest_rtf_config": summary.get("fastest_rtf_config"),
        },
        "configs": records,
    }
    (HISTORY_ROOT / f"{run_id}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    index_path = HISTORY_ROOT / "index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            index = []
    else:
        index = []
    index = [e for e in index if e.get("id") != run_id]
    index.append({
        "id": run_id,
        "timestamp": started_at,
        "audio_duration_s": summary.get("audio_duration_s"),
        "total_runtime_s": summary.get("total_runtime_s"),
        "n_configs": len(records),
        "best_wer_config": summary.get("best_wer_config"),
        "best_cer_config": summary.get("best_cer_config"),
        "best_wer": min((r["wer"] for r in records), default=None),
        "best_cer": min((r["cer"] for r in records), default=None),
    })
    index = index[-50:]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _print_overall(summary: dict, runs: list[RunMetrics]) -> None:
    print()
    print("=" * 72)
    print(
        f"OVERALL · {len(runs)} configs · audio={summary.get('audio_duration_s', 0):.1f}s · "
        f"total_runtime={summary.get('total_runtime_s', 0):.1f}s"
    )
    print(f"  Best WER:   {summary.get('best_wer_config')}  ({min(r.wer for r in runs):.3f})")
    print(f"  Best CER:   {summary.get('best_cer_config')}  ({min(r.cer for r in runs):.3f})")
    print(f"  Fastest RTF:{summary.get('fastest_rtf_config')}  ({min(r.rtf for r in runs):.3f})")
    print()
    header = f"{'config':<22} {'VAD':>4} {'WER':>7} {'CER':>7} {'RTF':>7} {'runtime':>9} {'silence':>8} {'segs':>5}"
    print(header)
    for r in runs:
        silence = f"{r.silence_removed:.1%}" if r.silence_removed is not None else "-"
        segs = str(r.n_segments) if r.n_segments is not None else "-"
        print(
            f"{r.config[:21]:<22} {'on' if r.vad_enabled else 'off':>4} "
            f"{r.wer:>7.3f} {r.cer:>7.3f} {r.rtf:>7.3f} {r.runtime_s:>8.1f}s "
            f"{silence:>8} {segs:>5}"
        )


def read_status(stale_after_s: int) -> dict:
    """Read the live status sidecar. Stamps ``stale:true`` if the lock
    hasn't been touched for ``stale_after_s`` seconds — same as ocr-benchmark
    so the UI can show a calm "looks stuck" message."""
    idle = {"running": False, "total": 0, "completed": [], "current": None}
    if not RUN_STATUS_PATH.exists():
        return idle
    try:
        status = json.loads(RUN_STATUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return idle
    if status.get("running"):
        last = status.get("updated_at") or status.get("started_at")
        try:
            ts = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            ts = None
        if ts and (datetime.now(timezone.utc) - ts).total_seconds() > stale_after_s:
            status["stale"] = True
    return status


if __name__ == "__main__":  # self-check
    s = read_status(stale_after_s=600)
    print("status:", s)