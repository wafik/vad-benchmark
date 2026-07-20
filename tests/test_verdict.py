"""Verdicts are allowed only for an explicit, equivalent comparison pair."""
from vad_bench.config import Settings
from vad_bench.verdict import build_verdict


def _comparable_records(control_rtf=0.5, candidate_rtf=1.0):
    settings = {
        **Settings().model_dump(exclude={"auth_password"}),
        "legacy_vad_enabled": None,
        "whisper_model": "tiny.bin",
        "language": "id",
        "threads": 4,
    }
    return [
        {"config": "off", "vad_mode": "off", "rtf": control_rtf, "effective_settings": dict(settings)},
        {"config": "on", "vad_mode": "builtin", "rtf": candidate_rtf, "effective_settings": dict(settings)},
    ]


def test_verdict_requires_named_comparable_pair():
    assert build_verdict(_comparable_records(), None, None) is None


def test_verdict_reports_candidate_over_control_slowdown():
    verdict = build_verdict(_comparable_records(), "off", "on")

    assert "2.00x" in verdict


def test_verdict_rejects_named_pair_in_a_sweep():
    records = _comparable_records()
    records.append({
        "config": "third",
        "vad_mode": "builtin",
        "rtf": 0.75,
        "effective_settings": records[0]["effective_settings"],
    })

    assert build_verdict(records, "off", "on") is None


def test_verdict_rejects_different_effective_settings():
    records = _comparable_records()
    records[1]["effective_settings"] = {**records[1]["effective_settings"], "threads": 8}

    assert build_verdict(records, "off", "on") is None


def test_verdict_rejects_missing_required_effective_setting():
    records = _comparable_records()
    for record in records:
        del record["effective_settings"]["legacy_vad_enabled"]

    assert build_verdict(records, "off", "on") is None


def test_verdict_compares_all_settings_in_fallback_records():
    control_settings = {**Settings().model_dump(), "vad_mode": "off"}
    candidate_settings = {**control_settings, "vad_mode": "builtin", "audio_channels": 2}
    records = [
        {"config": "off", "vad_mode": "off", "rtf": 0.5, **control_settings},
        {"config": "on", "vad_mode": "builtin", "rtf": 1.0, **candidate_settings},
    ]

    assert build_verdict(records, "off", "on") is None


def test_verdict_ignores_non_settings_runtime_metadata():
    records = _comparable_records()
    records[0]["effective_settings"] = {**records[0]["effective_settings"], "run_id": "one"}
    records[1]["effective_settings"] = {**records[1]["effective_settings"], "run_id": "two"}

    assert build_verdict(records, "off", "on") is not None


def test_verdict_excludes_auth_password_and_vad_mode_only():
    control_settings = Settings(auth_password="control-secret").model_dump()
    candidate_settings = {**control_settings, "auth_password": "candidate-secret"}
    records = [
        {"config": "off", "vad_mode": "off", "rtf": 0.5, "effective_settings": control_settings},
        {"config": "on", "vad_mode": "builtin", "rtf": 1.0, "effective_settings": candidate_settings},
    ]

    assert build_verdict(records, "off", "on") is not None
