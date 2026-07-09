"""Audio prep: mp3 → 16 kHz mono WAV via ffmpeg (cached).

Mirrors ``ai4db``'s contract: float32 PCM / 16 kHz / mono. We write int16 WAV
here because that's what whisper-cli's ``-f`` expects; ``audio_capture.py``
in ai4db writes a temp int16 WAV too.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import wave
from pathlib import Path

from .paths import PODCAST_MP3, PODCAST_WAV, ffmpeg_path


def ensure_wav() -> Path:
    """Decode ``PODCAST_MP3`` to 16 kHz mono int16 ``PODCAST_WAV``.

    Idempotent: skips ffmpeg if the wav exists and is newer than the mp3.
    Raises FileNotFoundError with a clear message if mp3 is missing or
    ffmpeg is unavailable.
    """
    if not PODCAST_MP3.exists():
        raise FileNotFoundError(
            f"missing input audio: {PODCAST_MP3}. "
            f"Drop your podcast.mp3 into data/."
        )
    if PODCAST_WAV.exists() and PODCAST_WAV.stat().st_mtime >= PODCAST_MP3.stat().st_mtime:
        return PODCAST_WAV

    bin_ = ffmpeg_path()
    if not shutil.which(bin_) and not Path(bin_).exists():
        raise FileNotFoundError(
            f"ffmpeg not found. Install with `winget install Gyan.FFmpeg` or set "
            f"FFMPEG_BIN=/path/to/ffmpeg.exe. Resolved: {bin_!r}"
        )
    PODCAST_WAV.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg on Windows under Git Bash / MSYS chokes on ``C:\…`` style paths
    # — backslashes get treated as escapes. Convert paths to POSIX form for
    # the ffmpeg invocation. This also plays nicely with the WAV being read
    # back on the same host.
    def _pp(p: Path) -> str:
        return p.as_posix() if sys.platform == "win32" else str(p)

    cmd = [
        bin_,
        "-y",
        "-i", _pp(PODCAST_MP3),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        _pp(PODCAST_WAV),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (rc={result.returncode}): {result.stderr.strip()[-500:]}"
        )
    return PODCAST_WAV


def wav_duration(path: Path) -> float:
    """Seconds of audio in a WAV file (reads RIFF header, no decoding)."""
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def slice_wav_segments(
    src: Path,
    segments: list[tuple[float, float, str]],
    out_dir: Path,
) -> None:
    """Slice ``src`` into one WAV file per ``(start_s, end_s, text)`` segment.

    Stdlib ``wave`` only — no ffmpeg subprocess per chunk. ``src`` is already
    16 kHz mono PCM16 (exactly what whisper-cli consumed), so raw frame
    slicing is enough. Output files are named ``NNNN.wav`` (zero-padded
    index, matching segment order) in ``out_dir``, created if missing.
    No-op (no directory created) when ``segments`` is empty.
    """
    if not segments:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    with wave.open(str(src), "rb") as wf:
        framerate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        nchannels = wf.getnchannels()
        for index, (start_s, end_s, _text) in enumerate(segments):
            start_frame = int(start_s * framerate)
            n_frames = int((end_s - start_s) * framerate)
            wf.setpos(start_frame)
            frames = wf.readframes(n_frames)
            out_path = out_dir / f"{index:04d}.wav"
            with wave.open(str(out_path), "wb") as out:
                out.setnchannels(nchannels)
                out.setsampwidth(sampwidth)
                out.setframerate(framerate)
                out.writeframes(frames)