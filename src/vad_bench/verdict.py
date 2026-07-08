"""Auto-verdict for a benchmark run.

Builds a short Indonesian paragraph comparing every config in the run,
with the headline deltas between VAD-off and VAD-on. Returns one string,
suitable for storing as ``summary["verdict"]`` and rendering as-is in the
dashboard. No LLM, no API calls — just arithmetic + templates.

Layout:

- If the run has only one config or only one side of the VAD toggle, the
  verdict describes just that single config.
- If both sides are present, the verdict gives the headline deltas
  (ΔWER, ΔCER, ΔRTF, silence_removed) and ends with a recommendation.
"""
from __future__ import annotations

from typing import Iterable


def _fmt_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _safe(v, default=None):
    return v if v is not None else default


def _pick(records: list[dict], vad_enabled: bool) -> list[dict]:
    return [r for r in records if bool(r.get("vad_enabled")) == vad_enabled]


def build_verdict(records: Iterable[dict]) -> str:
    """Build the Indonesian verdict string for a single run.

    ``records`` may be empty (returns a short notice) or contain configs
    with optional fields (``wer``, ``cer``, ``rtf``, ``runtime_s``,
    ``silence_removed``, ``n_segments``, ``vad_enabled``, ``config``).
    """
    records = list(records)
    if not records:
        return "Tidak ada config yang dijalankan."

    off = _pick(records, False)
    on = _pick(records, True)

    # Single-config or single-side case.
    if not off or not on:
        only = off or on
        state = "VAD ON" if on and not off else "VAD OFF"
        best = min(only, key=lambda r: _safe(r.get("wer"), 1.0))
        parts = [f"Run hanya berisi satu sisi ({state})."]
        wer = best.get("wer")
        cer = best.get("cer")
        rtf = best.get("rtf")
        if wer is not None:
            parts.append(f"Config terbaik: {best['config']} dengan WER {wer:.3f}")
        if cer is not None:
            parts.append(f"CER {cer:.3f}")
        if rtf is not None:
            parts.append(f"RTF {rtf:.3f}")
        return " ".join(parts) + "."

    # Head-to-head: use the lowest-WER config on each side.
    a = min(off, key=lambda r: _safe(r.get("wer"), 1.0))
    b = min(on, key=lambda r: _safe(r.get("wer"), 1.0))

    wer_off = _safe(a.get("wer"))
    wer_on = _safe(b.get("wer"))
    cer_off = _safe(a.get("cer"))
    cer_on = _safe(b.get("cer"))
    rtf_off = _safe(a.get("rtf"))
    rtf_on = _safe(b.get("rtf"))
    silence = _safe(b.get("silence_removed"))

    sentences: list[str] = []
    sentences.append(
        f"Membandingkan {a['config']} (VAD off) vs {b['config']} (VAD on)."
    )

    # WER delta is the headline.
    if wer_off is not None and wer_on is not None:
        d_wer = wer_on - wer_off
        if abs(d_wer) < 0.02:
            sentences.append(
                f"VAD tidak banyak mengubah WER (Δ {_fmt_pct(d_wer)}, "
                f"dari {wer_off:.3f} → {wer_on:.3f})."
            )
        elif d_wer < 0:
            sentences.append(
                f"VAD menurunkan WER sebesar {abs(d_wer) * 100:.1f}% "
                f"(dari {wer_off:.3f} → {wer_on:.3f})."
            )
        else:
            sentences.append(
                f"VAD meningkatkan WER sebesar {d_wer * 100:.1f}% "
                f"(dari {wer_off:.3f} → {wer_on:.3f})."
            )

    if cer_off is not None and cer_on is not None:
        d_cer = cer_on - cer_off
        sentences.append(
            f"CER {_fmt_pct(d_cer)} (CER {cer_off:.3f} → {cer_on:.3f})."
        )

    if rtf_off is not None and rtf_on is not None:
        d_rtf = rtf_on - rtf_off
        if rtf_off > 0:
            speedup = rtf_off / rtf_on if rtf_on > 0 else float("inf")
            if d_rtf < 0:
                sentences.append(
                    f"Waktu proses turun {speedup:.2f}× "
                    f"(RTF {rtf_off:.3f} → {rtf_on:.3f})."
                )
            elif d_rtf > 0:
                sentences.append(
                    f"Waktu proses naik {(speedup):.2f}× lebih lama "
                    f"(RTF {rtf_off:.3f} → {rtf_on:.3f})."
                )
            else:
                sentences.append(f"RTF tidak berubah ({rtf_off:.3f}).")
        else:
            sentences.append(f"RTF {rtf_on:.3f}.")

    if silence is not None:
        sentences.append(
            f"VAD memangkas {silence * 100:.1f}% audio sebagai silence."
        )

    # Recommendation — go by WER direction with a small dead-zone.
    if wer_off is not None and wer_on is not None:
        d_wer = wer_on - wer_off
        if d_wer <= 0.0:
            sentences.append(
                "Rekomendasi: aktifkan VAD untuk audio berdurasi panjang."
            )
        elif d_wer > 0.02:
            sentences.append(
                "Rekomendasi: nonaktifkan VAD, atau turunkan vad_threshold "
                "dan kurangi vad_min_silence_ms — VAD saat ini terlalu agresif."
            )
        else:
            sentences.append(
                "Rekomendasi: VAD netral terhadap akurasi; pilihan tergantung "
                "trade-off runtime vs biaya komputasi."
            )

    return " ".join(sentences)


if __name__ == "__main__":  # self-check
    # Synthetic baseline vs silero where VAD is strictly better.
    rec = [
        {"config": "baseline", "vad_enabled": False, "wer": 0.539, "cer": 0.210,
         "rtf": 0.051, "runtime_s": 31.4, "silence_removed": None, "n_segments": None},
        {"config": "silero_vad", "vad_enabled": True, "wer": 0.482, "cer": 0.180,
         "rtf": 0.074, "runtime_s": 45.2, "silence_removed": 0.40, "n_segments": 12},
    ]
    out = build_verdict(rec)
    assert "WER" in out, out
    assert "0.539" in out and "0.482" in out, out
    assert "aktifkan VAD" in out, out
    # Case where VAD hurts.
    rec_bad = [
        {"config": "baseline", "vad_enabled": False, "wer": 0.40, "cer": 0.15,
         "rtf": 0.05, "runtime_s": 30.0, "silence_removed": None, "n_segments": None},
        {"config": "silero", "vad_enabled": True, "wer": 0.50, "cer": 0.20,
         "rtf": 0.09, "runtime_s": 55.0, "silence_removed": 0.55, "n_segments": 8},
    ]
    out_bad = build_verdict(rec_bad)
    assert "nonaktifkan VAD" in out_bad or "turunkan vad_threshold" in out_bad, out_bad
    # Empty / single-config safety.
    assert "Tidak ada config" in build_verdict([])
    only = [{"config": "x", "vad_enabled": True, "wer": 0.3, "cer": 0.1, "rtf": 0.05}]
    out_only = build_verdict(only)
    assert "VAD ON" in out_only, out_only
    print("verdict self-check: OK")
