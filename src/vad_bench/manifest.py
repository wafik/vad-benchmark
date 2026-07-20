"""Immutable, reproducible input and environment record for benchmark runs."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import uuid
from pathlib import Path

from .config import Settings
from .paths import HISTORY_ROOT, MODELS_ROOT, PACKAGE_ROOT, PODCAST_WAV, REFERENCE_TXT

_BLOCK_SIZE = 1024 * 1024
_SHELL_CHARS = "|><&;$"


def sha256_file(path: Path) -> str:
    """Return a content hash without loading the whole artifact into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(_BLOCK_SIZE), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict:
    try:
        digest = sha256_file(path)
    except OSError as exc:
        return {"path": str(path), "sha256": None, "sha256_error": f"{type(exc).__name__}: {exc}"}
    return {"path": str(path), "sha256": digest, "sha256_error": None}


def _run_optional(args: list[str]) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            args,
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if result.returncode:
        return None, (result.stderr or result.stdout or f"exit {result.returncode}").strip()
    return result.stdout.strip(), None


def _git_identity() -> dict:
    revision, revision_error = _run_optional(["git", "rev-parse", "HEAD"])
    status, status_error = _run_optional(["git", "status", "--porcelain"])
    errors = [error for error in (revision_error, status_error) if error]
    return {
        "revision": revision,
        "dirty": bool(status) if status is not None else None,
        "error": "; ".join(errors) or None,
    }


def _ram_bytes() -> int | None:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        if os.name != "nt":
            return None
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    return int(status.total_physical) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None


def _host_identity(threads: list[int]) -> dict:
    uname = platform.uname()
    return {
        "os": {"system": uname.system, "release": uname.release, "version": uname.version},
        "cpu": {"machine": uname.machine, "processor": uname.processor, "count": os.cpu_count()},
        "ram_bytes": _ram_bytes(),
        "gpu": None,
        "gpu_error": "unavailable in stdlib-only manifest collection",
        "configured_threads": threads,
    }


def _tool_versions(configs: list[Settings]) -> dict:
    command = configs[0].whisper_cli_cmd.strip() if configs else ""
    if not command or any(char.isspace() for char in command) or any(char in command for char in _SHELL_CHARS):
        return {"whisper_cli": None, "whisper_cli_error": "not queried: configured command requires a shell"}
    version, error = _run_optional([command, "--version"])
    return {"whisper_cli": version, "whisper_cli_error": error}


def snapshot_manifest(
    configs: list[Settings],
    *,
    audio_path: Path | None = None,
    reference_path: Path | None = None,
) -> dict:
    """Capture mutable run identity before benchmark configuration work starts."""
    audio = _file_identity(audio_path or PODCAST_WAV)
    reference = _file_identity(reference_path or REFERENCE_TXT)
    return {
        "git": _git_identity(),
        "host": _host_identity([settings.threads for settings in configs]),
        "tool_versions": _tool_versions(configs),
        "inputs": [
            {
                "audio": audio,
                "reference": reference,
                "whisper_model": _file_identity(MODELS_ROOT / settings.whisper_model),
                "vad_model": _file_identity(MODELS_ROOT / settings.vad_model_path)
                if settings.vad_mode in ("builtin", "presegmented") else None,
            }
            for settings in configs
        ],
    }


def build_manifest(
    run_id: str,
    started_at: str,
    configs: list[Settings],
    records: list[dict],
    *,
    audio_path: Path | None = None,
    reference_path: Path | None = None,
    snapshot: dict | None = None,
) -> dict:
    """Build the complete identity record before it is written once to history."""
    snapshot = snapshot or snapshot_manifest(
        configs,
        audio_path=audio_path,
        reference_path=reference_path,
    )
    entries: list[dict] = []
    for settings, record, inputs in zip(configs, records, snapshot["inputs"]):
        effective_config = settings.model_dump(exclude={"auth_password", "legacy_vad_enabled"})
        effective_config["vad_enabled"] = settings.vad_enabled
        entries.append({
            "config": record.get("config"),
            "vad_mode": settings.vad_mode,
            "effective_config": effective_config,
            "resolved_command": record.get("resolved_command"),
            "inputs": inputs,
            "timing": {
                "total_s": record.get("total_s"),
                "segment_prep_s": record.get("segment_prep_s"),
                "staging_s": record.get("staging_s"),
                "transcription_s": record.get("transcription_s"),
            },
        })
    return {
        "run_id": run_id,
        "started_at": started_at,
        "git": snapshot["git"],
        "reference_quality": "silver",
        "host": snapshot["host"],
        "tool_versions": snapshot["tool_versions"],
        "timing_scope": "first configuration-specific operation through Whisper output availability",
        "configs": entries,
    }


def write_manifest(run_id: str, manifest: dict) -> Path:
    """Persist a manifest exactly once; history artifacts are never mutable."""
    HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
    path = HISTORY_ROOT / f"{run_id}.manifest.json"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8") as destination:
        json.dump(manifest, destination, ensure_ascii=False, indent=2)
        destination.flush()
        os.fsync(destination.fileno())

    try:
        if path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
            else:
                raise FileExistsError(path)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
