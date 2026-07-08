# Simple HTTP Auth for vad-benchmark

**Date:** 2026-07-08
**Status:** approved (verbal, in chat)
**Scope:** Add an HTTP Basic auth gate that mirrors the sibling
`ocr-benchmark` project's auth implementation.

## Source of truth

`C:\Users\Ulinn\Documents\projek\kreasi\ocr-benchmark\src\ocr_bench\api.py`
lines 112-133 (`_check_auth` + `_BasicAuthMiddleware`) — the entire auth
mechanism is inline in `api.py` there; no separate `auth.py` module exists.

## Decisions

- **Mechanism:** HTTP Basic, single shared password, browser-handled prompt.
  No login page, no cookies, no JWT. Same as `ocr-benchmark`.
- **Default password:** `"AI4DB-BENCH"` (same default as `ocr-benchmark` for
  cross-project consistency). Override via `AUTH_PASSWORD` in `.env`.
- **Realm:** `"VAD Benchmark"` (matches the dashboard title).
- **Allowlist:** `GET /api/health` returns `{"ok": true}` and bypasses auth,
  so Docker `HEALTHCHECK` or external monitors don't get prompted.
- **Tests:** new `tests/test_auth.py` with one `TestClient` covering the three
  matrix entries (no auth → 401, valid auth → 200, `/api/health` always 200).
  This is **more** than what `ocr-benchmark` ships — closes the gap that
  ocr-benchmark leaves open.

## Changes

1. **`src/vad_bench/config.py`** — add one field:
   ```python
   auth_password: str = "AI4DB-BENCH"
   ```
   (No new env key needed; `AUTH_PASSWORD` already maps via pydantic-settings.)

2. **`src/vad_bench/api.py`** — add:
   - `import secrets` and `from starlette.middleware.base import BaseHTTPMiddleware`
     and `from starlette.requests import Request`.
   - `_check_auth(request)` — copy verbatim from ocr-benchmark.
   - `_BasicAuthMiddleware` — copy verbatim, but change the realm string
     and the allowlist path.
   - `app.add_middleware(_BasicAuthMiddleware)` inside `create_app()`.
   - New `GET /api/health` endpoint returning `{"ok": true}` and
     `"status": "running"`.

3. **`.env.example`** — add:
   ```
   # HTTP Basic Auth password gating the whole dashboard (any username works).
   AUTH_PASSWORD=AI4DB-BENCH
   ```

4. **`tests/test_auth.py`** — one file, one TestClient. Asserts:
   - `GET /` without `Authorization` → 401 and `WWW-Authenticate` header.
   - `GET /` with wrong password → 401.
   - `GET /` with correct `Basic` header → 200.
   - `GET /api/health` without auth → 200.

5. **`README.md`** — one-line addition under "Caveats": "Dashboard is gated
   by HTTP Basic Auth (password in `AUTH_PASSWORD`); the browser will prompt
   on first visit."

## Out of scope

- No logout endpoint. No CSRF / rate limit / lockout. Same tradeoffs as
  ocr-benchmark — single-user local-network deployments only.
- No JS-side auth code. Browser handles login dialog.
- No `tests/conftest.py` rewiring; `TestClient(app)` is sufficient for
  these 4 assertions.