# Jetson Telemetry and History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect accurate Jetson Nano telemetry, display it live and per-run, and page benchmark history.

**Architecture:** `sysmon.py` will normalize `tegrastats` data into the existing system sample shape, falling back to psutil and `nvidia-smi` outside Jetson. The runner persists only aggregate samples in each immutable run artifact. The API pages the history index, while the static dashboard renders resource status and drives the page query.

**Tech Stack:** Python 3.10+, FastAPI, psutil, Jetson `tegrastats`, vanilla JavaScript/CSS, pytest.

## Global Constraints

- Prefer `tegrastats` on Jetson; retain best-effort psutil and `nvidia-smi` fallback elsewhere.
- Missing fields are `null`, never zero, and telemetry errors must not interrupt a run.
- Poll live telemetry every three seconds; sample active runs every two seconds.
- Warn at 75 percent, mark critical at 90 percent, and warn at 80 C.
- Persist aggregate summaries only, never raw time-series data.
- Preserve immutable history artifacts and do not create a commit unless the user requests one.

---

### Task 1: Normalize Jetson telemetry

**Files:**
- Modify: `src/vad_bench/sysmon.py`
- Modify: `tests/test_sysmon.py`

**Interfaces:**
- Produces: `parse_tegrastats(line: str) -> dict[str, object] | None` and enriched `SystemSample` fields consumed by `sample_dict()` and `ResourceMonitor`.
- Produces: `sample_dict() -> dict` with `cpu_cores_percent`, `swap_used_mb`, `swap_total_mb`, `gpu_util_percent`, `gpu_mem_used_mb`, `gpu_mem_total_mb`, `cpu_temp_c`, `gpu_temp_c`, `power_mw`, `clocks_mhz`, `warning_state`, and `timestamp`.

- [ ] **Step 1: Write failing parser and fallback tests**

```python
from vad_bench.sysmon import parse_tegrastats


def test_parse_tegrastats_normalizes_jetson_fields():
    sample = parse_tegrastats(
        "RAM 1200/3964MB (lfb 2x4MB) SWAP 32/1982MB (cached 0MB) "
        "CPU [12%@1479,25%@1479,off,50%@1479] EMC_FREQ 5%@1600 "
        "GR3D_FREQ 71%@921 PLL@42C CPU@51C GPU@49C VDD_IN 2840/2750"
    )

    assert sample["cpu_cores_percent"] == [12.0, 25.0, None, 50.0]
    assert sample["ram_used_mb"] == 1200.0
    assert sample["swap_used_mb"] == 32.0
    assert sample["gpu_util_percent"] == 71.0
    assert sample["cpu_temp_c"] == 51.0
    assert sample["gpu_temp_c"] == 49.0
    assert sample["power_mw"] == 2840.0


def test_parse_tegrastats_rejects_unrecognized_output():
    assert parse_tegrastats("not a tegrastats record") is None
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `rtk uv run pytest tests/test_sysmon.py -q`

Expected: FAIL because `parse_tegrastats` does not exist.

- [ ] **Step 3: Implement the minimal Jetson collector**

```python
import re


def parse_tegrastats(line: str) -> dict[str, object] | None:
    """Normalize one tegrastats record without raising on missing fields."""
    ram = re.search(r"\bRAM (\d+)/(\d+)MB", line)
    cpu = re.search(r"\bCPU \[([^]]+)\]", line)
    if not ram or not cpu:
        return None
    cores = [
        float(match.group(1)) if (match := re.match(r"(\d+(?:\.\d+)?)%@", item.strip())) else None
        for item in cpu.group(1).split(",")
    ]
    def number(pattern: str, group: int = 1) -> float | None:
        match = re.search(pattern, line)
        return float(match.group(group)) if match else None
    return {
        "cpu_cores_percent": cores,
        "ram_used_mb": float(ram.group(1)),
        "ram_total_mb": float(ram.group(2)),
        "swap_used_mb": number(r"\bSWAP (\d+)/"),
        "swap_total_mb": number(r"\bSWAP \d+/(\d+)MB"),
        "gpu_util_percent": number(r"\bGR3D_FREQ (\d+)%"),
        "gpu_clock_mhz": number(r"\bGR3D_FREQ \d+%@?(\d+)?"),
        "cpu_temp_c": number(r"\bCPU@(\d+(?:\.\d+)?)C"),
        "gpu_temp_c": number(r"\bGPU@(\d+(?:\.\d+)?)C"),
        "power_mw": number(r"\bVDD_IN (\d+)/"),
    }


def _read_tegrastats() -> dict[str, object] | None:
    if not shutil.which("tegrastats"):
        return None
    try:
        output = subprocess.check_output(["tegrastats", "--interval", "1", "--count", "1"], text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_tegrastats(output.splitlines()[-1]) if output.splitlines() else None
```

Merge a valid Jetson reading into `SystemSample`, and otherwise retain the existing psutil and `nvidia-smi` fields.

- [ ] **Step 4: Add threshold state tests and implementation**

```python
def test_warning_state_is_critical_for_90_percent_load_or_80c_temperature():
    assert warning_state(cpu_percent=90.0, gpu_percent=None, temp_c=None) == "critical"
    assert warning_state(cpu_percent=12.0, gpu_percent=76.0, temp_c=None) == "warning"
    assert warning_state(cpu_percent=12.0, gpu_percent=None, temp_c=80.0) == "warning"
    assert warning_state(cpu_percent=12.0, gpu_percent=None, temp_c=40.0) == "normal"
```

```python
def warning_state(*, cpu_percent: float | None, gpu_percent: float | None, temp_c: float | None) -> str:
    if any(value is not None and value >= 90 for value in (cpu_percent, gpu_percent)):
        return "critical"
    if any(value is not None and value >= 75 for value in (cpu_percent, gpu_percent)) or (temp_c is not None and temp_c >= 80):
        return "warning"
    return "normal"
```

- [ ] **Step 5: Run telemetry tests**

Run: `rtk uv run pytest tests/test_sysmon.py -q`

Expected: PASS.

### Task 2: Persist complete per-run resource summaries

**Files:**
- Modify: `src/vad_bench/sysmon.py`
- Modify: `src/vad_bench/runner.py`
- Modify: `tests/test_sysmon.py`
- Modify: `tests/test_runner.py`

**Interfaces:**
- Consumes: normalized `SystemSample` values from Task 1.
- Produces: `ResourceMonitor.summary() -> dict[str, float | None]` with average/peak CPU, RAM, swap, GPU, temperatures, disk, power, and elapsed warning/high-load seconds.
- Produces: `summary["resources"]` and immutable history snapshots containing this dict.

- [ ] **Step 1: Write failing aggregation tests**

```python
def test_resource_summary_aggregates_jetson_fields_and_elapsed_status():
    monitor = ResourceMonitor(interval_s=2.0)
    monitor._samples = [
        SystemSample(cpu_percent=50.0, ram_percent=40.0, swap_used_mb=10.0, gpu_util_percent=20.0, cpu_temp_c=60.0, gpu_temp_c=55.0, power_mw=2000.0, warning_state="normal"),
        SystemSample(cpu_percent=95.0, ram_percent=60.0, swap_used_mb=30.0, gpu_util_percent=80.0, cpu_temp_c=82.0, gpu_temp_c=75.0, power_mw=3000.0, warning_state="critical"),
    ]

    assert monitor.summary()["gpu_peak_percent"] == 80.0
    assert monitor.summary()["swap_peak_mib"] == 30.0
    assert monitor.summary()["cpu_temp_peak_c"] == 82.0
    assert monitor.summary()["high_load_seconds"] == 2.0
    assert monitor.summary()["thermal_warning_seconds"] == 2.0
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `rtk uv run pytest tests/test_sysmon.py::test_resource_summary_aggregates_jetson_fields_and_elapsed_status -q`

Expected: FAIL because the new sample fields and summary keys are absent.

- [ ] **Step 3: Implement aggregation and persist it unchanged**

```python
def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _peak(values: list[float]) -> float | None:
    return round(max(values), 1) if values else None
```

Use the helpers in `ResourceMonitor.summary()`. Count warning sample intervals using `self.interval_s`; keep unavailable values `None`. Confirm `_save_to_history()` copies `summary["resources"]` into its snapshot without reformatting or dropping fields.

- [ ] **Step 4: Add history persistence regression test**

```python
def test_history_snapshot_preserves_resource_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "HISTORY_ROOT", tmp_path)
    runner._save_to_history(
        {"resources": {"gpu_peak_percent": 80.0, "cpu_temp_peak_c": 82.0}},
        [], "2026-07-13T00:00:00Z", "run-1", "reports/history/run-1.manifest.json",
    )
    assert json.loads((tmp_path / "run-1.json").read_text())["resources"]["gpu_peak_percent"] == 80.0
```

- [ ] **Step 5: Run resource and runner tests**

Run: `rtk uv run pytest tests/test_sysmon.py tests/test_runner.py -q`

Expected: PASS.

### Task 3: Page the history API

**Files:**
- Modify: `src/vad_bench/api.py`
- Create: `tests/test_api_history.py`

**Interfaces:**
- Produces: `GET /api/history?page=1&page_size=20` returning `{runs, page, page_size, total, total_pages}` newest-first.
- Produces: invalid/nonpositive page inputs as HTTP 422 through FastAPI integer constraints.

- [ ] **Step 1: Write failing API pagination tests**

```python
def test_history_returns_newest_page_and_metadata(client, history_root):
    (history_root / "index.json").write_text(json.dumps([{"id": "old"}, {"id": "new"}]))

    response = client.get("/api/history?page=1&page_size=1")

    assert response.status_code == 200
    assert response.json() == {
        "runs": [{"id": "new"}], "page": 1, "page_size": 1, "total": 2, "total_pages": 2,
    }


def test_history_returns_empty_last_page_without_reading_detail_files(client):
    response = client.get("/api/history?page=9&page_size=20")
    assert response.status_code == 200
    assert response.json()["runs"] == []
```

- [ ] **Step 2: Run the focused API test and verify failure**

Run: `rtk uv run pytest tests/test_api_history.py -q`

Expected: FAIL because the endpoint returns only `runs`.

- [ ] **Step 3: Add bounded pagination to the index endpoint**

```python
@app.get("/api/history")
def api_history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)):
    runs = _read_history_index()
    newest = list(reversed(runs))
    total = len(newest)
    start = (page - 1) * page_size
    return {
        "runs": newest[start:start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, math.ceil(total / page_size)),
    }
```

Use a small private `_read_history_index()` that preserves current malformed/missing-index behavior as an empty list. Import `Query` and `math`; do not change the immutable detail endpoint.

- [ ] **Step 4: Run API tests**

Run: `rtk uv run pytest tests/test_api_history.py tests/test_api_run_readiness.py -q`

Expected: PASS.

### Task 4: Render telemetry and paginated history accessibly

**Files:**
- Modify: `ui/index.html`
- Modify: `ui/style.css`
- Modify: `ui/app.js`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: `/api/system` response from Task 1, run `resources` from Task 2, and paged history response from Task 3.
- Produces: live resource cards with explicit unavailable states and `#history-pagination` controls.

- [ ] **Step 1: Write failing static UI contract assertions**

```python
def test_ui_has_jetson_telemetry_and_history_pagination_contract():
    source = APP_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    for metric in ("cpu", "ram", "swap", "gpu", "gpu-memory", "cpu-temp", "gpu-temp", "disk"):
        assert f'data-metric="{metric}"' in html
    assert 'id="history-pagination"' in html
    assert 'params.set("page", page)' in source
    assert 'warning_state' in source
    assert 'not available on this host' in source
```

- [ ] **Step 2: Run the focused UI contract and verify failure**

Run: `rtk uv run pytest tests/test_ui_contract.py::test_ui_has_jetson_telemetry_and_history_pagination_contract -q`

Expected: FAIL because the cards and controls do not exist.

- [ ] **Step 3: Add the smallest complete UI**

```html
<nav id="history-pagination" aria-label="History pages" hidden>
  <button type="button" id="history-prev">Previous</button>
  <span id="history-page-status" aria-live="polite"></span>
  <button type="button" id="history-next">Next</button>
</nav>
```

Render all telemetry through a shared `setSysmonCard(id, percent, value, detail, available)` helper. Apply `sysmon-warn` at 75 percent, `sysmon-critical` at 90 percent, and the same severity state for temperature. Display each optional sensor only when its normalized value exists. Render stored resource summaries in the latest-result and selected-history detail using the existing `formatResource` helper.

- [ ] **Step 4: Add paged fetch and keyboard-safe controls**

```javascript
let historyPage = 1;
const HISTORY_PAGE_SIZE = 20;

async function refreshHistory(page = historyPage) {
  const params = new URLSearchParams({ page, page_size: HISTORY_PAGE_SIZE });
  const response = await fetch(`/api/history?${params}`);
  const payload = await response.json();
  historyPage = payload.page;
  renderHistory(payload.runs);
  renderHistoryPagination(payload);
}
```

Disable previous/next at their boundaries, update `#history-page-status` with current page and total runs, and call `refreshHistory(historyPage - 1)` or `refreshHistory(historyPage + 1)` from button handlers.

- [ ] **Step 5: Run UI checks**

Run: `rtk uv run pytest tests/test_ui_contract.py -q; rtk node --check ui/app.js`

Expected: all tests PASS and JavaScript syntax check exits 0.

### Task 5: Verify end-to-end on Jetson

**Files:**
- Modify: `README.md`

**Interfaces:**
- Documents: telemetry source, fallback behavior, history pagination, and required `tegrastats` availability.

- [ ] **Step 1: Document telemetry behavior**

```markdown
### Jetson telemetry

On Jetson, the dashboard reads `tegrastats` for GPU and thermal values. Other
hosts use best-effort psutil and `nvidia-smi` values. Unavailable sensors are
shown as unavailable and do not invalidate a benchmark result.
```

- [ ] **Step 2: Run the complete local regression suite**

Run: `rtk uv run pytest tests/ -q; rtk node --check ui/app.js; rtk git diff --check`

Expected: all tests pass, JavaScript syntax check exits 0, and no whitespace errors.

- [ ] **Step 3: Deploy changed source and UI with the approved Jetson transport**

Run: `rtk scp src/vad_bench/sysmon.py src/vad_bench/runner.py src/vad_bench/api.py ui/index.html ui/app.js ui/style.css README.md jetson-nano-ssh:/home/nvidia/vad-benchmark/`

Expected: transfer succeeds without overwriting `/home/nvidia/vad-benchmark/.env`, `models/`, or `reports/`.

- [ ] **Step 4: Verify Jetson live telemetry, one completed run, and page navigation**

Run: `rtk ssh jetson-nano-ssh "cd /home/nvidia/vad-benchmark && PYTHONPATH=src .venv/bin/python -c 'from vad_bench.sysmon import sample_dict; import json; print(json.dumps(sample_dict()))'"`

Expected: response includes non-null Jetson GPU utilization and at least one temperature when `tegrastats` reports them. Run one benchmark and verify its history detail shows `resources`; request `/api/history?page=2&page_size=1` and confirm pagination metadata.
