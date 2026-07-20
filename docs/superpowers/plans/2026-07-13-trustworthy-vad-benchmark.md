# Trustworthy VAD Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce explicit, reproducible, end-to-end VAD benchmark results that cannot silently mix pipelines or hide metric failures.

**Architecture:** Replace `vad_enabled` with one declared `vad_mode` across configuration, execution, artifacts, and rendering. The runner owns end-to-end timing and run identity, while the engine reports only execution component timing. A per-run manifest links immutable inputs and environment identity to each result.

**Tech Stack:** Python 3.11, FastAPI, Pydantic settings, jiwer, psutil, vanilla JavaScript, pytest, uv.

## Global Constraints

- Use only `off`, `builtin`, and `presegmented` as VAD modes.
- `builtin` is the canonical `whisper-cli --vad --vad-model` candidate; no mode fallback is permitted.
- Rank and verdict on `total_s / audio_duration_s`, not decoder-only time.
- Keep the bundled dataset labelled exploratory with a silver reference.
- Do not introduce a dependency for hashing, manifest collection, or timing.
- Do not commit unless the user explicitly requests it.

---

### Task 1: Declare Explicit VAD Modes

**Files:**
- Modify: `src/vad_bench/config.py`
- Modify: `src/vad_bench/engine.py`
- Modify: `src/vad_bench/api.py`
- Modify: `scripts/run_benchmark.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_api_run_readiness.py`

**Interfaces:**
- Produces `Settings.vad_mode: Literal["off", "builtin", "presegmented"]`.
- Produces `Settings.vad_enabled -> bool` as the derived condition `vad_mode != "off"` for internal read-only use.
- Consumes `Settings.vad_mode` in `_whisper_flags()` and readiness validation.

- [ ] **Step 1: Write failing mode-command tests**

```python
def test_builtin_mode_adds_whisper_vad_flags(tmp_path):
    settings = Settings(vad_mode="builtin")
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", settings)
    assert "--vad" in cmd

def test_presegmented_mode_omits_whisper_vad_flags(tmp_path):
    settings = Settings(vad_mode="presegmented")
    cmd, _ = _resolve_cmd("whisper-cli", tmp_path / "m.bin", tmp_path / "v.bin", tmp_path / "a.wav", settings, skip_vad=True)
    assert "--vad" not in cmd
```

- [ ] **Step 2: Run the targeted tests and observe failure**

Run: `uv run --extra dev pytest tests/test_engine.py -q`

Expected: failures because `vad_mode` is not a settings field.

- [ ] **Step 3: Add mode validation and command selection**

```python
from typing import Literal

class Settings(BaseSettings):
    vad_mode: Literal["off", "builtin", "presegmented"] = "builtin"

    @property
    def vad_enabled(self) -> bool:
        return self.vad_mode != "off"
```

```python
if s.vad_mode == "builtin" and vad_model_path is not None:
    flags += ["--vad", "--vad-model", _pp(vad_model_path)]
```

Reject invalid `presegmented` readiness when the standalone segment binary is
missing. Update defaults and CLI examples to use `vad_mode=off` and
`vad_mode=builtin`.

- [ ] **Step 4: Run mode and readiness tests**

Run: `uv run --extra dev pytest tests/test_engine.py tests/test_api_run_readiness.py -q`

Expected: PASS.

### Task 2: Measure End-to-End Configuration Time

**Files:**
- Modify: `src/vad_bench/engine.py`
- Modify: `src/vad_bench/runner.py`
- Modify: `src/vad_bench/metrics.py`
- Modify: `tests/test_engine.py`
- Create: `tests/test_runner.py`

**Interfaces:**
- Extends `EngineResult` with `staging_s: float` and `transcription_s: float`.
- Extends `RunMetrics` with `vad_mode`, `total_s`, `segment_prep_s`, `staging_s`, and `transcription_s`.
- `RunMetrics.rtf == total_s / audio_duration_s`.

- [ ] **Step 1: Write a failing timing-boundary test**

```python
def test_score_uses_total_configuration_time(monkeypatch):
    result = EngineResult(transcript="halo", transcription_s=2.0, staging_s=1.0)
    metric = _score(result, "halo", 10.0, vad_mode="presegmented", total_s=5.0, segment_prep_s=2.0)
    assert metric.total_s == 5.0
    assert metric.rtf == 0.5
    assert metric.transcription_s == 2.0
```

- [ ] **Step 2: Run the targeted test and observe failure**

Run: `uv run --extra dev pytest tests/test_runner.py::test_score_uses_total_configuration_time -q`

Expected: failure because timing fields are absent.

- [ ] **Step 3: Implement complete timing ownership in the runner**

```python
config_started = time.perf_counter()
segment_prep_s = 0.0
if settings.vad_mode == "presegmented":
    prep_started = time.perf_counter()
    segments = compute_vad_segments(wav, settings)
    segment_prep_s = time.perf_counter() - prep_started
    if not segments:
        raise RuntimeError("presegmented mode produced no speech segments")
result = transcribe(...)
total_s = time.perf_counter() - config_started
```

In `transcribe()`, measure remote staging separately and rename the old decoder
duration to `transcription_s`. Do not slice UI chunk artifacts into `total_s`;
they are post-result presentation artifacts rather than request-path work.

- [ ] **Step 4: Run timing tests**

Run: `uv run --extra dev pytest tests/test_runner.py tests/test_engine.py -q`

Expected: PASS.

### Task 3: Make Metric Status and Region Scoring Honest

**Files:**
- Modify: `src/vad_bench/metrics.py`
- Modify: `src/vad_bench/runner.py`
- Modify: `tests/test_metrics.py`
- Modify: `tests/test_reference.py`

**Interfaces:**
- `per_region_wer(ref_segments: Sequence[tuple[float, float, str]], hyp_segments)` receives tuples only.
- `RunMetrics.metric_status: Literal["verified", "error"]` and `metric_error: str | None` are serialized.
- `per_region_wer` remains a reference-caption comparison, not VAD-boundary quality.

- [ ] **Step 1: Write failing tests for `Segment` conversion and visible errors**

```python
def test_score_converts_reference_segments_to_metric_tuples():
    refs = [Segment(0.0, 1.0, "halo")]
    metric = _score(EngineResult(transcript="halo"), "halo", 1.0, ref_segments=refs)
    assert metric.per_region_wer[0]["wer"] == 0.0
    assert metric.metric_status == "verified"

def test_score_records_region_metric_failure(monkeypatch):
    monkeypatch.setattr("vad_bench.runner.per_region_wer", lambda *_: (_ for _ in ()).throw(ValueError("bad regions")))
    metric = _score(EngineResult(transcript="halo"), "halo", 1.0, ref_segments=[])
    assert metric.metric_status == "error"
    assert metric.metric_error == "bad regions"
```

- [ ] **Step 2: Run the target tests and observe failure**

Run: `uv run --extra dev pytest tests/test_metrics.py tests/test_runner.py -q`

Expected: failures because `Segment` is unpacked directly and failures are swallowed.

- [ ] **Step 3: Convert at the boundary and serialize status**

```python
region_refs = [(segment.start_s, segment.end_s, segment.text) for segment in ref_segments]
try:
    per_region = per_region_wer(region_refs, result.segments)
    metric_status, metric_error = "verified", None
except Exception as exc:
    per_region, metric_status, metric_error = [], "error", str(exc)
```

Persist both status fields. Keep overall WER/CER valid when only the optional
region view fails.

- [ ] **Step 4: Run metric tests**

Run: `uv run --extra dev pytest tests/test_metrics.py tests/test_reference.py tests/test_runner.py -q`

Expected: PASS.

### Task 4: Persist an Immutable Run Manifest

**Files:**
- Create: `src/vad_bench/manifest.py`
- Modify: `src/vad_bench/paths.py`
- Modify: `src/vad_bench/runner.py`
- Modify: `src/vad_bench/metrics.py`
- Create: `tests/test_manifest.py`

**Interfaces:**
- `sha256_file(path: Path) -> str` streams in 1 MiB blocks.
- `build_manifest(run_id: str, started_at: str, configs: list[Settings], records: list[dict]) -> dict`.
- `write_manifest(run_id: str, manifest: dict) -> Path` writes
  `reports/history/<run-id>.manifest.json` once.

- [ ] **Step 1: Write failing manifest tests**

```python
def test_sha256_file_is_content_stable(tmp_path):
    path = tmp_path / "input.bin"
    path.write_bytes(b"vad")
    assert sha256_file(path) == "b0c5c9e24c22097842c7617002ec1c18121df29e2d5cf39bda739f2387c1631b"

def test_manifest_links_each_config_to_declared_mode(tmp_path, monkeypatch):
    manifest = build_manifest("run-1", "2026-07-13T00:00:00Z", [Settings(vad_mode="builtin")], [{"config": "candidate"}])
    assert manifest["configs"][0]["vad_mode"] == "builtin"
```

- [ ] **Step 2: Run manifest tests and observe failure**

Run: `uv run --extra dev pytest tests/test_manifest.py -q`

Expected: import failure because `manifest.py` does not exist.

- [ ] **Step 3: Implement a stdlib-only manifest**

```python
def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
```

Collect `platform.uname()`, `os.cpu_count()`, `psutil.virtual_memory().total`,
`git rev-parse HEAD`, `git status --porcelain`, resolved command text, effective
settings, input hashes, and result timings. Tool-version lookup is best effort
and stored as `null` with an error string when unavailable. Add `run_id` and
`manifest_path` to summary records and per-config JSON.

- [ ] **Step 4: Run manifest and runner tests**

Run: `uv run --extra dev pytest tests/test_manifest.py tests/test_runner.py -q`

Expected: PASS.

### Task 5: Restrict Verdicts and Normalize Resources

**Files:**
- Modify: `src/vad_bench/verdict.py`
- Modify: `src/vad_bench/sysmon.py`
- Modify: `src/vad_bench/runner.py`
- Modify: `tests/test_metrics.py`
- Create: `tests/test_verdict.py`
- Create: `tests/test_sysmon.py`

**Interfaces:**
- `build_verdict(records, control_name: str | None, candidate_name: str | None) -> str | None`.
- A record has `vad_mode`, `whisper_model`, `language`, `threads`, `total_s`, and `rtf`.
- Resource aggregate keys are `cpu_avg_percent`, `cpu_peak_percent`,
  `rss_peak_mib`, `gpu_memory_peak_mib`, and `gpu_temp_peak_c`.

- [ ] **Step 1: Write failing verdict/resource tests**

```python
def test_verdict_requires_named_comparable_pair():
    records = [{"config": "off", "vad_mode": "off"}, {"config": "on", "vad_mode": "builtin"}]
    assert build_verdict(records, None, None) is None

def test_verdict_reports_candidate_over_control_slowdown():
    records = comparable_records(control_rtf=0.5, candidate_rtf=1.0)
    assert "2.00x" in build_verdict(records, "off", "on")
```

- [ ] **Step 2: Run target tests and observe failure**

Run: `uv run --extra dev pytest tests/test_verdict.py tests/test_sysmon.py -q`

Expected: failure because pairing and resource schema do not exist.

- [ ] **Step 3: Implement pair validation and one resource schema**

Reject a verdict unless the named records exist and their effective settings are
equal after removing `vad_mode`. Compute slowdown as `candidate_rtf / control_rtf`.
Have `ResourceMonitor.summary` publish process RSS MiB rather than system RAM
percent; preserve unavailable GPU fields as `None`.

- [ ] **Step 4: Run verdict/resource tests**

Run: `uv run --extra dev pytest tests/test_verdict.py tests/test_sysmon.py -q`

Expected: PASS.

### Task 6: Present Result Identity and Limits

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/app.js`
- Modify: `ui/style.css`
- Modify: `README.md`
- Modify: `docs/pipeline-flow.md`
- Modify: `docs/benchmark-audit.md`
- Modify: `tests/test_api_run_readiness.py`

**Interfaces:**
- UI consumes `vad_mode`, `total_s`, component timings, `metric_status`,
  `run_id`, `manifest_path`, `reference_quality`, and the normalized resources.
- API response continues to serve summary/per-config JSON without client-side
  metric reconstruction.

- [ ] **Step 1: Write failing API payload assertions**

```python
def test_summary_result_exposes_run_identity_and_mode(client, tmp_path, monkeypatch):
    write_summary(tmp_path, {"run_id": "run-1", "configs": [{"vad_mode": "builtin", "total_s": 1.0, "metric_status": "verified"}]})
    body = client.get("/api/summary", headers=AUTH).json()
    assert body["run_id"] == "run-1"
    assert body["configs"][0]["vad_mode"] == "builtin"
```

- [ ] **Step 2: Run the API target test and observe failure**

Run: `uv run --extra dev pytest tests/test_api_run_readiness.py -q`

Expected: failure until the fixture uses the new result schema.

- [ ] **Step 3: Render facts rather than inferred labels**

Replace VAD on/off chips with mode names. Show `total_s` and component timing
labels, a manifest/run identifier, `silver reference - exploratory dataset`,
and an explicit metric error badge. Rename the breakdown score text to
`Reference-caption WER/CER`; remove any client-side proxy WER/CER calculation.
Render absent resource fields as `unavailable`.

- [ ] **Step 4: Update operation documentation**

Document mode semantics, timing scope, manifest fields, pairing requirements,
the exploratory dataset caveat, and `make test` as the canonical command.

- [ ] **Step 5: Run full verification**

Run: `uv sync --extra dev`

Run: `uv run --extra dev pytest tests/ -q`

Expected: all tests pass without collection errors.

Run: `git diff --check`

Expected: no output.
