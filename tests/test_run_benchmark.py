"""CLI config parsing and runner handoff."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import run_benchmark
from vad_bench.runner import _vad_binary_cmd


def test_parse_config_keeps_name_as_metadata():
    parsed = run_benchmark._parse_kv_spec(
        "name=segments,vad_mode=presegmented,vad_threshold=0.7"
    )

    assert parsed == {
        "name": "segments",
        "vad_mode": "presegmented",
        "vad_threshold": "0.7",
    }


def test_main_passes_name_separately_from_settings_overrides(monkeypatch):
    received = []
    monkeypatch.setattr(
        run_benchmark,
        "run_benchmark",
        lambda configs, **_kwargs: received.extend(configs) or {},
    )

    assert run_benchmark.main([
        "--config",
        "name=baseline,vad_mode=off",
    ]) == 0

    assert received == [{"name": "baseline", "overrides": {"vad_mode": "off"}}]


def test_vad_binary_cmd_recognizes_tab_delimited_ssh_command():
    assert _vad_binary_cmd(
        "ssh\tjetson\t'whisper.cpp/build/bin/whisper-cli'"
    ) == "ssh\tjetson\t'whisper.cpp/build/bin/whisper-vad-speech-segments'"
