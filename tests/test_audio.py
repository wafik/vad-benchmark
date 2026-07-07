"""Smoke tests for audio module — only tests the helpers, not ffmpeg."""
import wave

import pytest

from vad_bench import audio
from vad_bench.audio import ensure_wav, wav_duration
from vad_bench.paths import PODCAST_MP3


def test_ensure_wav_missing_input(tmp_path, monkeypatch):
    # Force a missing input by pointing the constant at a non-existent file.
    fake = tmp_path / "does_not_exist.mp3"
    monkeypatch.setattr(audio, "PODCAST_MP3", fake)
    with pytest.raises(FileNotFoundError):
        ensure_wav()


def test_wav_duration(tmp_path):
    wav_path = tmp_path / "test.wav"
    # Write a 0.5s 16kHz mono silence WAV.
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(b"\x00" * (16000 // 2 * 2))  # 0.5s of 16-bit silence
    assert abs(wav_duration(wav_path) - 0.5) < 1e-3