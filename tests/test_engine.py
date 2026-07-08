"""Engine — covers the cmd-builder without actually invoking whisper-cli."""
import sys
from pathlib import Path

import pytest

from vad_bench.config import Settings
from vad_bench.engine import _resolve_cmd


def test_cmd_with_vad(tmp_path):
    s = Settings(vad_enabled=True)
    cmd, use_shell = _resolve_cmd("whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", s)
    assert use_shell is False
    assert isinstance(cmd, list)
    assert "--vad" in cmd
    assert "--vad-model" in cmd
    # --no-timestamps intentionally omitted so the VAD breakdown tab can
    # render per-region timelines from the bracketed timestamps.
    assert "--no-timestamps" not in cmd


def test_cmd_without_vad(tmp_path):
    s = Settings(vad_enabled=False)
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", None, tmp_path / "a.wav", s)
    assert "--vad" not in cmd


def test_cmd_with_ssh_prefix(tmp_path):
    """WHISPER_CLI_CMD can be a shell command (e.g. ssh-based)."""
    s = Settings()
    cmd, use_shell = _resolve_cmd(
        "ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'",
        tmp_path / "m.bin",
        tmp_path / "v.bin",
        tmp_path / "a.wav",
        s,
    )
    assert use_shell is True
    assert isinstance(cmd, str)
    assert "ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'" in cmd
    assert "--vad" in cmd


def test_default_vad_flags_omitted(tmp_path):
    """whisper.cpp has sensible VAD defaults — don't pass them when they match."""
    s = Settings(
        vad_enabled=True,
        vad_threshold=0.5,
        vad_min_speech_ms=250,
        vad_min_silence_ms=100,
        vad_speech_pad_ms=30,
        vad_max_speech_s=0.0,
    )
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", s)
    assert "--vad" in cmd
    assert "--vad-model" in cmd
    for flag in ("--vad-threshold", "--vad-min-speech-duration-ms", "--vad-min-silence-duration-ms",
                 "--vad-speech-pad-ms", "--vad-max-speech-duration-s"):
        assert flag not in cmd, f"unexpectedly included {flag}"


def test_nondefault_vad_threshold_included(tmp_path):
    s = Settings(vad_enabled=True, vad_threshold=0.7)
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", s)
    assert "--vad-threshold" in cmd
    idx = cmd.index("--vad-threshold")
    assert cmd[idx + 1] == "0.7"


def test_empty_cmd_rejected(tmp_path):
    s = Settings()
    import pytest
    with pytest.raises(RuntimeError):
        _resolve_cmd("", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", s)


def test_parse_progress_extracts_vad_reduction():
    from vad_bench.engine import _parse_progress
    stderr = (
        "whisper_vad: VAD is enabled, processing speech segments only\n"
        "whisper_vad_init_with_params: model type: silero-16k\n"
        "whisper_vad: Reduced audio from 9778387 to 8352640 samples (14.6% reduction)\n"
        "whisper_print_progress_callback: progress =  50%\n"
    )
    silence_removed, speech_seconds = _parse_progress(stderr, audio_duration_s=611.149)
    # Real reduction = (9778387 - 8352640) / 9778387 = 0.1458…
    assert silence_removed == pytest.approx(0.1458, abs=1e-3)
    # 14.58% removed → 85.42% kept → 611.149 * 0.8542 ≈ 522.1s
    assert speech_seconds == pytest.approx(611.149 * (8352640 / 9778387), abs=0.01)


def test_parse_progress_missing_line_returns_none():
    from vad_bench.engine import _parse_progress
    silence_removed, speech_seconds = _parse_progress("", audio_duration_s=10.0)
    assert silence_removed is None
    assert speech_seconds is None


def test_parse_segments_extracts_bracketed_lines():
    from vad_bench.engine import _parse_segments
    stdout = (
        "[00:00:00.000 --> 00:00:08.500]  Halo semua, hari ini kita bicara.\n"
        "[00:00:08.500 --> 00:00:14.000]  Topik kita adalah AI.\n"
        "non-timestamped line that should be ignored\n"
        "[00:00:14.000 --> 00:00:20.250]  Silakan disimak.\n"
    )
    segs = _parse_segments(stdout)
    assert len(segs) == 3, segs
    assert segs[0][0] == 0.0 and segs[0][1] == 8.5
    assert segs[1][0] == 8.5 and segs[1][1] == 14.0
    assert "Halo semua" in segs[0][2]
    assert "Silakan disimak" in segs[2][2]


def test_parse_segments_empty_input():
    from vad_bench.engine import _parse_segments
    assert _parse_segments("") == []
    assert _parse_segments(None) == []  # type: ignore[arg-type] — None is allowed by the parser


if __name__ == "__main__":  # self-check
    pass