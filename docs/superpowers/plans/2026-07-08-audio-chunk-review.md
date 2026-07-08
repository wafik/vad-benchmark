# Audio chunk review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Slice and persist the actual audio chunks whisper receives after VAD, keep their text/timing in run history, and let the dashboard play each chunk back next to its transcript — plus auto-play the source podcast when "Run benchmark" is clicked.

**Architecture:** After `transcribe()` returns per-segment timestamps for a VAD-enabled config, a new stdlib-`wave`-only helper slices the already-16kHz-mono-PCM16 source WAV into one file per segment under `reports/chunks/<config>/NNNN.wav`. `RunMetrics` gains a `chunks_available` flag; a new `GET /api/chunks/{config}/{index}` endpoint serves the files. The dashboard's existing VAD-breakdown tab renders a new chunk-list table with a native `<audio>` per row. Chunk **audio** is wiped and rebuilt every run (latest-run-only); chunk **text+timing** is added to the history snapshot dict (cheap, kept for 50 runs like today).

**Tech Stack:** Python stdlib `wave` (no ffmpeg subprocess per chunk), FastAPI `FileResponse`, vanilla JS + native `<audio controls>`.

## Global Constraints

- Chunk audio is only ever produced for configs where `vad_enabled` is `True` and segments are non-empty — VAD-off configs never get chunk files (per spec).
- Chunk audio files are retained for the **latest run only** — `reports/chunks/` is deleted wholesale at the start of every `run()` call, before any config runs.
- Chunk **text + timing** (not audio) is retained indefinitely in run history, same 50-run cap as today (`HISTORY_ROOT/index.json`).
- No new third-party dependency — stdlib `wave` only, matching `audio.py`'s existing `wav_duration()`.
- No waveform visualization, no chunk editing/export — out of scope per spec.
- 404 (not 500) for a missing chunk file; the UI must treat `chunks_available: false` as a quiet state, never a broken `<audio src>`.

---

## File Structure

| File | Change |
|---|---|
| `src/vad_bench/paths.py` | Add `CHUNKS_ROOT = REPORTS_ROOT / "chunks"` constant (matches existing convention of centralizing shared roots). |
| `src/vad_bench/audio.py` | Add `slice_wav_segments(src, segments, out_dir)`. |
| `tests/test_audio.py` | Add a test for `slice_wav_segments`. |
| `src/vad_bench/metrics.py` | Add `chunks_available: bool = False` field to `RunMetrics` + serialize in `to_dict()`. |
| `src/vad_bench/runner.py` | Wipe `CHUNKS_ROOT` at start of `run()`; call `slice_wav_segments()` after a VAD-on config transcribes; compute `chunks_available` in `_score()`; add `segments` (text+timing) to `_record_from_metrics()`. |
| `src/vad_bench/api.py` | Add `GET /api/chunks/{config}/{index}`. |
| `ui/app.js` | Add `vad.chunks.*` i18n keys (en+id); render chunk-list table inside `renderVadBreakdown()`; auto-play line in `#btn-run` click handler. |
| `ui/style.css` | Add `.vad-chunks-table` styling (reuse `.vad-regions-table` look) if the existing table classes don't already cover it — see Task 6. |

---

## Task 1: `paths.py` — add `CHUNKS_ROOT`

**Files:**
- Modify: `src/vad_bench/paths.py:13` (after `HISTORY_ROOT`)

**Interfaces:**
- Produces: `CHUNKS_ROOT: Path` — importable by `runner.py` and `api.py`.

No test needed — this is a one-line constant matching the existing `HISTORY_ROOT = REPORTS_ROOT / "history"` pattern; there's nothing to assert beyond "it's a Path", which `test_audio.py`'s later import will already exercise implicitly.

- [ ] **Step 1: Add the constant**

In `src/vad_bench/paths.py`, change:

```python
DATA_ROOT = PACKAGE_ROOT / "data"
MODELS_ROOT = PACKAGE_ROOT / "models"
REPORTS_ROOT = PACKAGE_ROOT / "reports"
HISTORY_ROOT = REPORTS_ROOT / "history"
UI_ROOT = PACKAGE_ROOT / "ui"
TESTS_ROOT = PACKAGE_ROOT / "tests"
```

to:

```python
DATA_ROOT = PACKAGE_ROOT / "data"
MODELS_ROOT = PACKAGE_ROOT / "models"
REPORTS_ROOT = PACKAGE_ROOT / "reports"
HISTORY_ROOT = REPORTS_ROOT / "history"
CHUNKS_ROOT = REPORTS_ROOT / "chunks"
UI_ROOT = PACKAGE_ROOT / "ui"
TESTS_ROOT = PACKAGE_ROOT / "tests"
```

- [ ] **Step 2: Commit**

```bash
git add src/vad_bench/paths.py
git commit -m "Add CHUNKS_ROOT path constant"
```

---

## Task 2: `audio.py` — `slice_wav_segments`

**Files:**
- Modify: `src/vad_bench/audio.py`
- Test: `tests/test_audio.py`

**Interfaces:**
- Consumes: nothing new — uses stdlib `wave`, and `pathlib.Path`.
- Produces: `slice_wav_segments(src: Path, segments: list[tuple[float, float, str]], out_dir: Path) -> None`. Later tasks (runner.py) call this with `segments=result.segments` (the same `list[tuple[float, float, str]]` shape already produced by `engine._parse_segments()` and stored on `EngineResult.segments`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_audio.py` (append after `test_wav_duration`):

```python
def test_slice_wav_segments(tmp_path):
    from vad_bench.audio import slice_wav_segments

    src = tmp_path / "src.wav"
    framerate = 16000
    total_s = 2.0
    n_frames = int(framerate * total_s)
    with wave.open(str(src), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x01" * n_frames)  # 2 bytes/frame, distinguishable non-zero pattern

    out_dir = tmp_path / "chunks"
    segments = [(0.0, 0.5, "halo"), (1.0, 1.5, "dunia")]
    slice_wav_segments(src, segments, out_dir)

    files = sorted(out_dir.glob("*.wav"))
    assert [f.name for f in files] == ["0000.wav", "0001.wav"]

    with wave.open(str(files[0]), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == framerate
        assert wf.getnframes() == int(0.5 * framerate)

    with wave.open(str(files[1]), "rb") as wf:
        assert wf.getnframes() == int(0.5 * framerate)


def test_slice_wav_segments_empty_list_is_noop(tmp_path):
    from vad_bench.audio import slice_wav_segments

    src = tmp_path / "src.wav"
    with wave.open(str(src), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(b"\x00" * 3200)

    out_dir = tmp_path / "chunks"
    slice_wav_segments(src, [], out_dir)
    assert not out_dir.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL — `ImportError: cannot import name 'slice_wav_segments'`

- [ ] **Step 3: Write minimal implementation**

In `src/vad_bench/audio.py`, add after `wav_duration`:

```python
def slice_wav_segments(
    src: Path,
    segments: list[tuple[float, float, str]],
    out_dir: Path,
) -> None:
    """Slice ``src`` into one WAV file per ``(start_s, end_s, text)`` segment.

    Stdlib ``wave`` only — no ffmpeg subprocess per chunk. ``src`` is already
    16 kHz mono PCM16 (exactly what whisper-cli consumed), so raw frame
    slicing is enough; no resampling needed. Output files are named
    ``NNNN.wav`` (zero-padded index, matching segment order) in ``out_dir``,
    which is created if missing. A no-op (no directory created) when
    ``segments`` is empty, mirroring ``_parse_segments``'s empty-list
    contract.
    """
    if not segments:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    with wave.open(str(src), "rb") as wf:
        framerate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        nchannels = wf.getnchannels()
        for index, (start_s, end_s, _text) in enumerate(segments):
            start_frame = int(start_s * framerate)
            n_frames = int((end_s - start_s) * framerate)
            wf.setpos(start_frame)
            frames = wf.readframes(n_frames)
            out_path = out_dir / f"{index:04d}.wav"
            with wave.open(str(out_path), "wb") as out:
                out.setnchannels(nchannels)
                out.setsampwidth(sampwidth)
                out.setframerate(framerate)
                out.writeframes(frames)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_audio.py -v`
Expected: PASS (4 tests: `test_ensure_wav_missing_input`, `test_wav_duration`, `test_slice_wav_segments`, `test_slice_wav_segments_empty_list_is_noop`)

- [ ] **Step 5: Commit**

```bash
git add src/vad_bench/audio.py tests/test_audio.py
git commit -m "Add slice_wav_segments for per-region chunk audio"
```

---

## Task 3: `metrics.py` — `chunks_available` field

**Files:**
- Modify: `src/vad_bench/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `RunMetrics.chunks_available: bool` (default `False`), serialized as `"chunks_available"` in `to_dict()`. Task 4 (`runner.py`) sets this field when constructing `RunMetrics` in `_score()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_metrics.py` (append):

```python
def test_run_metrics_chunks_available_default_and_serialization():
    from vad_bench.metrics import RunMetrics

    rm = RunMetrics(
        config="c", vad_enabled=True,
        transcript_raw="", transcript_normalized="", reference_normalized="",
        wer=0.0, cer=0.0, rtf=0.0, runtime_s=0.0, audio_duration_s=0.0,
    )
    assert rm.chunks_available is False
    assert rm.to_dict()["chunks_available"] is False

    rm2 = RunMetrics(
        config="c", vad_enabled=True,
        transcript_raw="", transcript_normalized="", reference_normalized="",
        wer=0.0, cer=0.0, rtf=0.0, runtime_s=0.0, audio_duration_s=0.0,
        chunks_available=True,
    )
    assert rm2.to_dict()["chunks_available"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: FAIL — `TypeError: RunMetrics.__init__() got an unexpected keyword argument 'chunks_available'`

- [ ] **Step 3: Write minimal implementation**

In `src/vad_bench/metrics.py`, change the `RunMetrics` dataclass from:

```python
@dataclass
class RunMetrics:
    config: str
    vad_enabled: bool
    transcript_raw: str
    transcript_normalized: str
    reference_normalized: str
    wer: float
    cer: float
    rtf: float
    runtime_s: float
    audio_duration_s: float
    speech_seconds: float | None = None
    silence_removed: float | None = None
    n_segments: int | None = None
    segments: list[tuple[float, float, str]] = field(default_factory=list)
    alignment: list[dict] = field(default_factory=list)
```

to:

```python
@dataclass
class RunMetrics:
    config: str
    vad_enabled: bool
    transcript_raw: str
    transcript_normalized: str
    reference_normalized: str
    wer: float
    cer: float
    rtf: float
    runtime_s: float
    audio_duration_s: float
    speech_seconds: float | None = None
    silence_removed: float | None = None
    n_segments: int | None = None
    segments: list[tuple[float, float, str]] = field(default_factory=list)
    alignment: list[dict] = field(default_factory=list)
    chunks_available: bool = False
```

And change `to_dict()` from:

```python
            "n_segments": self.n_segments,
            "segments": [
                {"start": s, "end": e, "text": t}
                for s, e, t in self.segments
            ],
            "alignment": self.alignment,
        }
```

to:

```python
            "n_segments": self.n_segments,
            "segments": [
                {"start": s, "end": e, "text": t}
                for s, e, t in self.segments
            ],
            "alignment": self.alignment,
            "chunks_available": self.chunks_available,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_metrics.py -v`
Expected: PASS (all existing metrics tests + the new one)

- [ ] **Step 5: Commit**

```bash
git add src/vad_bench/metrics.py tests/test_metrics.py
git commit -m "Add chunks_available field to RunMetrics"
```

---

## Task 4: `runner.py` — wire up chunk slicing, availability, and history text

**Files:**
- Modify: `src/vad_bench/runner.py`

**Interfaces:**
- Consumes: `slice_wav_segments` (Task 2, `audio.py`), `CHUNKS_ROOT` (Task 1, `paths.py`), `RunMetrics.chunks_available` (Task 3, `metrics.py`).
- Produces: `reports/chunks/<slug(config)>/NNNN.wav` files on disk for VAD-on configs with segments; `_record_from_metrics()` output dicts now include a `"segments"` key (`list[{"start","end","text"}]`) that flows into `_save_to_history()`'s `records` list and therefore into the history JSON snapshot.

- [ ] **Step 1: Update imports**

In `src/vad_bench/runner.py`, change:

```python
from .audio import ensure_wav, wav_duration
from .config import Settings
from .engine import EngineResult, parse_settings_overrides, transcribe
from .metrics import RunMetrics, aggregate, cer, normalize, wer, word_alignment
from .paths import HISTORY_ROOT, MODELS_ROOT, REPORTS_ROOT
```

to:

```python
from .audio import ensure_wav, slice_wav_segments, wav_duration
from .config import Settings
from .engine import EngineResult, parse_settings_overrides, transcribe
from .metrics import RunMetrics, aggregate, cer, normalize, wer, word_alignment
from .paths import CHUNKS_ROOT, HISTORY_ROOT, MODELS_ROOT, REPORTS_ROOT
```

- [ ] **Step 2: Wipe chunk audio at the start of `run()`**

In `run()`, right after the existing:

```python
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    per_config_dir = REPORTS_ROOT / "per_config"
    per_config_dir.mkdir(parents=True, exist_ok=True)
```

add:

```python
    import shutil
    if CHUNKS_ROOT.exists():
        shutil.rmtree(CHUNKS_ROOT)
```

(placed right after `per_config_dir.mkdir(...)`, so it runs once per `run()` call before any config is processed — matching the spec's "latest-run-only retention".)

- [ ] **Step 3: Slice chunk audio after a successful transcribe**

In the per-config loop, right after:

```python
            rm = _score(result, reference_text, audio_duration)
            run_metrics.append(rm)
            run_records.append(_record_from_metrics(rm, s))
```

add:

```python
            if s.vad_enabled and result.segments:
                slice_wav_segments(wav, result.segments, CHUNKS_ROOT / _slug(name))
```

- [ ] **Step 4: Compute `chunks_available` in `_score()`**

Change `_score()` from:

```python
def _score(result: EngineResult, reference_norm: str, audio_duration_s: float) -> RunMetrics:
    hyp_norm = normalize(result.transcript)
    return RunMetrics(
        config=result.config,
        vad_enabled=result.vad_enabled,
        transcript_raw=result.transcript,
        transcript_normalized=hyp_norm,
        reference_normalized=reference_norm,
        wer=wer(reference_norm, hyp_norm),
        cer=cer(reference_norm, hyp_norm),
        rtf=result.runtime_s / audio_duration_s if audio_duration_s > 0 else 0.0,
        runtime_s=result.runtime_s,
        audio_duration_s=audio_duration_s,
        speech_seconds=result.speech_seconds,
        silence_removed=result.silence_removed if result.vad_enabled else None,
        n_segments=len(result.segments) if result.segments else None,
        segments=result.segments,
        alignment=word_alignment(reference_norm, hyp_norm),
    )
```

to:

```python
def _score(result: EngineResult, reference_norm: str, audio_duration_s: float) -> RunMetrics:
    hyp_norm = normalize(result.transcript)
    return RunMetrics(
        config=result.config,
        vad_enabled=result.vad_enabled,
        transcript_raw=result.transcript,
        transcript_normalized=hyp_norm,
        reference_normalized=reference_norm,
        wer=wer(reference_norm, hyp_norm),
        cer=cer(reference_norm, hyp_norm),
        rtf=result.runtime_s / audio_duration_s if audio_duration_s > 0 else 0.0,
        runtime_s=result.runtime_s,
        audio_duration_s=audio_duration_s,
        speech_seconds=result.speech_seconds,
        silence_removed=result.silence_removed if result.vad_enabled else None,
        n_segments=len(result.segments) if result.segments else None,
        segments=result.segments,
        alignment=word_alignment(reference_norm, hyp_norm),
        chunks_available=bool(result.vad_enabled and result.segments),
    )
```

- [ ] **Step 5: Add `segments` (text+timing) to the history record**

Change `_record_from_metrics()` from:

```python
def _record_from_metrics(rm: RunMetrics, s: Settings) -> dict:
    return {
        "config": rm.config,
        "vad_enabled": rm.vad_enabled,
        "wer": rm.wer,
        "cer": rm.cer,
        "rtf": rm.rtf,
        "runtime_s": rm.runtime_s,
        "audio_duration_s": rm.audio_duration_s,
        "speech_seconds": rm.speech_seconds,
        "silence_removed": rm.silence_removed,
        "n_segments": rm.n_segments,
        "vad_threshold": s.vad_threshold,
        "vad_min_speech_ms": s.vad_min_speech_ms,
        "vad_min_silence_ms": s.vad_min_silence_ms,
        "vad_speech_pad_ms": s.vad_speech_pad_ms,
        "vad_max_speech_s": s.vad_max_speech_s,
        "whisper_model": s.whisper_model,
        "language": s.language,
        "threads": s.threads,
    }
```

to:

```python
def _record_from_metrics(rm: RunMetrics, s: Settings) -> dict:
    return {
        "config": rm.config,
        "vad_enabled": rm.vad_enabled,
        "wer": rm.wer,
        "cer": rm.cer,
        "rtf": rm.rtf,
        "runtime_s": rm.runtime_s,
        "audio_duration_s": rm.audio_duration_s,
        "speech_seconds": rm.speech_seconds,
        "silence_removed": rm.silence_removed,
        "n_segments": rm.n_segments,
        "segments": [
            {"start": start, "end": end, "text": text}
            for start, end, text in rm.segments
        ],
        "vad_threshold": s.vad_threshold,
        "vad_min_speech_ms": s.vad_min_speech_ms,
        "vad_min_silence_ms": s.vad_min_silence_ms,
        "vad_speech_pad_ms": s.vad_speech_pad_ms,
        "vad_max_speech_s": s.vad_max_speech_s,
        "whisper_model": s.whisper_model,
        "language": s.language,
        "threads": s.threads,
    }
```

Note: `_write_summary_csv()`'s `fields` list is left unchanged — `csv.DictWriter(..., extrasaction="ignore")` already silently drops keys not in `fields`, so adding `segments` to the record dict does not break CSV export (a list value in a CSV cell would be undesirable anyway; it's correctly excluded).

- [ ] **Step 6: Run existing test suite to verify nothing broke**

Run: `python -m pytest tests/ -v`
Expected: PASS — all existing tests plus Task 2/3's new tests. `test_engine.py` and `test_reference.py` are untouched by this task and should be unaffected.

- [ ] **Step 7: Commit**

```bash
git add src/vad_bench/runner.py
git commit -m "Slice and persist VAD chunk audio per run; keep chunk text in history"
```

---

## Task 5: `api.py` — `GET /api/chunks/{config}/{index}`

**Files:**
- Modify: `src/vad_bench/api.py`

**Interfaces:**
- Consumes: `CHUNKS_ROOT` (Task 1, `paths.py`), `_slug` (already imported inline in `api_results_one`, same pattern reused here).
- Produces: `GET /api/chunks/{config}/{index}` → `audio/wav` bytes, or 404.

- [ ] **Step 1: Update the `paths` import**

In `src/vad_bench/api.py`, change:

```python
from .paths import (
    HISTORY_ROOT,
    MODELS_ROOT,
    PODCAST_WAV,
    REPORTS_ROOT,
    UI_ROOT,
)
```

to:

```python
from .paths import (
    CHUNKS_ROOT,
    HISTORY_ROOT,
    MODELS_ROOT,
    PODCAST_WAV,
    REPORTS_ROOT,
    UI_ROOT,
)
```

- [ ] **Step 2: Add the endpoint**

In `src/vad_bench/api.py`, add right after `api_results_one` (which ends at line 189 with `return JSONResponse(json.loads(path.read_text(encoding="utf-8")))`):

```python
    @app.get("/api/chunks/{config}/{index}")
    def api_chunk_audio(config: str, index: int):
        from .runner import _slug
        path = CHUNKS_ROOT / _slug(config) / f"{index:04d}.wav"
        if not path.exists():
            raise HTTPException(404, f"chunk not available: {config}/{index}")
        return FileResponse(path, media_type="audio/wav")
```

- [ ] **Step 3: Manual smoke test**

Run: `python -m pytest tests/test_auth.py -v` (confirms `create_app()` still builds cleanly with the new route registered)
Expected: PASS — all 4 auth tests still pass, confirming the app still constructs without error.

Then start the server and check the 404 path by hand:

Run: `python -c "from src.vad_bench.api import create_app; from fastapi.testclient import TestClient; c=TestClient(create_app()); import base64; h={'Authorization':'Basic '+base64.b64encode(b'x:'+__import__('src.vad_bench.config',fromlist=['get_settings']).get_settings().auth_password.encode()).decode()}; r=c.get('/api/chunks/nonexistent/0', headers=h); print(r.status_code)"`
Expected: `404`

- [ ] **Step 4: Commit**

```bash
git add src/vad_bench/api.py
git commit -m "Add GET /api/chunks/{config}/{index} endpoint"
```

---

## Task 6: `ui/app.js` + `ui/style.css` — chunk list in VAD breakdown, auto-play on Run

**Files:**
- Modify: `ui/app.js`
- Modify: `ui/style.css`

**Interfaces:**
- Consumes: `d.chunks_available` and `d.segments` from the `/api/results/{config}` response (already present via `RunMetrics.to_dict()` after Task 3/4); existing helpers `fmtMmSs()`, `escapeHtml()`, `truncate()`, `$()`.
- Produces: nothing consumed by other tasks — this is the last task.

- [ ] **Step 1: Add i18n keys**

In `ui/app.js`, in the `en` block of `I18N`, add after the existing `"vad.emptyTimeline": "(audio timeline)",` line:

```javascript
    "vad.chunks.title":     "Audio chunks sent to Whisper",
    "vad.chunks.idx":       "#",
    "vad.chunks.range":     "Time",
    "vad.chunks.duration":  "Dur.",
    "vad.chunks.text":      "Whisper text",
    "vad.chunks.audio":     "Audio",
    "vad.chunks.unavailable": "Chunk audio is only available for VAD-on configs from the most recent run.",
```

In the `id` block of `I18N`, add after the existing `"vad.emptyTimeline": "(timeline audio)",` line:

```javascript
    "vad.chunks.title":     "Potongan audio yang dikirim ke Whisper",
    "vad.chunks.idx":       "#",
    "vad.chunks.range":     "Waktu",
    "vad.chunks.duration":  "Durasi",
    "vad.chunks.text":      "Teks Whisper",
    "vad.chunks.audio":     "Audio",
    "vad.chunks.unavailable": "Potongan audio hanya tersedia untuk config VAD-on pada run terakhir.",
```

- [ ] **Step 2: Render the chunk list inside `renderVadBreakdown()`**

In `ui/app.js`, `renderVadBreakdown(d, refSegments)` currently ends with:

```javascript
    <table class="vad-regions-table">
      <thead>
        <tr>
          <th>${t("vad.regions.idx")}</th>
          <th>${t("vad.regions.range")}</th>
          <th class="num">${t("vad.regions.duration")}</th>
          <th>${t("vad.regions.gtText")}</th>
          <th>${t("vad.regions.hypText")}</th>
          <th class="num">${t("vad.regions.match")}</th>
        </tr>
      </thead>
      <tbody>
        ${perRegion.map(r => `
          <tr>
            <td>${r.index + 1}</td>
            <td><span class="muted">${fmtMmSs(r.start)}–${fmtMmSs(r.end)}</span></td>
            <td class="num">${r.duration.toFixed(1)}s</td>
            <td>${escapeHtml(truncate(r.refText, 80))}</td>
            <td>${escapeHtml(truncate(r.hypText, 80))}</td>
            <td class="num ${matchCls(r.overlap)}" title="overlap=${r.overlap.toFixed(2)}">${(r.matchScore * 100).toFixed(0)}%</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}
```

Change the closing to append a new chunk-list section, using `d.config` for the API path (the function's `d` parameter is the full detail response, which already carries `config`):

```javascript
    <table class="vad-regions-table">
      <thead>
        <tr>
          <th>${t("vad.regions.idx")}</th>
          <th>${t("vad.regions.range")}</th>
          <th class="num">${t("vad.regions.duration")}</th>
          <th>${t("vad.regions.gtText")}</th>
          <th>${t("vad.regions.hypText")}</th>
          <th class="num">${t("vad.regions.match")}</th>
        </tr>
      </thead>
      <tbody>
        ${perRegion.map(r => `
          <tr>
            <td>${r.index + 1}</td>
            <td><span class="muted">${fmtMmSs(r.start)}–${fmtMmSs(r.end)}</span></td>
            <td class="num">${r.duration.toFixed(1)}s</td>
            <td>${escapeHtml(truncate(r.refText, 80))}</td>
            <td>${escapeHtml(truncate(r.hypText, 80))}</td>
            <td class="num ${matchCls(r.overlap)}" title="overlap=${r.overlap.toFixed(2)}">${(r.matchScore * 100).toFixed(0)}%</td>
          </tr>
        `).join("")}
      </tbody>
    </table>

    ${renderChunkList(d)}
  `;
}

function renderChunkList(d) {
  if (!d.chunks_available) {
    return `<div class="vad-chunks-unavailable muted">${t("vad.chunks.unavailable")}</div>`;
  }
  const rows = (d.segments || []).map((s, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><span class="muted">${fmtMmSs(s.start)}–${fmtMmSs(s.end)}</span></td>
      <td class="num">${(s.end - s.start).toFixed(1)}s</td>
      <td>${escapeHtml(truncate(s.text, 100))}</td>
      <td><audio controls preload="none" src="/api/chunks/${encodeURIComponent(d.config)}/${i}"></audio></td>
    </tr>
  `).join("");
  return `
    <div class="vad-chunks">
      <h3>${t("vad.chunks.title")}</h3>
      <table class="vad-regions-table vad-chunks-table">
        <thead>
          <tr>
            <th>${t("vad.chunks.idx")}</th>
            <th>${t("vad.chunks.range")}</th>
            <th class="num">${t("vad.chunks.duration")}</th>
            <th>${t("vad.chunks.text")}</th>
            <th>${t("vad.chunks.audio")}</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}
```

- [ ] **Step 3: Auto-play the source podcast on Run click**

In `ui/app.js`, change:

```javascript
$("#btn-run").addEventListener("click", async () => {
  const configs = collectConfigs();
  if (configs.length === 0) { alert(t("run.emptyAlert")); return; }
  if (RUNNING) { return; }
```

to:

```javascript
$("#btn-run").addEventListener("click", async () => {
  $("#audio-player").play().catch(() => {});
  const configs = collectConfigs();
  if (configs.length === 0) { alert(t("run.emptyAlert")); return; }
  if (RUNNING) { return; }
```

(Fires first, inside the click's user-gesture context, before the empty-config check — so autoplay works even if the click is later aborted by validation, matching the spec's "before the fetch() call" requirement while keeping it the literal first line of the handler.)

- [ ] **Step 4: Add chunk-list styling**

In `ui/style.css`, after the existing `.vad-regions-table` rules block (ends at the `.vad-regions-table .match-none` rule, just before the `/* ─── Footer ─────` comment), add:

```css
/* Chunk list (audio-per-segment) */
.vad-chunks { margin-top: 18px; }
.vad-chunks h3 {
  font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;
  text-transform: uppercase; letter-spacing: 0.06em; font-family: var(--mono);
}
.vad-chunks-table audio { width: 220px; height: 32px; display: block; }
.vad-chunks-unavailable { padding: 14px 0; font-family: var(--mono); font-size: 12px; }
```

- [ ] **Step 5: Manual UI smoke test**

Run: `python -m vad_bench.api` (or however the dev server is normally started — check README/scripts if this doesn't match) then open the dashboard in a browser, run a benchmark with a VAD-on config, and verify:
1. Clicking "Run benchmark" starts audio playback immediately.
2. After the run completes, the "VAD breakdown" tab for the VAD-on config shows a new "Audio chunks sent to Whisper" section with one row per segment, each with a playable `<audio>` element.
3. Selecting a VAD-off config shows the "Potongan audio hanya tersedia..." note instead.

Expected: all three behaviors observed; no console errors; no broken audio elements (no chunk row should show a 404 error when the config is VAD-on and was in the latest run).

- [ ] **Step 6: Commit**

```bash
git add ui/app.js ui/style.css
git commit -m "Show per-chunk audio+text in VAD breakdown; auto-play podcast on Run"
```

---

## Self-Review

**Spec coverage:**
- Slice source WAV per VAD-detected region, VAD-on only → Task 2 + Task 4 Step 3 ✓
- Persist chunk audio for latest run only → Task 4 Step 2 (wipe `CHUNKS_ROOT` at run start) ✓
- Persist chunk text+timing in history indefinitely (50-run retention, unchanged) → Task 4 Step 5 ✓
- Surface chunks in VAD breakdown tab as playable list → Task 6 Step 2 ✓
- Auto-play source podcast on Run click → Task 6 Step 3 ✓
- `slice_wav_segments` signature and stdlib-`wave` behavior → Task 2 ✓
- `chunks_available` field end-to-end (RunMetrics → to_dict → API → UI gate) → Task 3, Task 4 Step 4, Task 6 Step 2 ✓
- `GET /api/chunks/{config}/{index}` with 404 on missing → Task 5 ✓
- `tests/test_audio.py` slice test → Task 2 Step 1 ✓
- i18n keys `vad.chunks.*` in en+id → Task 6 Step 1 ✓
- Error handling: empty segments no-op, missing file 404/quiet-note, zero-duration segment writes valid empty WAV rather than raising → Task 2 (empty-list test + natural behavior of `readframes(0)` returning `b""`, which `writeframes` accepts) ✓

**Placeholder scan:** No TBD/TODO markers; every step has complete code and exact commands.

**Type consistency:** `slice_wav_segments(src: Path, segments: list[tuple[float,float,str]], out_dir: Path) -> None` used identically in Task 2 (definition) and Task 4 Step 3 (call site with `result.segments`, `CHUNKS_ROOT / _slug(name)`). `RunMetrics.chunks_available: bool` defined in Task 3, set in Task 4 Step 4, read in Task 6 Step 2 as `d.chunks_available`. `_record_from_metrics()`'s new `"segments"` key matches the `{start,end,text}` shape already used elsewhere (e.g. `to_dict()`'s `segments` list, `/api/reference/segments`'s normalized shape) — the UI's `renderChunkList` reads `s.start`/`s.end`/`s.text` consistently with this shape.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-08-audio-chunk-review.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
