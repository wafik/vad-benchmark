"""Whisper engine — wraps the ``whisper-cli`` subprocess.

Mirrors ``ai4db``'s ``stt/whisper_bridge.py`` almost line-for-line:

    whisper-cli -m <model> -f <wav> -l <lang> -t <threads> \\
        --no-prints --no-timestamps \\
        [--vad --vad-model <silero.bin> \\
         --vad-threshold <t> --vad-min-speech-duration-ms <ms> ...]

The CLI runs as a normal subprocess, so ``WHISPER_CLI_CMD`` can be a bare
binary on PATH, an absolute path, or any shell command — including
``ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'`` for the Windows
dev host that has no local build.

whisper.cpp emits ``failed to process audio`` on stderr when VAD filters
out every segment. We treat that as empty transcription (matches ai4db's
``whisper_bridge._NO_SPEECH_MARKER`` handler) so a 30-min silent input
doesn't crash the WS session — or here, the benchmark.
"""
from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings

log = logging.getLogger(__name__)

_NO_SPEECH_MARKER = "failed to process audio"

# whisper-cli (with --print-progress) emits per-segment progress lines like:
#   whisper_print_progress_callback: progress =  11%
# and one VAD summary line:
#   whisper_vad: Reduced audio from 9778387 to 8352640 samples (14.6% reduction)
# and (when --no-timestamps is OFF) one segment line per region:
#   [00:00:00.000 --> 00:00:08.500]  Halo semua, hari ini kita...
_VAD_REDUCTION_RE = re.compile(
    r"Reduced audio from (\d+) to (\d+) samples \(([\d.]+)% reduction\)"
)
_SEGMENT_RE = re.compile(
    r"\[(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*)"
)


@dataclass
class EngineResult:
    config: str
    vad_enabled: bool
    transcript: str
    runtime_s: float
    # Set when the whisper-cli stderr contained a VAD reduction line.
    # None for the no-VAD run.
    silence_removed: float | None
    speech_seconds: float | None
    cmd: list[str] | str
    raw_stdout: str
    raw_stderr: str
    # Per-segment (start_s, end_s, text) from the timestamped whisper-cli
    # output. Empty when --no-timestamps was on or parsing failed.
    segments: list[tuple[float, float, str]] = field(default_factory=list)


def _hms_to_s(hms: str) -> float:
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


# Kept for future use — parsing per-segment timing text when whisper-cli runs
# without --no-timestamps. Currently the runner uses --no-timestamps + --print-progress
# instead, so we extract silence stats from the VAD reduction line above.
def _parse_segments_legacy(_stderr: str, _stdout: str) -> str:
    """Deprecated. Returns the bare stdout transcript."""
    return (_stdout or "").strip()


def _parse_segments(stdout: str) -> list[tuple[float, float, str]]:
    """Parse per-region segments from a timestamped whisper-cli output.

    The CLI prints one line per detected region::

        [00:00:00.000 --> 00:00:08.500]  Halo semua, hari ini kita...

    Returns ``[(start_s, end_s, text), ...]``. Lines that don't match the
    bracket format are silently skipped (whisper-cli can also print
    non-timestamped text in some configurations). Empty list on failure.
    """
    if not stdout:
        return []
    out: list[tuple[float, float, str]] = []
    for line in stdout.splitlines():
        m = _SEGMENT_RE.search(line)
        if not m:
            continue
        try:
            start = _hms_to_s(m.group(1))
            end = _hms_to_s(m.group(2))
        except ValueError:
            continue
        if end < start:
            continue
        text = m.group(3).strip()
        out.append((start, end, text))
    return out


def _parse_progress(stderr: str, audio_duration_s: float) -> tuple[float | None, float | None]:
    """Pull VAD reduction stats out of ``whisper_print_progress`` output.

    Returns ``(silence_removed, speech_seconds)`` where each is ``None`` if
    the line wasn't present. ``silence_removed`` is a fraction in [0, 1];
    ``speech_seconds`` is the absolute duration of the kept speech.

    whisper.cpp's line format::

        whisper_vad: Reduced audio from N to M samples (P% reduction)

    where ``reduction = (N - M) / N``. We expose both forms so the runner
    and UI can pick whichever it wants.
    """
    if not stderr:
        return None, None
    m = _VAD_REDUCTION_RE.search(stderr)
    if not m:
        return None, None
    n_str, m_str, pct_str = m.groups()
    n_samples = int(n_str)
    m_samples = int(m_str)
    if n_samples <= 0:
        return None, None
    kept_fraction = m_samples / n_samples
    reduced_fraction = 1.0 - kept_fraction
    speech_seconds = kept_fraction * audio_duration_s if audio_duration_s > 0 else None
    return reduced_fraction, speech_seconds


def _resolve_cmd(cmd_str: str, model_path: Path, vad_model_path: Path | None,
                 wav_path: Path, s: Settings) -> tuple[list[str] | str, bool]:
    """Turn the configured ``WHISPER_CLI_CMD`` into a final command + shell flag.

    Two modes:
      - **direct binary** (no spaces): returned as a list, invoked without a
        shell. Validated up-front for a friendly FileNotFoundError.
      - **shell command** (contains spaces or shell operators): returned as a
        single string with the flags appended; invoked with ``shell=True`` so
        the platform shell parses it. This is how a Windows dev host can
        transparently use a Linux whisper-cli on the Jetson via SSH.

    Returns ``(command, use_shell)``.
    """
    flags = _whisper_flags(model_path, vad_model_path, wav_path, s)

    if not cmd_str or not cmd_str.strip():
        raise RuntimeError("WHISPER_CLI_CMD is empty")

    # Heuristic: if the value has no spaces and no shell operators, treat it as
    # a bare binary / absolute path. Otherwise it's a shell command.
    looks_like_shell = (
        " " in cmd_str
        or any(op in cmd_str for op in ("|", ">", "<", "&", ";", "$"))
    )

    if not looks_like_shell:
        tokens = [cmd_str] + flags
        return tokens, False

    # Shell mode — append the flags as a single quoted tail. Using shlex.join
    # makes the quoting portable across POSIX shells and cmd.exe enough for our
    # SSH-style use cases (where the *remote* command is what matters).
    return f"{cmd_str} {' '.join(shlex.quote(f) for f in flags)}", True


def _whisper_flags(model_path: Path, vad_model_path: Path | None,
                   wav_path: Path, s: Settings) -> list[str]:
    """Build the whisper-cli flag list (model/audio/VAD knobs).

    Paths are emitted as POSIX (``/…``) form when running on Windows, so the
    SSH transport doesn't strip backslashes. whisper-cli accepts forward
    slashes on every platform.
    """
    def _pp(p: Path) -> str:
        return p.as_posix()

    flags = [
        "-m", _pp(model_path),
        "-f", _pp(wav_path),
        "-l", s.language,
        "-t", str(s.threads),
        # Note: --no-timestamps intentionally omitted so the VAD breakdown
        # tab can render per-region timelines. The transcript still goes to
        # stdout, prefixed with [HH:MM:SS.mmm --> HH:MM:SS.mmm] markers.
        # Always request progress to stderr — we extract the VAD-reduction
        # summary line from there. The transcript still lands on stdout.
        "--print-progress",
    ]
    if s.vad_enabled and vad_model_path is not None:
        flags += ["--vad", "--vad-model", _pp(vad_model_path)]
        if s.vad_threshold != 0.5:
            flags += ["--vad-threshold", str(s.vad_threshold)]
        if s.vad_min_speech_ms != 250:
            flags += ["--vad-min-speech-duration-ms", str(s.vad_min_speech_ms)]
        if s.vad_min_silence_ms != 100:
            flags += ["--vad-min-silence-duration-ms", str(s.vad_min_silence_ms)]
        if s.vad_speech_pad_ms != 30:
            flags += ["--vad-speech-pad-ms", str(s.vad_speech_pad_ms)]
        if s.vad_max_speech_s > 0:
            flags += ["--vad-max-speech-duration-s", str(s.vad_max_speech_s)]
    return flags


def transcribe(
    wav_path: Path,
    *,
    config: str,
    settings: Settings,
    models_root: Path,
    audio_duration_s: float | None = None,
    timeout_s: int = 600,
) -> EngineResult:
    """Run whisper-cli on ``wav_path`` and return the parsed result.

    ``audio_duration_s`` is used to convert the VAD sample-reduction into a
    seconds-based ``speech_seconds``. If omitted (None), ``speech_seconds``
    is left as None even when silence_removed is known.
    """
    model_path = models_root / settings.whisper_model
    if not model_path.exists():
        raise FileNotFoundError(
            f"whisper model not found at {model_path}. "
            f"Copy from ai4db/models/whisper.cpp/ or set WHISPER_MODEL to an "
            f"existing file under models/."
        )
    vad_model_path: Path | None = None
    if settings.vad_enabled:
        vad_model_path = models_root / settings.vad_model_path
        if not vad_model_path.exists():
            raise FileNotFoundError(
                f"Silero VAD model not found at {vad_model_path}. "
                f"Download: https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-silero-v6.2.0.bin"
            )

    # If WHISPER_CLI_CMD routes through `ssh …`, the whisper-cli process runs
    # on the remote host, so it needs its own copies of (wav, model, vad_model).
    # Sync them to a stable scratch dir on the remote and rewrite the cmd paths
    # to point there. This makes "run whisper on the Jetson from Windows" work
    # without manual scp.
    remote = _maybe_sync_remote(
        settings.whisper_cli_cmd,
        local_paths={"wav": wav_path, "model": model_path, "vad": vad_model_path},
    )

    # Stash the local-POSIX paths so _rewrite_remote_paths can identify them
    # inside the resolved cmd. Order matches the dict above.
    if remote:
        _rewrite_remote_paths._local_paths = [
            wav_path.as_posix(),
            model_path.as_posix(),
            vad_model_path.as_posix() if vad_model_path else None,
        ]

    cmd, use_shell = _resolve_cmd(
        settings.whisper_cli_cmd, model_path, vad_model_path, wav_path, settings
    )

    if remote:
        cmd = _rewrite_remote_paths(cmd, remote)

    if not use_shell:
        # Validate the binary up-front for a friendlier error.
        binary = cmd[0]
        if shutil.which(binary) is None and not Path(binary).exists():
            raise FileNotFoundError(
                f"whisper-cli not found: {binary!r}. Set WHISPER_CLI_CMD to a "
                f"valid binary or shell command."
            )

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout_s,
            text=True,
            shell=use_shell,
        )
    except FileNotFoundError as exc:
        cmd_repr = cmd[0] if isinstance(cmd, list) else cmd
        raise FileNotFoundError(
            f"failed to launch whisper-cli ({cmd_repr!r}). "
            f"Set WHISPER_CLI_CMD to a valid binary or shell command. "
            f"Underlying: {exc}"
        ) from exc
    runtime_s = time.perf_counter() - t0

    stderr = proc.stderr or ""
    stdout = proc.stdout or ""

    if proc.returncode != 0 and _NO_SPEECH_MARKER in stderr and settings.vad_enabled:
        log.info("whisper-cli VAD found no speech")
        return EngineResult(
            config=config,
            vad_enabled=settings.vad_enabled,
            transcript="",
            runtime_s=runtime_s,
            silence_removed=None,
            speech_seconds=None,
            segments=[],
            cmd=cmd,
            raw_stdout=stdout,
            raw_stderr=stderr,
        )

    if proc.returncode != 0:
        cmd_str_repr = cmd if isinstance(cmd, str) else " ".join(cmd)
        raise RuntimeError(
            f"whisper-cli failed (rc={proc.returncode}). "
            f"cmd: {cmd_str_repr}\nstderr: {stderr.strip()[:500]}"
        )

    silence_removed, speech_seconds = _parse_progress(stderr, audio_duration_s or 0.0)
    segments = _parse_segments(stdout)
    # The transcript is the joined text of the segments when we have them —
    # avoids double-counting timestamps in the user-facing transcript.
    if segments:
        transcript = " ".join(t for _, _, t in segments if t).strip()
    else:
        transcript = (stdout or "").strip()

    return EngineResult(
        config=config,
        vad_enabled=settings.vad_enabled,
        transcript=transcript,
        runtime_s=runtime_s,
        silence_removed=silence_removed,
        speech_seconds=speech_seconds,
        segments=segments,
        cmd=cmd,
        raw_stdout=stdout,
        raw_stderr=stderr,
    )

# scp/ssh are sync — short hops are tolerable for a benchmark. Use a stable
# scratch dir per host so repeated runs don't churn the remote.
_REMOTE_SCRATCH = "/tmp/vad-bench-scratch"


def _is_ssh_command(cmd_str: str) -> bool:
    return cmd_str.lstrip().startswith(("ssh ", "ssh\t"))


def _extract_ssh_host(cmd_str: str) -> str | None:
    """Pull the destination token from ``ssh [opts] HOST [command]``.

    Handles ``-o KEY=VAL``, ``-p PORT``, ``-l USER`` style options — anything
    that takes a value consumes the next token before we look for the host.
    """
    tokens = shlex.split(cmd_str, posix=True)
    if not tokens or tokens[0] != "ssh":
        return None

    opts_with_value = {"-b", "-c", "-E", "-e", "-F", "-I", "-i", "-l",
                       "-o", "-p", "-S", "-W", "-J", "-L", "-R", "-D"}
    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in opts_with_value:
            i += 2  # option + its argument
            continue
        if tok.startswith("-") and len(tok) > 2 and not tok.startswith("--"):
            # Bundled single-letter options like ``-qT`` — no values.
            i += 1
            continue
        if tok.startswith("-"):
            # Long options that may or may not take values. We don't track
            # every one; assume non-value first, fall back to value.
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                # Heuristic: if the next token looks like ``KEY=VAL`` or a port
                # number, treat this option as taking a value.
                nxt = tokens[i + 1]
                if "=" in nxt or nxt.isdigit():
                    i += 2
                    continue
            i += 1
            continue
        return tok  # first bare token = host
    return None


def _maybe_sync_remote(
    cmd_str: str,
    *,
    local_paths: dict[str, Path | None],
) -> dict[str, str] | None:
    """If the whisper-cli command routes through SSH, scp each local file to a
    stable scratch dir on the remote host and return ``{role: remote_path}``
    for the roles that were synced.

    Returns ``None`` when the command is local — no sync needed.
    """
    if not _is_ssh_command(cmd_str):
        return None
    host = _extract_ssh_host(cmd_str)
    if not host:
        return None

    remote: dict[str, str] = {}
    # Make sure the scratch dir exists on the remote.
    try:
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", host, f"mkdir -p {_REMOTE_SCRATCH}"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(
            f"failed to create remote scratch dir {_REMOTE_SCRATCH} on {host}: {exc}"
        ) from exc

    # Collision-safe names: hash the source path so two files with the same
    # name (e.g. two ``wav.wav`` in different folders) never clobber each
    # other on the remote.
    import hashlib
    for role, p in local_paths.items():
        if p is None:
            continue
        if not p.exists():
            raise FileNotFoundError(f"local file missing for {role}: {p}")
        h = hashlib.sha1(str(p.resolve()).encode()).hexdigest()[:10]
        remote_name = f"{h}_{p.name}"
        remote_path = f"{_REMOTE_SCRATCH}/{remote_name}"
        # scp uses POSIX-style paths on the remote; convert Windows backslashes
        # in the local path before passing to scp.
        local_posix = p.as_posix() if sys.platform == "win32" else str(p)
        try:
            subprocess.run(
                ["scp", "-q", local_posix, f"{host}:{remote_path}"],
                check=True,
                capture_output=True,
                timeout=180,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise RuntimeError(
                f"failed to scp {role} ({local_posix}) to {host}:{remote_path}: {exc}"
            ) from exc
        remote[role] = remote_path
    return remote


def _rewrite_remote_paths(cmd: list[str] | str, remote: dict[str, str]) -> list[str] | str:
    """Swap the local paths in ``cmd`` for their remote-side equivalents.

    We identify files by their *full local path* (stored at sync time) — the
    flag emission converts Windows paths to POSIX form, so the suffix we look
    for is the POSIX-form local path.
    """
    local_paths = getattr(_rewrite_remote_paths, "_local_paths", None)
    if local_paths is None:
        return cmd
    _rewrite_remote_paths._local_paths = None  # consume once

    def _swap_list(tok: str) -> str:
        # If the token ends with any of the local-POSIX paths, swap it.
        for local_posix, remote_path in zip(local_paths, [remote["wav"], remote["model"], remote.get("vad")]):
            if tok == local_posix or tok.endswith("/" + local_posix.rsplit("/", 1)[-1]):
                # Path-equal OR just filename equal — different files can
                # share a name so prefer the full match first.
                if tok == local_posix:
                    return remote_path
        # Fallback: filename-only match.
        for local_posix, remote_path in zip(local_paths, [remote["wav"], remote["model"], remote.get("vad")]):
            if tok.endswith("/" + local_posix.rsplit("/", 1)[-1]):
                return remote_path
        return tok

    if isinstance(cmd, list):
        return [_swap_list(t) for t in cmd]
    # Shell-mode string: replace the full local-POSIX path occurrences
    # literally. Local paths are unique by construction (we sync three
    # different files at most), so a plain replace is safe.
    out = cmd
    for local_posix, remote_path in zip(local_paths, [remote["wav"], remote["model"], remote.get("vad")]):
        if remote_path and local_posix:
            out = out.replace(local_posix, remote_path)
    return out


def parse_settings_overrides(overrides: dict, base: Settings) -> Settings:
    """Apply a partial dict of overrides on top of ``base`` Settings.

    Used by the FastAPI layer to build a per-run Settings instance from the
    UI's POST params. Mirrors ocr-benchmark's pattern of merging at the
    call site rather than mutating the singleton.
    """
    if not overrides:
        return base
    clean = {k: v for k, v in overrides.items() if v is not None}
    return base.model_copy(update=clean)


if __name__ == "__main__":  # self-check: token round-trip only
    s = Settings()
    print("OK; default whisper_cli_cmd =", s.whisper_cli_cmd)
    cmd, use_shell = _resolve_cmd(
        "whisper-cli",
        Path("/tmp/m.bin"),
        Path("/tmp/v.bin"),
        Path("/tmp/a.wav"),
        s,
    )
    assert isinstance(cmd, list) and use_shell is False
    assert "--vad" in cmd and "--vad-model" in cmd, cmd
    print("OK; example cmd tail =", cmd[-6:])

    # Shell mode for the SSH pattern.
    cmd, use_shell = _resolve_cmd(
        "ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'",
        Path("/tmp/m.bin"),
        Path("/tmp/v.bin"),
        Path("/tmp/a.wav"),
        s,
    )
    assert use_shell is True and isinstance(cmd, str)
    assert "whisper.cpp/build/bin/whisper-cli" in cmd
    print("OK; ssh-mode cmd =", cmd[:80] + "…")