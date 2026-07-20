"""WER / CER / RTF / silence-removed metrics.

``normalize`` mirrors the sibling ``ocr-benchmark`` exactly: NFKC, lowercase,
collapse whitespace, strip. That way both projects score text the same way and
the WER is comparable.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Literal, Sequence

import jiwer


def normalize(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text).lower()
    t = " ".join(t.split())
    return t.strip()


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    r, h = normalize(ref), normalize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return jiwer.cer(r, h)


def wer(ref: str, hyp: str) -> float:
    if not ref:
        return 0.0 if not hyp else 1.0
    r, h = normalize(ref), normalize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return jiwer.wer(r, h)


def word_alignment(ref: str, hyp: str) -> list[dict]:
    """Per-word alignment for the dashboard diff view.

    Returns ``[{kind, ref, hyp}, ...]`` where ``kind`` is one of
    ``equal | substitute | insert | delete``.

    jiwer's ``AlignmentChunk`` only carries index spans into the original
    tokenized ref/hyp lists (``ref_start_idx..ref_end_idx``,
    ``hyp_start_idx..hyp_end_idx``) — the chunk type tells us which side each
    span came from:

      equal:       both spans non-empty, same word
      substitute:  both spans non-empty, different word
      insert:      ref span empty (word only in hyp)
      delete:      hyp span empty (word only in ref)
    """
    r, h = normalize(ref), normalize(hyp)
    if not r and not h:
        return []
    if not r:
        return [{"kind": "insert", "ref": "", "hyp": w} for w in h.split()]
    if not h:
        return [{"kind": "delete", "ref": w, "hyp": ""} for w in r.split()]

    ref_tokens = r.split()
    hyp_tokens = h.split()
    out: list[dict] = []
    for chunk in jiwer.process_words([r], [h]).alignments[0]:
        kind = chunk.type
        ref_slice = ref_tokens[chunk.ref_start_idx:chunk.ref_end_idx]
        hyp_slice = hyp_tokens[chunk.hyp_start_idx:chunk.hyp_end_idx]
        if kind == "equal":
            # Pair them up one-by-one (same length when kind == equal).
            for rw, hw in zip(ref_slice, hyp_slice):
                out.append({"kind": "equal", "ref": rw, "hyp": hw})
        elif kind == "substitute":
            # Pair ref slice with hyp slice — usually 1:1 but handle N:M defensively.
            maxlen = max(len(ref_slice), len(hyp_slice))
            for i in range(maxlen):
                out.append({
                    "kind": "substitute",
                    "ref": ref_slice[i] if i < len(ref_slice) else "",
                    "hyp": hyp_slice[i] if i < len(hyp_slice) else "",
                })
        elif kind == "insert":
            for hw in hyp_slice:
                out.append({"kind": "insert", "ref": "", "hyp": hw})
        elif kind == "delete":
            for rw in ref_slice:
                out.append({"kind": "delete", "ref": rw, "hyp": ""})
    return out


def per_region_wer(
    ref_segments: Sequence[tuple[float, float, str]],
    hyp_segments: Sequence[tuple[float, float, str]],
    *,
    iou_threshold: float = 0.1,
) -> list[dict]:
    """Compute per-reference-caption-region WER/CER by timestamp overlap.

    Caption timestamps define comparison windows; they do not measure VAD
    boundary quality.

    For each reference segment, finds the hyp segment with the largest
    intersection-over-union (IoU) overlap. If the best IoU is below
    ``iou_threshold``, the reference region is treated as having no
    matching hyp (i.e. WER=1.0 for missing region).

    Returns one entry per reference segment::

        [{index, start, end, duration, ref_text, hyp_text, hyp_start,
          hyp_end, wer, cer, overlap}, ...]
    """
    out: list[dict] = []
    for i, (rs, re_, rt) in enumerate(ref_segments):
        ref_dur = max(0.0, re_ - rs)
        best_iou = 0.0
        best_match: tuple[float, float, str] | None = None
        for hs, he_, ht in hyp_segments:
            inter = max(0.0, min(re_, he_) - max(rs, hs))
            union = ref_dur + max(0.0, he_ - hs) - inter
            iou = (inter / union) if union > 0 else 0.0
            if iou > best_iou:
                best_iou = iou
                best_match = (hs, he_, ht)
        if best_match is not None and best_iou >= iou_threshold:
            hs, he_, ht = best_match
            w = wer(rt, ht)
            c = cer(rt, ht)
        else:
            hs = he_ = 0.0
            ht = ""
            w = 1.0 if rt.strip() else 0.0
            c = 1.0 if rt.strip() else 0.0
        out.append({
            "index": i,
            "start": rs,
            "end": re_,
            "duration": ref_dur,
            "ref_text": rt,
            "hyp_text": ht,
            "hyp_start": hs,
            "hyp_end": he_,
            "wer": w,
            "cer": c,
            "overlap": best_iou,
        })
    return out


@dataclass
class RunMetrics:
    config: str
    vad_mode: str
    vad_enabled: bool
    transcript_raw: str
    transcript_normalized: str
    reference_normalized: str
    wer: float
    cer: float
    rtf: float
    runtime_s: float
    audio_duration_s: float
    total_s: float = 0.0
    segment_prep_s: float = 0.0
    staging_s: float = 0.0
    transcription_s: float = 0.0
    # VAD-specific; zero / NaN when vad_enabled=False.
    speech_seconds: float | None = None
    silence_removed: float | None = None
    n_segments: int | None = None
    # Per-segment (start, end, text) parsed from whisper-cli output.
    # Empty when --no-timestamps was on or parsing failed.
    segments: list[tuple[float, float, str]] = field(default_factory=list)
    # Optional aligned diff for the UI.
    alignment: list[dict] = field(default_factory=list)
    chunks_available: bool = False
    # Per-region WER/CER from server-side computation (real jiwer metrics,
    # not the simplified client-side word-overlap proxy).
    per_region_wer: list[dict] = field(default_factory=list)
    metric_status: Literal["verified", "error"] = "verified"
    metric_error: str | None = None
    run_id: str | None = None
    manifest_path: str | None = None
    # Average segment duration in seconds (speech_seconds / n_segments).
    avg_seg_duration: float | None = None

    def __post_init__(self) -> None:
        self.rtf = self.total_s / self.audio_duration_s if self.audio_duration_s > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "config": self.config,
            "vad_mode": self.vad_mode,
            "vad_enabled": self.vad_enabled,
            "transcript_raw": self.transcript_raw,
            "transcript_normalized": self.transcript_normalized,
            "wer": self.wer,
            "cer": self.cer,
            "rtf": self.rtf,
            "runtime_s": self.runtime_s,
            "audio_duration_s": self.audio_duration_s,
            "total_s": self.total_s,
            "segment_prep_s": self.segment_prep_s,
            "staging_s": self.staging_s,
            "transcription_s": self.transcription_s,
            "speech_seconds": self.speech_seconds,
            "silence_removed": self.silence_removed,
            "n_segments": self.n_segments,
            "segments": [
                {"start": s, "end": e, "text": t}
                for s, e, t in self.segments
            ],
            "alignment": self.alignment,
            "chunks_available": self.chunks_available,
            "per_region_wer": self.per_region_wer,
            "metric_status": self.metric_status,
            "metric_error": self.metric_error,
            "run_id": self.run_id,
            "manifest_path": self.manifest_path,
            "avg_seg_duration": self.avg_seg_duration,
        }


def aggregate(runs: Iterable[RunMetrics]) -> dict:
    runs = list(runs)
    if not runs:
        return {"n_configs": 0, "configs": []}
    vad_runs = [run for run in runs if run.vad_mode != "off" and run.n_segments is not None]
    total_segments = sum(run.n_segments for run in vad_runs)
    has_speech_timing = all(run.speech_seconds is not None for run in vad_runs)
    total_speech = sum(run.speech_seconds for run in vad_runs) if has_speech_timing else None
    audio_duration = vad_runs[0].audio_duration_s if vad_runs else 0.0
    vad_summary = None
    if vad_runs:
        vad_summary = {
            "total_segments": total_segments,
            "avg_segment_duration": total_speech / total_segments if total_speech is not None and total_segments else None,
            "speech_coverage": total_speech / len(vad_runs) / audio_duration if total_speech is not None and audio_duration > 0 else None,
        }
    return {
        "n_configs": len(runs),
        "configs": [r.to_dict() for r in runs],
        "best_wer_config": min(runs, key=lambda r: r.wer).config,
        "best_wer": min(run.wer for run in runs),
        "best_cer_config": min(runs, key=lambda r: r.cer).config,
        "best_cer": min(run.cer for run in runs),
        "fastest_rtf_config": min(runs, key=lambda r: r.rtf).config,
        "fastest_rtf": min(run.rtf for run in runs),
        "vad_summary": vad_summary,
    }


if __name__ == "__main__":  # self-check
    assert cer("HELLO world", "hello  WORLD") == 0.0
    assert cer("abc", "axc") == 1 / 3
    assert wer("the cat sat", "the cat sit") == 1 / 3
    diff = word_alignment("satu dua tiga", "satu tiga")
    kinds = sorted({d["kind"] for d in diff})
    assert "delete" in kinds, f"expected 'delete' in {diff}"

    # per_region_wer
    ref_segs = [(0.0, 5.0, "halo semua"), (5.0, 10.0, "hari ini kita ngobrol")]
    hyp_segs_perfect = [(0.0, 5.0, "halo semua"), (5.0, 10.0, "hari ini kita ngobrol")]
    out = per_region_wer(ref_segs, hyp_segs_perfect)
    assert len(out) == 2
    assert out[0]["wer"] == 0.0 and out[1]["wer"] == 0.0, out
    assert out[0]["hyp_text"] == "halo semua"

    # substitution in one region
    hyp_segs_partial = [(0.0, 5.0, "halo semua"), (5.0, 10.0, "hari ini kita bisnis")]
    out = per_region_wer(ref_segs, hyp_segs_partial)
    assert out[0]["wer"] == 0.0
    assert out[1]["wer"] > 0.0, out[1]

    # ref region with no overlapping hyp -> empty match
    hyp_segs_short = [(0.0, 5.0, "halo semua")]
    out = per_region_wer(ref_segs, hyp_segs_short)
    assert out[0]["wer"] == 0.0
    assert out[1]["wer"] == 1.0   # all ref words missing
    assert out[1]["hyp_text"] == ""

    print("metrics self-check: OK")
