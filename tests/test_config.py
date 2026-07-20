"""Settings environment compatibility."""
from pathlib import Path

import pytest

from vad_bench.config import PROJECT_ROOT, Settings


def test_settings_env_file_is_anchored_to_project_root():
    assert Settings.model_config["env_file"] == PROJECT_ROOT / ".env"
    assert PROJECT_ROOT == Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("legacy_value", "expected_mode"), [("false", "off"), ("true", "builtin")])
def test_legacy_vad_enabled_maps_to_mode_when_vad_mode_is_unset(monkeypatch, legacy_value, expected_mode):
    monkeypatch.delenv("VAD_MODE", raising=False)
    monkeypatch.setenv("VAD_ENABLED", legacy_value)

    with pytest.warns(DeprecationWarning, match="VAD_ENABLED"):
        assert Settings().vad_mode == expected_mode


def test_explicit_vad_mode_wins_over_legacy_vad_enabled(monkeypatch):
    monkeypatch.setenv("VAD_ENABLED", "true")
    monkeypatch.setenv("VAD_MODE", "off")

    with pytest.warns(DeprecationWarning, match="VAD_ENABLED"):
        assert Settings().vad_mode == "off"
