"""Configuration loaded from .env (pydantic-settings).

All knobs default to what ``ai4db`` ships, so a fresh clone reproduces
production behavior. Every field is overridable per-run from the UI
(``POST /api/run`` query params), exactly like the sibling ``ocr-benchmark``
project.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from warnings import warn

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # ── Audio ────────────────────────────────────────────────────────────────
    audio_sample_rate: int = 16000
    audio_channels: int = 1

    # ── Whisper / STT engine ─────────────────────────────────────────────────
    # Path to whisper-cli. May be an absolute path, a bare binary name resolved
    # via PATH, or an ssh-prefixed command like "ssh jetson whisper-cli".
    # (Set via env var WHISPER_CLI_CMD.)
    whisper_cli_cmd: str = "whisper-cli"

    # Whisper model file under models/.
    whisper_model: str = "ggml-tiny.id.bin"
    language: str = "id"
    threads: int = 4

    # ── Silero VAD ───────────────────────────────────────────────────────────
    vad_mode: Literal["off", "builtin", "presegmented", "rms_energy"] = "builtin"
    legacy_vad_enabled: bool | None = Field(
        default=None,
        validation_alias="VAD_ENABLED",
        repr=False,
    )
    vad_model_path: str = "ggml-silero-v6.2.0.bin"

    # whisper.cpp VAD tuning knobs. Naming matches the CLI:
    #   --vad-threshold, --vad-min-speech-duration-ms, etc.
    # Float over CLI string so the UI can send numbers from sliders.
    # Shared by rms_energy mode too (min-speech/min-silence/pad), so both
    # segmenters are shaped by the same three knobs — only the detection
    # threshold differs (vad_threshold for Silero, rms_threshold below).
    vad_threshold: float = 0.5
    vad_min_speech_ms: int = 250
    vad_min_silence_ms: int = 100
    vad_speech_pad_ms: int = 30
    vad_max_speech_s: float = 0.0  # 0 = unlimited in whisper.cpp CLI

    # ── RMS-energy VAD (rms_energy mode) ────────────────────────────────────
    # Fraction of the file's peak RMS a frame must reach to count as speech.
    # ponytail: fixed threshold relative to file peak, not an adaptive
    # noise floor — a speaker who gets much quieter mid-clip can fall below
    # it. Upgrade path: rolling-percentile noise floor if that bites.
    rms_threshold: float = 0.05

    # ai4db mirrors this in STTPipeline / config.py; here we just expose it for
    # documentation. whisper-cli's CLI mode doesn't window internally the same
    # way; we transcribe whole-file, so this value is reported but unused.
    vad_window_duration: float = 3.0

    # ── Server ───────────────────────────────────────────────────────────────
    serve_host: str = "127.0.0.1"
    serve_port: int = 8770  # distinct from ocr-benchmark's 8765

    # ── Runner ───────────────────────────────────────────────────────────────
    # Stale lock detection: a run with no status update for this long is
    # assumed dead (one full file transcribe + scoring; well under 5 min).
    run_stale_after_s: int = 600

    # ── Auth ─────────────────────────────────────────────────────────────────
    # HTTP Basic Auth password gating the whole dashboard (any username
    # works). Mirrors the sibling ocr-benchmark project exactly. Override
    # via AUTH_PASSWORD in .env. The browser handles the login prompt —
    # there's no /login page or session token.
    auth_password: str = "AI4DB-BENCH"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def map_legacy_vad_enabled(self) -> Settings:
        if self.legacy_vad_enabled is None:
            return self

        warn(
            "VAD_ENABLED is deprecated; set VAD_MODE to off, builtin, or presegmented instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if "vad_mode" not in self.model_fields_set:
            self.vad_mode = "builtin" if self.legacy_vad_enabled else "off"
        return self

    @property
    def vad_enabled(self) -> bool:
        """Internal convenience for behavior shared by VAD-capable modes."""
        return self.vad_mode != "off"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
