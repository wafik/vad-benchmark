"""RMS-energy VAD — a classic, non-neural baseline to compare against Silero.

Fixed threshold relative to the file's own peak RMS. No numpy/audioop:
stdlib ``wave`` + ``array`` only, mirroring the project's dependency-light
philosophy. Returns the same ``[(start_s, end_s), ...]`` shape as
``engine.compute_vad_segments()`` so callers can treat it as a drop-in
alternative segmenter.
"""
from __future__ import annotations

import array
import math
import wave
from pathlib import Path

_FRAME_MS = 30  # matches Silero's minimum chunk size


def compute_rms_segments(
    wav_path: Path,
    *,
    rms_threshold: float = 0.05,
    min_speech_ms: int = 250,
    min_silence_ms: int = 100,
    speech_pad_ms: int = 30,
) -> list[tuple[float, float]]:
    """Detect speech regions by per-frame RMS relative to the file's peak RMS.

    A frame counts as speech when ``rms(frame) >= peak_rms * rms_threshold``.
    Consecutive speech frames merge; gaps shorter than ``min_silence_ms``
    are bridged; segments shorter than ``min_speech_ms`` are dropped; the
    survivors are padded by ``speech_pad_ms`` and clamped to file bounds.

    Requires mono 16-bit PCM (what ``audio.ensure_wav()`` always produces).
    Raises ``RuntimeError`` on any other format instead of silently
    downmixing/resampling — same fail-loud convention as the rest of the
    engine.
    """
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise RuntimeError(
                f"rms_energy VAD requires 16-bit PCM, got sampwidth={wf.getsampwidth()}"
            )
        if wf.getnchannels() != 1:
            raise RuntimeError(
                f"rms_energy VAD requires mono audio, got nchannels={wf.getnchannels()}"
            )
        framerate = wf.getframerate()
        frame_len = max(1, int(framerate * _FRAME_MS / 1000))
        samples = array.array("h")
        samples.frombytes(wf.readframes(wf.getnframes()))

    total = len(samples)
    if total == 0:
        return []

    frame_rms: list[float] = []
    for start in range(0, total, frame_len):
        chunk = samples[start:start + frame_len]
        if not chunk:
            break
        mean_sq = sum(s * s for s in chunk) / len(chunk)
        frame_rms.append(math.sqrt(mean_sq))

    peak = max(frame_rms, default=0.0)
    if peak <= 0.0:
        return []  # fully silent file
    threshold = peak * rms_threshold
    is_speech = [r >= threshold for r in frame_rms]

    # ── Merge consecutive speech frames into raw (start_s, end_s) segments ──
    raw: list[tuple[float, float]] = []
    seg_start: int | None = None
    for i, speech in enumerate(is_speech):
        if speech and seg_start is None:
            seg_start = i
        elif not speech and seg_start is not None:
            raw.append((seg_start * frame_len / framerate, i * frame_len / framerate))
            seg_start = None
    if seg_start is not None:
        raw.append((seg_start * frame_len / framerate, total / framerate))
    if not raw:
        return []

    # ── Bridge gaps shorter than min_silence_ms ──
    min_silence_s = min_silence_ms / 1000
    bridged: list[list[float]] = [list(raw[0])]
    for start_s, end_s in raw[1:]:
        if start_s - bridged[-1][1] < min_silence_s:
            bridged[-1][1] = end_s
        else:
            bridged.append([start_s, end_s])

    # ── Drop segments shorter than min_speech_ms ──
    min_speech_s = min_speech_ms / 1000
    kept = [(s, e) for s, e in bridged if (e - s) >= min_speech_s]
    if not kept:
        return []

    # ── Pad + clamp to file bounds ──
    pad_s = speech_pad_ms / 1000
    duration_s = total / framerate
    return [
        (max(0.0, s - pad_s), min(duration_s, e + pad_s))
        for s, e in kept
    ]


if __name__ == "__main__":  # self-check: synthetic tone-then-silence WAV
    import struct
    import tempfile

    def _write_test_wav(path: Path, framerate: int = 16000) -> None:
        # 0.5s silence, 1.0s "speech" (loud sine-ish square wave), 0.5s silence,
        # 0.05s speech blip too short to survive min_speech_ms.
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            silence = struct.pack("<h", 0) * int(0.5 * framerate)
            loud = b"".join(
                struct.pack("<h", 20000 if (i // 20) % 2 == 0 else -20000)
                for i in range(int(1.0 * framerate))
            )
            blip = b"".join(
                struct.pack("<h", 20000 if (i // 20) % 2 == 0 else -20000)
                for i in range(int(0.05 * framerate))
            )
            wf.writeframes(silence + loud + silence + blip + silence)

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "test.wav"
        _write_test_wav(wav_path)

        segments = compute_rms_segments(wav_path, min_speech_ms=250, min_silence_ms=100, speech_pad_ms=0)
        assert len(segments) == 1, f"expected 1 surviving segment (blip dropped), got {segments}"
        start, end = segments[0]
        assert 0.4 < start < 0.6, f"segment start off: {start}"
        assert 1.4 < end < 1.6, f"segment end off: {end}"

        padded = compute_rms_segments(wav_path, min_speech_ms=250, min_silence_ms=100, speech_pad_ms=100)
        p_start, p_end = padded[0]
        assert p_start < start and p_end > end, "padding should widen the segment"
        assert p_start >= 0.0, "padding must clamp at 0"

        silent_path = Path(tmp) / "silent.wav"
        with wave.open(str(silent_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(struct.pack("<h", 0) * 16000)
        assert compute_rms_segments(silent_path) == []

        print("rms_vad self-check: OK")
