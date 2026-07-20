"""Verdicts for explicit, like-for-like VAD comparisons."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

from .config import Settings

_REQUIRED_SETTINGS_KEYS = frozenset(Settings.model_fields) - {"auth_password", "vad_mode"}


def _effective_settings(record: dict) -> dict | None:
    settings = record.get("effective_settings")
    if isinstance(settings, Mapping):
        source = settings
    else:
        source = record
    if not _REQUIRED_SETTINGS_KEYS.issubset(source):
        return None
    return {key: source[key] for key in _REQUIRED_SETTINGS_KEYS}


def build_verdict(
    records: Iterable[dict],
    control_name: str | None = None,
    candidate_name: str | None = None,
) -> str | None:
    """Return a recommendation only for one named, comparable pair."""
    records = list(records)
    if len(records) != 2:
        return None
    if not control_name or not candidate_name or control_name == candidate_name:
        return None

    by_name = {record.get("config"): record for record in records}
    control = by_name.get(control_name)
    candidate = by_name.get(candidate_name)
    if control is None or candidate is None:
        return None

    control_settings = _effective_settings(control)
    candidate_settings = _effective_settings(candidate)
    if control_settings is None or control_settings != candidate_settings:
        return None

    parts = [
        f"Membandingkan {control_name} (VAD {control.get('vad_mode')}) vs "
        f"{candidate_name} (VAD {candidate.get('vad_mode')})."
    ]
    control_rtf = control.get("rtf")
    candidate_rtf = candidate.get("rtf")
    if isinstance(control_rtf, (int, float)) and isinstance(candidate_rtf, (int, float)) and control_rtf > 0:
        factor = candidate_rtf / control_rtf
        parts.append(
            f"RTF kandidat/kontrol: {factor:.2f}x "
            f"({control_rtf:.3f} -> {candidate_rtf:.3f})."
        )

    control_wer = control.get("wer")
    candidate_wer = candidate.get("wer")
    if isinstance(control_wer, (int, float)) and isinstance(candidate_wer, (int, float)):
        if candidate_wer <= control_wer:
            parts.append("Rekomendasi: gunakan kandidat untuk perbandingan ini.")
        else:
            parts.append("Rekomendasi: gunakan kontrol untuk perbandingan ini.")

    return " ".join(parts)
