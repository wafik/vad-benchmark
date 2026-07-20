# Task 5 Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicit control/candidate comparisons flow from the dashboard to the runner, reject invalid pairs, suppress sweep recommendations, and render the normalized resource payload faithfully.

**Architecture:** The API validates optional pair query parameters against the submitted config names and forwards valid values unchanged to `runner.run`. The verdict remains pure: it refuses runs with any count other than two and compares every declared `Settings` field except `vad_mode`. Vanilla JS owns two native selects that synchronize with config cards and submits both values alongside the JSON configs.

**Tech Stack:** FastAPI, Pydantic settings, pytest, vanilla JavaScript.

## Global Constraints

- Do not create a commit.
- Write each test before its production behavior and run it red first.
- Accept pair names for sweeps but always return no verdict when config count is not exactly two.
- Render normalized resource keys with their specified units; `null` is rendered as `unavailable`.

---

### Task 1: Validate and Forward Explicit Pairs

**Files:**
- Modify: `tests/test_api_run_readiness.py`
- Modify: `src/vad_bench/api.py:193-234`

**Interfaces:**
- Consumes: `configs: str | None`, `control_name: str | None`, `candidate_name: str | None`.
- Produces: `background.add_task(run_benchmark, cfgs, verbose=True, control_name=..., candidate_name=...)`.

- [ ] **Step 1: Write the failing API handoff and validation tests**

```python
def test_run_forwards_explicit_pair_names(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "run_benchmark", lambda *args, **kwargs: calls.append((args, kwargs)))
    client = _ready_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/run",
        headers=AUTH,
        params={
            "configs": '[{"name":"off","overrides":{"vad_mode":"off"}},{"name":"on","overrides":{"vad_mode":"builtin"}}]',
            "control_name": "off",
            "candidate_name": "on",
        },
    )

    assert response.json()["ok"] is True
    assert calls[0][1]["control_name"] == "off"
    assert calls[0][1]["candidate_name"] == "on"

def test_run_rejects_invalid_explicit_pair(tmp_path, monkeypatch):
    client = _ready_client(tmp_path, monkeypatch)
    response = client.post(
        "/api/run",
        headers=AUTH,
        params={"configs": '[{"name":"off","overrides":{}}]', "control_name": "off"},
    )

    assert response.status_code == 400
```

- [ ] **Step 2: Run the API tests and verify they fail because pair parameters are ignored**

Run: `rtk uv run pytest tests/test_api_run_readiness.py -q`

Expected: FAIL for missing handoff or validation.

- [ ] **Step 3: Add minimal parameter validation and runner handoff**

```python
if bool(control_name) != bool(candidate_name):
    raise HTTPException(400, "control_name and candidate_name must be supplied together")
if control_name and (control_name == candidate_name or {control_name, candidate_name} - names):
    raise HTTPException(400, "control_name and candidate_name must be distinct submitted configs")

background.add_task(
    run_benchmark, cfgs, verbose=True,
    control_name=control_name, candidate_name=candidate_name,
)
```

- [ ] **Step 4: Run the API tests and verify they pass**

Run: `rtk uv run pytest tests/test_api_run_readiness.py -q`

Expected: PASS.

### Task 2: Enforce Verdict Eligibility and Full Settings Equality

**Files:**
- Modify: `tests/test_verdict.py`
- Modify: `src/vad_bench/verdict.py:7-47`

**Interfaces:**
- Consumes: iterable result records with `config` and `effective_settings`.
- Produces: `None` for sweeps, invalid pairs, or unequal effective settings; a text verdict only for exactly two comparable records.

- [ ] **Step 1: Write failing sweep and all-settings mismatch tests**

```python
def test_verdict_rejects_named_pair_in_a_sweep():
    records = _comparable_records() + [{"config": "third", "vad_mode": "builtin", "effective_settings": {}}]
    assert build_verdict(records, "off", "on") is None

def test_verdict_rejects_every_settings_field_except_vad_mode():
    records = _comparable_records()
    records[1]["effective_settings"] = {
        **records[1]["effective_settings"],
        "serve_port": 9999,
    }
    assert build_verdict(records, "off", "on") is None
```

- [ ] **Step 2: Run the verdict tests and verify they fail**

Run: `rtk uv run pytest tests/test_verdict.py -q`

Expected: FAIL because a sweep is eligible and unlisted effective settings are not compared reliably.

- [ ] **Step 3: Implement the minimal eligibility and comparison rules**

```python
records = list(records)
if len(records) != 2 or not control_name or not candidate_name or control_name == candidate_name:
    return None

settings = record.get("effective_settings")
return {
    key: value
    for key, value in settings.items()
    if key in Settings.model_fields and key != "vad_mode"
}
```

Non-`Settings` runtime metadata is ignored only when present in `effective_settings`; every actual `Settings` field is compared.

- [ ] **Step 4: Run the verdict tests and verify they pass**

Run: `rtk uv run pytest tests/test_verdict.py -q`

Expected: PASS.

### Task 3: Synchronize Pair Controls and Render Resource Schema

**Files:**
- Modify: `ui/index.html:89-97`
- Modify: `ui/app.js:534-692,833-851`
- Modify: `tests/test_ui_contract.py`

**Interfaces:**
- Consumes: config-card names and `summary.resources` keys `cpu_avg_percent`, `cpu_peak_percent`, `rss_peak_mib`, `gpu_memory_peak_mib`, and `gpu_temp_peak_c`.
- Produces: `control_name` and `candidate_name` query parameters on `/api/run`; resource strings with `%`, `MiB`, or `C`, and `unavailable` for `null`.

- [ ] **Step 1: Write the failing static UI contract test**

```python
def test_ui_submits_pair_selection_and_normalized_resources():
    source = APP_JS.read_text(encoding="utf-8")

    assert 'id="control-name"' in source
    assert 'id="candidate-name"' in source
    assert 'params.set("control_name", controlName)' in source
    assert 'params.set("candidate_name", candidateName)' in source
    for key in ("cpu_avg_percent", "cpu_peak_percent", "rss_peak_mib", "gpu_memory_peak_mib", "gpu_temp_peak_c"):
        assert key in source
    assert '"unavailable"' in source
```

- [ ] **Step 2: Run the UI contract test and verify it fails**

Run: `rtk uv run pytest tests/test_ui_contract.py -q`

Expected: FAIL because no pair controls or normalized resource renderer exists.

- [ ] **Step 3: Add native select synchronization, request params, and schema renderer**

```javascript
function syncPairSelects() {
  const names = $$(".config-name-input").map(input => input.value.trim()).filter(Boolean);
  [$("#control-name"), $("#candidate-name")].forEach(select => {
    const value = select.value;
    select.innerHTML = names.map(name => `<option value="${escapeAttr(name)}">${escapeHtml(name)}</option>`).join("");
    select.value = names.includes(value) ? value : names[select === $("#control-name") ? 0 : 1] || names[0] || "";
  });
}
```

Call `syncPairSelects` after config renders, removals, and name edits. Build request parameters with both select values. Render each normalized resource key through a single local formatter that returns `unavailable` for `null`/`undefined` and appends its defined unit.

- [ ] **Step 4: Run the UI contract test and verify it passes**

Run: `rtk uv run pytest tests/test_ui_contract.py -q`

Expected: PASS.

### Task 4: Full Verification

**Files:**
- Verify: repository test suite and diff whitespace.

- [ ] **Step 1: Run the full suite**

Run: `rtk uv run pytest -q`

Expected: PASS.

- [ ] **Step 2: Run the diff check**

Run: `git diff --check`

Expected: no output.
