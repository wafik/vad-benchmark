"""WER / CER / RTF / silence-removed metrics.

``normalize`` mirrors the sibling ``ocr-benchmark`` exactly: NFKC, lowercase,
collapse whitespace, strip. That way both projects score text the same way and
the WER is comparable.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

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


@dataclass
class RunMetrics:
    config: str
    vad_enabled: bool
    transcript_raw: str
    transcript_normalized: str
    reference_normalized: str
    wer: float
    cer: float
    rtf: float
    runtime_s: float
    audio_duration_s: float
    # VAD-specific; zero / NaN when vad_enabled=False.
    speech_seconds: float | None = None
    silence_removed: float | None = None
    n_segments: int | None = None
    # Optional aligned diff for the UI.
    alignment: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "config": self.config,
            "vad_enabled": self.vad_enabled,
            "transcript_raw": self.transcript_raw,
            "transcript_normalized": self.transcript_normalized,
            "wer": self.wer,
            "cer": self.cer,
            "rtf": self.rtf,
            "runtime_s": self.runtime_s,
            "audio_duration_s": self.audio_duration_s,
            "speech_seconds": self.speech_seconds,
            "silence_removed": self.silence_removed,
            "n_segments": self.n_segments,
            "alignment": self.alignment,
        }


def aggregate(runs: Iterable[RunMetrics]) -> dict:
    runs = list(runs)
    if not runs:
        return {"n_configs": 0, "configs": []}
    return {
        "n_configs": len(runs),
        "configs": [r.to_dict() for r in runs],
        "best_wer_config": min(runs, key=lambda r: r.wer).config,
        "best_cer_config": min(runs, key=lambda r: r.cer).config,
        "fastest_rtf_config": min(runs, key=lambda r: r.rtf).config,
    }


if __name__ == "__main__":  # self-check
    assert cer("HELLO world", "hello  WORLD") == 0.0
    assert cer("abc", "axc") == 1 / 3
    assert wer("the cat sat", "the cat sit") == 1 / 3
    diff = word_alignment("satu dua tiga", "satu tiga")
    kinds = sorted({d["kind"] for d in diff})
    assert "delete" in kinds, f"expected 'delete' in {diff}"
    print("metrics self-check: OK")