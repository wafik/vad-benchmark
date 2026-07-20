"""RMS-energy VAD segmenter."""
import struct
import wave

from vad_bench.rms_vad import compute_rms_segments


def _tone(n_frames: int) -> bytes:
    return b"".join(
        struct.pack("<h", 20000 if (i // 20) % 2 == 0 else -20000)
        for i in range(n_frames)
    )


def _write_wav(path, framerate: int, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(pcm)


def test_detects_loud_region_and_drops_short_blip(tmp_path):
    fr = 16000
    silence = struct.pack("<h", 0) * int(0.5 * fr)
    loud = _tone(int(1.0 * fr))
    blip = _tone(int(0.05 * fr))  # shorter than min_speech_ms, must be dropped
    path = tmp_path / "test.wav"
    _write_wav(path, fr, silence + loud + silence + blip + silence)

    segments = compute_rms_segments(
        path, min_speech_ms=250, min_silence_ms=100, speech_pad_ms=0,
    )

    assert len(segments) == 1
    start, end = segments[0]
    assert 0.4 < start < 0.6
    assert 1.4 < end < 1.6


def test_padding_widens_segment_and_clamps_at_file_start(tmp_path):
    fr = 16000
    loud = _tone(int(1.0 * fr))
    silence = struct.pack("<h", 0) * int(0.5 * fr)
    path = tmp_path / "test.wav"
    _write_wav(path, fr, loud + silence)

    unpadded = compute_rms_segments(path, min_speech_ms=250, min_silence_ms=100, speech_pad_ms=0)
    padded = compute_rms_segments(path, min_speech_ms=250, min_silence_ms=100, speech_pad_ms=200)

    assert padded[0][0] == 0.0  # clamped, can't go below file start
    assert padded[0][1] > unpadded[0][1]  # end padded outward


def test_silent_file_returns_no_segments(tmp_path):
    path = tmp_path / "silent.wav"
    _write_wav(path, 16000, struct.pack("<h", 0) * 16000)

    assert compute_rms_segments(path) == []


def test_rejects_stereo_input(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(struct.pack("<hh", 0, 0) * 16000)

    try:
        compute_rms_segments(path)
        assert False, "expected RuntimeError for stereo input"
    except RuntimeError as exc:
        assert "mono" in str(exc)
