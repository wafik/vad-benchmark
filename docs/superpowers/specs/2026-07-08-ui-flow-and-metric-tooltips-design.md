# VAD Benchmark — UI Flow, Tooltips, Color, Verdict, i18n

**Date:** 2026-07-08 (updated in-session)
**Status:** approved (verbal, in chat)
**Scope:** UI + small backend change (verdict calculation). One new module
(`verdict.py`), updates to `runner.py` and `api.py`. All UI changes in
`ui/index.html`, `ui/style.css`, `ui/app.js`.

## Goal

Make the dashboard legible to a non-ML reviewer (ai4db team) without reading
the docs. Three consecutive iterations:

1. **(Done)** 3-step flow marker + metric tooltips + value color-coding.
2. **(Now)** Verdict sentence computed and stored at run time; UI reordered
   to match the flow; full i18n toggle (EN | ID) with default ID.

## 1. Verdict (backend)

Compute and persist **once per run** so the sentence is stable across
re-renders and history snapshots.

### Source

`src/vad_bench/verdict.py` — new module.

```python
def build_verdict(records: list[dict]) -> str:
    """Indonesian-language one-paragraph verdict comparing every config in
    the run. Returns a single string for embedding in summary.json +
    history."""
```

Inputs: list of `RunMetrics`-shaped dicts (config name, vad_enabled, wer,
cer, rtf, runtime_s, silence_removed, n_segments).

Logic:
- Partition records into `vad_off` and `vad_on`. If only one partition is
  non-empty (or no pair to compare), the verdict describes just that set
  (e.g. baseline-only: "Baseline tanpa VAD mencapai WER X; tidak ada
  pembanding.").
- For the vad_on vs vad_off head-to-head, compute deltas:
  - `Δwer  = wer_on - wer_off` (negative = VAD improves)
  - `Δcer  = cer_on - cer_off`
  - `Δrtf  = rtf_on - rtf_off` (positive = VAD slower)
  - `silence_removed` if available
- Build a short Indonesian sentence with the deltas and a recommendation:
  - if `|Δwer| >= 0.02` → "VAD {'menurunkan' if Δwer<0 else 'meningkatkan'} WER sebesar {pct}%"
  - else → "VAD tidak banyak mengubah WER (Δ < 2%)"
  - always mention RTF direction
  - recommend "aktifkan VAD" if WER improved OR is essentially flat; suggest
    tuning `vad_threshold`/`vad_min_silence_ms` if VAD hurt WER by >2%.

### Where it runs

`runner.py::run()` — after `aggregate(...)`, before writing `summary.json`.
Store as `summary["verdict"] = build_verdict(run_records)`.

`runner.py::_save_to_history()` — copy `summary["verdict"]` into the
`snapshot["verdict"]` field.

`metrics.py::aggregate()` — unchanged (verdict is not aggregate, it's run-level).

### Where it shows

`ui/app.js` — render above the summary tiles, inside the Results panel.
Style: distinct background (`--accent-light`), italic, with a "Verdict"
label. Hidden when the run had no configs / errored out.

### Self-test

`src/vad_bench/verdict.py` ends with `if __name__ == "__main__":` block that
runs on a synthetic record list (off vs on with known deltas) and asserts the
returned string contains the expected substrings. Same shape as the existing
`metrics.py` self-check.

## 2. Reorder panel

New DOM order, top to bottom:

1. Stepper (already at top)
2. **Run panel** (was 3rd)
3. **Results** (was 4th, was hidden until first run)
4. **History** (was 5th)
5. **Audio player** — moved into the Run panel as a small "Audio under test"
   row (it currently lives in its own panel above Run). Makes the run flow
   self-contained: configure → listen to what you're testing → run.
6. **System resources** — bottom, smaller card, demoted to a "context"
   status row (less visual weight). Same data, same polling, just lower
   in the document.
7. Footer (unchanged)

Stepper `data-step-target` IDs get re-pointed to match:
- step 1 → `#run-panel`
- step 2 → `#run-status` (now lives inside Run panel, since audio merged in)
- step 3 → `#results-panel`

In `style.css`, the sysmon panel becomes more compact:
- grid columns collapse to one row at the bottom (4 cards, smaller)
- header gets `muted` styling instead of `panel-head`

No HTML content moves between JS or backend. Just reorder in HTML + tweak
the CSS weight of the sysmon section.

## 3. i18n toggle

### Storage

- `localStorage["vad-bench.lang"]` — `"en"` or `"id"`. Default `"id"` on
  first visit.
- Read once in `init()`, used by `t(key)` helper.

### Strings to translate

Two categories:

**(a) Add `data-i18n="some.key"` attributes** to existing HTML strings — the
**toggle rewrites textContent on load and on language flip**. Affects:
- Topbar title + sub
- Stepper labels (3 keys)
- Section headers (System resources, Audio under test, Run benchmark,
  Results, Run history)
- Run panel toolbar (Add config, Reset to baseline vs silero, Run benchmark)
- Result table headers (Config, VAD, WER, CER, RTF, Runtime, Silence removed,
  Segments, Model)
- Summary tile labels (Best WER, Best CER, Fastest RTF, Total runtime)
- Field labels inside config card (Whisper model, Language, Threads, VAD
  threshold, Min speech, Min silence, Speech pad, Max speech)
- Footer paragraphs
- Verdict label (when present)

**(b) For tooltip strings**, each `<button class="tip">` gets **both**
`data-tip` (EN) and `data-tip-id` (ID). `tTip()` reads the right one based on
current language.

**(c) Verdict itself** — already Indonesian per §1. No translation needed;
`data-i18n` skipped for that block.

### Toggle UI

`<button class="lang-toggle" aria-label="Language">EN | ID</button>` in
topbar-right, after the last-run span. Visually two side-by-side segments:
clicking either switches language; the active segment is bold.

### Bundle

A single `const I18N = { en: {…}, id: {…} }` object near the top of
`app.js`. Keys are dotted (`stepper.configure`, `tooltip.wer`). Each value
is the full string. Keep keys collocated so it's one scan to add a new
translation.

### Wrap up

`init()` calls `applyLanguage()` once at the end. New button click handler
calls `setLanguage('en'|'id')` → updates localStorage + re-runs
`applyLanguage()`. No diffing needed — we just rewrite every matched
node's `textContent`.

## Out of scope (still)

- No DB / no per-user preferences beyond localStorage.
- No language picker dropdowns (just a binary toggle).
- No new deps. No build step.
- No translation of the `docs/vad-benchmark-plan.md` or README.
- Backend verdict is Indonesian-only; if a future "EN" request comes in,
  we add an optional `_en` variant in the same dict and let the UI pick.
- Panel reorder is layout-only — no information is dropped or hidden
  by default.
- Sysmon polling, SSE, history snapshot, all unchanged.
