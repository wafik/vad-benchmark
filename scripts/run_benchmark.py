"""CLI entrypoint for the VAD benchmark.

Headless / CI-friendly. Mirrors the UI's ``POST /api/run`` payload — every
flag from ``config.Settings`` is overridable here.

Examples
--------
    # canonical comparison (baseline_novad vs silero_vad)
    uv run python -m scripts.run_benchmark

    # single config with explicit overrides
    uv run python -m scripts.run_benchmark \\
        --config name=silero_t05,vad_enabled=true,vad_threshold=0.5

    # multiple configs
    uv run python -m scripts.run_benchmark \\
        --config name=baseline,vad_enabled=false \\
        --config name=silero_05,vad_enabled=true,vad_threshold=0.5 \\
        --config name=silero_07,vad_enabled=true,vad_threshold=0.7
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure `vad_bench` is importable when invoked as a module.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vad_bench.config import Settings  # noqa: E402
from vad_bench.runner import run as run_benchmark  # noqa: E402


def _parse_kv_spec(spec: str | None) -> dict | None:
    """Parse ``key=value,key=value`` into a dict. Returns None if ``spec`` is empty."""
    if not spec:
        return None
    out: dict = {}
    for kv in spec.split(","):
        kv = kv.strip()
        if not kv:
            continue
        if "=" not in kv:
            raise SystemExit(f"bad config spec (expected key=value, got {kv!r})")
        k, v = kv.split("=", 1)
        k = k.strip()
        v = v.strip()
        # Cast to the right type using the Settings model.
        field = Settings.model_fields.get(k)
        if field is None:
            raise SystemExit(f"unknown setting: {k!r}. Valid: {list(Settings.model_fields)}")
        ann = str(field.annotation)
        if ann == "bool" or ann == "Optional[bool]":
            out[k] = v.lower() in {"1", "true", "yes", "on"}
        elif ann == "int" or ann == "Optional[int]":
            out[k] = int(v)
        elif ann == "float" or ann == "Optional[float]":
            out[k] = float(v)
        else:
            out[k] = v
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="VAD benchmark CLI")
    p.add_argument(
        "--config", action="append", default=[],
        help="Repeatable. Format: name=<n>,vad_enabled=<bool>,vad_threshold=<float>,… "
             "Anything not given falls back to .env / defaults. "
             "If omitted entirely, runs the canonical baseline_novad vs silero_vad.",
    )
    p.add_argument("--json", action="store_true", help="Print the summary as JSON.")
    args = p.parse_args(argv)

    if args.config:
        cfgs: list[dict] = []
        for spec in args.config:
            if "name=" not in spec:
                raise SystemExit(f"config spec must include name=… : {spec!r}")
            d = _parse_kv_spec(spec)
            name = d.pop("name")
            cfgs.append({"name": name, "overrides": d})
    else:
        cfgs = None  # runner's default 2-config comparison

    summary = run_benchmark(cfgs, verbose=not args.json)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())