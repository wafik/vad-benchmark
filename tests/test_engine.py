"""Engine — covers the cmd-builder without actually invoking whisper-cli."""
import hashlib
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from vad_bench.config import Settings
from vad_bench.engine import _resolve_cmd, compute_vad_segments, transcribe


def test_cmd_with_vad(tmp_path):
    s = Settings(vad_mode="builtin")
    cmd, use_shell = _resolve_cmd("whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", s)
    assert use_shell is False
    assert isinstance(cmd, list)
    assert "--vad" in cmd
    assert "--vad-model" in cmd
    # --no-timestamps intentionally omitted so the VAD breakdown tab can
    # render per-region timelines from the bracketed timestamps.
    assert "--no-timestamps" not in cmd


def test_cmd_without_vad(tmp_path):
    s = Settings(vad_mode="off")
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", None, tmp_path / "a.wav", s)
    assert "--vad" not in cmd


def test_off_mode_omits_whisper_vad_flags(tmp_path):
    s = Settings(vad_mode="off")
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", None, tmp_path / "a.wav", s)
    assert s.vad_mode == "off"
    assert "--vad" not in cmd


def test_presegmented_mode_never_adds_whisper_vad_flags(tmp_path):
    s = Settings(vad_mode="presegmented")
    cmd, _ = _resolve_cmd(
        "whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", s
    )
    assert s.vad_mode == "presegmented"
    assert "--vad" not in cmd


def test_presegmented_mode_rejects_empty_segments_before_whisper(tmp_path):
    settings = Settings(vad_mode="presegmented", whisper_cli_cmd="not-called")
    (tmp_path / settings.whisper_model).write_bytes(b"stub")
    (tmp_path / settings.vad_model_path).write_bytes(b"stub")

    with pytest.raises(RuntimeError, match="presegmented mode produced no speech segments"):
        transcribe(
            tmp_path / "audio.wav",
            config="segments",
            settings=settings,
            models_root=tmp_path,
            vad_segments=[],
        )


def test_rms_energy_mode_never_adds_whisper_vad_flags(tmp_path):
    s = Settings(vad_mode="rms_energy")
    cmd, _ = _resolve_cmd(
        "whisper-cli", tmp_path / "m.bin", None, tmp_path / "a.wav", s
    )
    assert s.vad_mode == "rms_energy"
    assert "--vad" not in cmd


def test_rms_energy_mode_needs_no_silero_model(tmp_path):
    # rms_energy is pure Python — it must not require ggml-silero-*.bin to
    # exist, unlike builtin/presegmented which shell out to a Silero-backed
    # binary. Reaching the "no speech segments" error (not a missing-model
    # FileNotFoundError) proves the Silero-model check was skipped.
    settings = Settings(vad_mode="rms_energy", whisper_cli_cmd="not-called")
    (tmp_path / settings.whisper_model).write_bytes(b"stub")

    with pytest.raises(RuntimeError, match="rms_energy mode produced no speech segments"):
        transcribe(
            tmp_path / "audio.wav",
            config="segments",
            settings=settings,
            models_root=tmp_path,
            vad_segments=[],
        )


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


def test_tab_delimited_ssh_command_uses_shell(tmp_path):
    s = Settings()
    cmd, use_shell = _resolve_cmd(
        "ssh\tjetson\t'whisper.cpp/build/bin/whisper-cli'",
        tmp_path / "m.bin",
        tmp_path / "v.bin",
        tmp_path / "a.wav",
        s,
    )

    assert use_shell is True
    assert isinstance(cmd, str)


def test_remote_segmenter_stages_wav_and_vad_model(tmp_path, monkeypatch):
    wav_path = tmp_path / "audio.wav"
    vad_model_path = tmp_path / "vad.bin"
    wav_path.write_bytes(b"wav")
    vad_model_path.write_bytes(b"vad")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout="Speech segment 0: start = 0.00, end = 100.00\n",
            stderr="",
        )

    monkeypatch.setattr("vad_bench.engine.subprocess.run", fake_run)
    clock = iter([10.0, 11.0, 12.0, 15.0])
    monkeypatch.setattr("vad_bench.engine.time.perf_counter", lambda: next(clock))
    timings = {}
    segments = compute_vad_segments(
        wav_path,
        vad_model_path,
        Settings(),
        cmd="ssh\tjetson\t'whisper-vad-speech-segments'",
        timings=timings,
    )

    def remote_path(path):
        digest = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:10]
        return f"/tmp/vad-bench-scratch/{digest}_{path.name}"

    remote_wav = remote_path(wav_path)
    remote_vad = remote_path(vad_model_path)
    assert segments == [(0.0, 1.0)]
    assert timings == {"staging_s": 1.0, "segment_prep_s": 3.0}
    assert [command for command, _ in calls[:3]] == [
        ["ssh", "-o", "BatchMode=yes", "jetson", "mkdir -p /tmp/vad-bench-scratch"],
        ["scp", "-q", wav_path.as_posix(), f"jetson:{remote_wav}"],
        ["scp", "-q", vad_model_path.as_posix(), f"jetson:{remote_vad}"],
    ]
    segment_cmd = calls[3][0]
    assert remote_wav in segment_cmd
    assert remote_vad in segment_cmd


def test_remote_presegmented_transcription_stages_whisper_model(tmp_path, monkeypatch):
    settings = Settings(
        vad_mode="presegmented",
        whisper_cli_cmd="ssh jetson 'whisper-cli'",
    )
    model_path = tmp_path / settings.whisper_model
    vad_model_path = tmp_path / settings.vad_model_path
    model_path.write_bytes(b"model")
    vad_model_path.write_bytes(b"vad")
    wav_path = tmp_path / "audio.wav"
    with wave.open(str(wav_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16_000)
        out.writeframes(b"\0\0" * 1_600)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("vad_bench.engine.subprocess.run", fake_run)
    transcribe(
        wav_path,
        config="segments",
        settings=settings,
        models_root=tmp_path,
        vad_segments=[(0.0, 0.1)],
    )

    digest = hashlib.sha1(str(model_path.resolve()).encode()).hexdigest()[:10]
    remote_model = f"/tmp/vad-bench-scratch/{digest}_{model_path.name}"
    assert ["scp", "-q", model_path.as_posix(), f"jetson:{remote_model}"] in [
        command for command, _ in calls
    ]
    whisper_cmd = next(
        command
        for command, _ in calls
        if isinstance(command, str) and command.startswith(settings.whisper_cli_cmd)
    )
    assert remote_model in whisper_cmd


def test_builtin_no_speech_returns_empty_result_before_cleanup(tmp_path, monkeypatch):
    settings = Settings(vad_mode="builtin", whisper_cli_cmd=str(tmp_path / "whisper-cli"))
    (tmp_path / "whisper-cli").write_bytes(b"")
    (tmp_path / settings.whisper_model).write_bytes(b"model")
    (tmp_path / settings.vad_model_path).write_bytes(b"vad")
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"wav")
    monkeypatch.setattr(
        "vad_bench.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="failed to process audio"
        ),
    )
    clock = iter([10.0, 12.0])
    monkeypatch.setattr("vad_bench.engine.time.perf_counter", lambda: next(clock))
    output_ready = []

    result = transcribe(
        wav_path,
        config="builtin",
        settings=settings,
        models_root=tmp_path,
        on_output_ready=lambda: output_ready.append(True),
    )

    assert output_ready == [True]
    assert result.transcript == ""
    assert result.transcription_s == 2.0


def test_default_vad_flags_omitted(tmp_path):
    """whisper.cpp has sensible VAD defaults — don't pass them when they match."""
    s = Settings(
        vad_mode="builtin",
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
    s = Settings(vad_mode="builtin", vad_threshold=0.7)
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


def test_local_transcription_reports_invocation_time_without_staging(tmp_path, monkeypatch):
    cli_path = tmp_path / "whisper-cli"
    cli_path.write_bytes(b"")
    settings = Settings(vad_mode="off", whisper_cli_cmd=str(cli_path))
    (tmp_path / settings.whisper_model).write_bytes(b"model")
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"wav")
    monkeypatch.setattr(
        "vad_bench.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="halo", stderr=""),
    )
    clock = iter([10.0, 12.0])
    monkeypatch.setattr("vad_bench.engine.time.perf_counter", lambda: next(clock))

    result = transcribe(
        wav_path,
        config="off",
        settings=settings,
        models_root=tmp_path,
    )

    assert result.staging_s == 0.0
    assert result.transcription_s == 2.0


def test_local_presegmented_output_timing_precedes_region_cleanup(tmp_path, monkeypatch):
    import vad_bench.engine as engine

    cli_path = tmp_path / "whisper-cli"
    cli_path.write_bytes(b"")
    settings = Settings(vad_mode="presegmented", whisper_cli_cmd=str(cli_path))
    (tmp_path / settings.whisper_model).write_bytes(b"model")
    (tmp_path / settings.vad_model_path).write_bytes(b"vad")
    wav_path = tmp_path / "audio.wav"
    with wave.open(str(wav_path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16_000)
        out.writeframes(b"\0\0" * 1_600)

    monkeypatch.setattr(
        engine.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="halo", stderr=""),
    )
    clock = iter([10.0, 11.0, 13.0, 14.0, 99.0])
    monkeypatch.setattr(engine.time, "perf_counter", lambda: next(clock))
    cleanup_started = []
    total_s = None
    original_rmtree = engine.shutil.rmtree

    config_started = engine.time.perf_counter()

    def capture_output_time():
        nonlocal total_s
        total_s = engine.time.perf_counter() - config_started

    def cleanup_region_dir(path, **kwargs):
        assert total_s == 4.0
        assert path.exists()
        cleanup_started.append(engine.time.perf_counter())
        return original_rmtree(path, **kwargs)

    monkeypatch.setattr(engine.shutil, "rmtree", cleanup_region_dir)

    result = transcribe(
        wav_path,
        config="segments",
        settings=settings,
        models_root=tmp_path,
        vad_segments=[(0.0, 0.1)],
        on_output_ready=capture_output_time,
    )

    assert result.transcription_s == 2.0
    assert total_s == 4.0
    assert cleanup_started == [99.0]


def test_remote_transcription_reports_staging_and_invocation_time(tmp_path, monkeypatch):
    settings = Settings(vad_mode="builtin", whisper_cli_cmd="ssh jetson 'whisper-cli'")
    (tmp_path / settings.whisper_model).write_bytes(b"model")
    (tmp_path / settings.vad_model_path).write_bytes(b"vad")
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"wav")
    monkeypatch.setattr(
        "vad_bench.engine.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="halo", stderr=""),
    )
    clock = iter([10.0, 11.0, 20.0, 23.0])
    monkeypatch.setattr("vad_bench.engine.time.perf_counter", lambda: next(clock))

    result = transcribe(
        wav_path,
        config="builtin",
        settings=settings,
        models_root=tmp_path,
    )

    assert result.staging_s == 1.0
    assert result.transcription_s == 3.0


if __name__ == "__main__":  # self-check
    pass
