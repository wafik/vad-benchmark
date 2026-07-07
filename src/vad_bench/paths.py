"""Shared paths for the vad_bench package."""
from __future__ import annotations

import os
from pathlib import Path

# src/vad_bench/paths.py → src/vad_bench/ → src/ → package root
PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_ROOT = PACKAGE_ROOT / "data"
MODELS_ROOT = PACKAGE_ROOT / "models"
REPORTS_ROOT = PACKAGE_ROOT / "reports"
HISTORY_ROOT = REPORTS_ROOT / "history"
UI_ROOT = PACKAGE_ROOT / "ui"
TESTS_ROOT = PACKAGE_ROOT / "tests"

# Audio / reference artifacts derived from data/.
PODCAST_MP3 = DATA_ROOT / "podcast.mp3"
PODCAST_WAV = DATA_ROOT / "podcast_16k.wav"
REFERENCE_TXT = DATA_ROOT / "text_podcast.txt"


def ffmpeg_path() -> str:
    """Return the path to ``ffmpeg``.

    Honours ``FFMPEG_BIN`` if set (typical use: a non-PATH portable install
    like Gyan.FFmpeg unpacked by winget). Otherwise falls back to the system
    ``ffmpeg`` on PATH.
    """
    override = os.environ.get("FFMPEG_BIN", "").strip()
    if override:
        return override
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    # Last-resort: default winget path on Windows. Lets the dashboard still
    # work even when PATH wasn't refreshed after winget install.
    winget = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    )
    if winget.exists():
        for p in winget.rglob("ffmpeg.exe"):
            return str(p)
    return "ffmpeg"  # subprocess will raise FileNotFoundError with a useful message