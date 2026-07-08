"""FastAPI: serves the dashboard + JSON endpoints.

Mirrors the sibling ``ocr-benchmark``'s api.py almost line-for-line so the
UI patterns are portable:

  GET  /                        dashboard (ui/index.html)
  POST /api/run                 run benchmark (background; poll /api/progress)
  GET  /api/progress            live run status
  GET  /api/progress/stream     Server-Sent Events
  GET  /api/summary             aggregated metrics
  GET  /api/results/<config>    per-config detail incl. word alignment
  GET  /api/results             list all configs from latest run
  GET  /api/audio               serve the prepared 16 kHz WAV (in-page player)
  GET  /api/config              current runtime config
  GET  /api/models              whisper/silero models present in models/
  GET  /api/system              live CPU/RAM/GPU/temperature snapshot
  GET  /api/history             past runs (newest first)
  GET  /api/history/<id>        one past run
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import secrets
import sys
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .config import Settings, get_settings
from .paths import (
    HISTORY_ROOT,
    MODELS_ROOT,
    PODCAST_WAV,
    REPORTS_ROOT,
    UI_ROOT,
)
from .runner import RUN_STATUS_PATH, run as run_benchmark, read_status

log = logging.getLogger(__name__)


# ─── HTTP Basic Auth ──────────────────────────────────────────────
# Mirrors the sibling ocr-benchmark project exactly: single shared
# password in `Settings.auth_password` (env var AUTH_PASSWORD), browser
# handles the login prompt (no /login page, no session token). Constant-
# time compare via secrets.compare_digest. /api/health is allowlisted so
# Docker HEALTHCHECK / external monitors can probe without credentials.
def _check_auth(request: Request) -> bool:
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        _, password = base64.b64decode(header[6:]).decode("utf-8").split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return False
    return secrets.compare_digest(password, get_settings().auth_password)


class _BasicAuthMiddleware(BaseHTTPMiddleware):
    """Static password gate. Browser handles the login prompt (no login
    page/session needed) — any username, password from AUTH_PASSWORD."""

    async def dispatch(self, request: Request, call_next):
        # Unauthenticated: only the healthcheck, so it doesn't need creds.
        if request.url.path == "/api/health" or _check_auth(request):
            return await call_next(request)
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="VAD Benchmark"'},
        )


def _is_stale(status: dict, stale_after_s: int) -> bool:
    last = status.get("updated_at") or status.get("started_at")
    if not last:
        return False
    from datetime import datetime, timezone
    try:
        ts = datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return False
    return (datetime.now(timezone.utc) - ts).total_seconds() > stale_after_s


def create_app() -> FastAPI:
    app = FastAPI(title="VAD Benchmark", version="0.1.0")

    # Auth gate — must be added before any routes mount. Covers every
    # endpoint except /api/health (allowlisted for Docker HEALTHCHECK).
    app.add_middleware(_BasicAuthMiddleware)

    @app.get("/api/health")
    def api_health():
        # Allowlisted in _BasicAuthMiddleware so monitors can probe
        # without prompting for credentials.
        return {"ok": True, "status": "running", "service": "vad-benchmark"}

    @app.post("/api/run")
    def api_run(
        background: BackgroundTasks,
        configs: str | None = None,  # JSON-encoded list of {name, overrides}
        force: bool = False,
    ):
        # Build the configs list. Either from JSON in the `configs` param
        # (used by the UI) or the canonical 2-config comparison.
        if configs:
            try:
                parsed = json.loads(configs)
                if not isinstance(parsed, list):
                    raise ValueError("configs must be a JSON array")
                cfgs = parsed
            except (json.JSONDecodeError, ValueError) as e:
                raise HTTPException(400, f"invalid configs JSON: {e}")
        else:
            cfgs = None  # runner's default

        if RUN_STATUS_PATH.exists():
            try:
                current = json.loads(RUN_STATUS_PATH.read_text(encoding="utf-8"))
                if current.get("running") and not force:
                    s = get_settings()
                    if not _is_stale(current, s.run_stale_after_s):
                        return {"ok": False, "already_running": True}
            except (json.JSONDecodeError, OSError):
                pass

        background.add_task(run_benchmark, cfgs, True)
        return {"ok": True, "started": True}

    @app.get("/api/progress")
    def api_progress():
        s = get_settings()
        return JSONResponse(read_status(s.run_stale_after_s))

    @app.get("/api/progress/stream")
    async def api_progress_stream():
        async def gen():
            last = None
            try:
                while True:
                    s = get_settings()
                    payload = json.dumps(read_status(s.run_stale_after_s))
                    if payload != last:
                        yield f"data: {payload}\n\n"
                        last = payload
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                return

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/summary")
    def api_summary():
        path = REPORTS_ROOT / "summary.json"
        if not path.exists():
            raise HTTPException(404, "no reports yet — run POST /api/run or scripts/run_benchmark.py")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/results")
    def api_results_list():
        path = REPORTS_ROOT / "summary.json"
        if not path.exists():
            raise HTTPException(404, "no reports yet")
        data = json.loads(path.read_text(encoding="utf-8"))
        # Strip heavy alignment payloads from the list view.
        light = []
        for c in data.get("configs", []):
            light.append({k: v for k, v in c.items() if k != "alignment"})
        return JSONResponse({"configs": light, "last_run": data.get("last_run"),
                              "audio_duration_s": data.get("audio_duration_s")})

    @app.get("/api/results/{config}")
    def api_results_one(config: str):
        from .runner import _slug
        path = REPORTS_ROOT / "per_config" / f"{_slug(config)}.json"
        if not path.exists():
            raise HTTPException(404, f"config not found: {config}")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/api/audio")
    def api_audio():
        if not PODCAST_WAV.exists():
            raise HTTPException(404, "audio not prepared — run a benchmark first")
        return FileResponse(PODCAST_WAV, media_type="audio/wav")

    @app.get("/api/reference/segments")
    def api_reference_segments():
        """Return the reference transcript as ``[{start, end, text}, ...]``.

        Used by the VAD breakdown tab to draw the ground-truth timeline
        underneath the Whisper-region timeline. The on-disk schema uses
        ``start_s`` / ``end_s`` (from ``reference.write_reference_artifacts``)
        — we normalize to ``start`` / ``end`` here for the UI.
        """
        path = REPORTS_ROOT / "reference" / "segments.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                segs = data.get("segments") if isinstance(data, dict) else data
                return {"segments": [
                    {"start": s.get("start_s", s.get("start")),
                     "end":   s.get("end_s",   s.get("end")),
                     "text":  s.get("text", "")}
                    for s in (segs or [])
                ]}
            except (json.JSONDecodeError, OSError):
                pass
        from .reference import load_reference
        _text, segments = load_reference()
        return {"segments": [{"start": s[0], "end": s[1], "text": s[2]} for s in segments]}

    @app.get("/api/config")
    def api_config():
        s = get_settings()
        return {
            "whisper_model": s.whisper_model,
            "language": s.language,
            "threads": s.threads,
            "vad_enabled": s.vad_enabled,
            "vad_model_path": s.vad_model_path,
            "vad_threshold": s.vad_threshold,
            "vad_min_speech_ms": s.vad_min_speech_ms,
            "vad_min_silence_ms": s.vad_min_silence_ms,
            "vad_speech_pad_ms": s.vad_speech_pad_ms,
            "vad_max_speech_s": s.vad_max_speech_s,
            "audio_sample_rate": s.audio_sample_rate,
            "audio_channels": s.audio_channels,
            "serve_host": s.serve_host,
            "serve_port": s.serve_port,
            "whisper_cli_cmd": s.whisper_cli_cmd,
            "vad_model_present": (MODELS_ROOT / s.vad_model_path).exists(),
            "whisper_model_present": (MODELS_ROOT / s.whisper_model).exists(),
        }

    @app.get("/api/models")
    def api_models():
        # Surface every .bin in models/ — handy when the user has multiple
        # whisper models or wants to add a base/small one.
        bins = sorted(p.name for p in MODELS_ROOT.glob("*.bin")) if MODELS_ROOT.exists() else []
        s = get_settings()
        return {
            "available": bins,
            "whisper_model": s.whisper_model,
            "vad_model": s.vad_model_path,
            "whisper_present": (MODELS_ROOT / s.whisper_model).exists(),
            "vad_present": (MODELS_ROOT / s.vad_model_path).exists(),
        }

    @app.get("/api/system")
    def api_system():
        from .sysmon import sample_dict
        return JSONResponse(sample_dict())

    @app.get("/api/history")
    def api_history():
        idx = HISTORY_ROOT / "index.json"
        if not idx.exists():
            return {"runs": []}
        try:
            runs = json.loads(idx.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"runs": []}
        return {"runs": list(reversed(runs))}  # newest first

    @app.get("/api/history/{run_id}")
    def api_history_detail(run_id: str):
        safe = "".join(c if c.isalnum() or c in "_-" else "" for c in run_id)
        path = HISTORY_ROOT / f"{safe}.json"
        if not path.exists():
            raise HTTPException(404, f"run not found: {run_id}")
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    @app.get("/")
    def index():
        idx = UI_ROOT / "index.html"
        if not idx.exists():
            raise HTTPException(404, "ui/index.html not found")
        return FileResponse(idx, media_type="text/html")

    if UI_ROOT.exists():
        class _NoCacheStaticFiles(StaticFiles):
            def file_response(self, *args, **kwargs):
                resp = super().file_response(*args, **kwargs)
                resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                resp.headers["Expires"] = "0"
                return resp
        app.mount("/static", _NoCacheStaticFiles(directory=str(UI_ROOT)), name="static")

    return app


app = create_app()


def serve() -> None:
    """Console-script entrypoint (`vad-bench-serve`)."""
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )
    logging.getLogger("vad_bench").setLevel(logging.INFO)
    s = get_settings()
    uvicorn.run(app, host=s.serve_host, port=s.serve_port, log_level="warning")


if __name__ == "__main__":  # self-check
    serve()