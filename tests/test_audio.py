"""Smoke tests for audio module — only tests the helpers, not ffmpeg."""
import wave

import pytest

from vad_bench import audio
from vad_bench.audio import ensure_wav, slice_wav_segments, wav_duration
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


def test_slice_wav_segments(tmp_path):
    src = tmp_path / "src.wav"
    framerate = 16000
    total_s = 2.0
    n_frames = int(framerate * total_s)
    with wave.open(str(src), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x01" * n_frames)  # 2 bytes/frame, non-zero pattern

    out_dir = tmp_path / "chunks"
    segments = [(0.0, 0.5, "halo"), (1.0, 1.5, "dunia")]
    slice_wav_segments(src, segments, out_dir)

    files = sorted(out_dir.glob("*.wav"))
    assert [f.name for f in files] == ["0000.wav", "0001.wav"]

    with wave.open(str(files[0]), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == framerate
        assert wf.getnframes() == int(0.5 * framerate)

    with wave.open(str(files[1]), "rb") as wf:
        assert wf.getnframes() == int(0.5 * framerate)


def test_slice_wav_segments_empty_list_is_noop(tmp_path):
    src = tmp_path / "src.wav"
    with wave.open(str(src), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(b"\x00" * 3200)

    out_dir = tmp_path / "chunks"
    slice_wav_segments(src, [], out_dir)
    assert not out_dir.exists()