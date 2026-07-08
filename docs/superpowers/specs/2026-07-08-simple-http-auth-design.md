# VAD breakdown tab + timeline visualization

**Date:** 2026-07-08 (in-session iteration)
**Status:** approved (verbal, in chat)
**Scope:** new "VAD breakdown" tab inside the Results panel + parse
per-segment timestamps from `whisper-cli`. No new deps.

## Goal

Make VAD behavior legible at a glance. Right now `silence_removed` /
`speech_seconds` are aggregate scalars; reviewers can't see *which* parts
of the audio were kept vs cut. Add a second tab in the Results panel that
visualizes:

1. Two stacked timelines of the audio — VAD output (from `whisper-cli`
   timestamps) on top, reference transcript timestamps on bottom.
2. A per-region WER/CER table.

## Decisions

- **Source of timestamps:** drop `--no-timestamps` from `whisper-cli`
  and parse the bracketed timestamps it prints by default. No new deps.
- **Source of reference timeline:** reuse the second return value of
  `load_reference()` — `segments` already carries `(start, end, text)`
  tuples parsed from `HH:MM:SS.mmm <text>` lines.
- **Tab location:** inside the existing Results panel, alongside the
  current table. Tabs are a simple `<div class="results-tabs">` switch
  driven by JS — no library, no URL hash.
- **No ai4db touches.** No new pipeline deps. silero-vad Python lib
  remains future work.

## Changes

### `src/vad_bench/engine.py`

- Add `--output-json` (or just remove `--no-timestamps`) so whisper-cli
  emits `[{start, end, text}, ...]`. Pick the approach that works with
  the local whisper.cpp build; default to removing `--no-timestamps`
  (timestamps are printed in `[HH:MM:SS.mmm --> HH:MM:SS.mmm]` form
  which is parseable).
- New parser `_parse_segments(stdout)` → `list[(start_s, end_s, text)]`.
- Add `segments: list[tuple[float, float, str]]` to `EngineResult`.

### `src/vad_bench/metrics.py`

- New helper `per_region_wer(ref_segments, hyp_segments)` returning
  `list[dict]` keyed by reference-segment index, each with start/end/text
  + matched hyp text + WER + CER. Match by greedy timestamp overlap
  (IoU threshold 0.1).

### `src/vad_bench/runner.py`

- Pass `segments` through to `RunMetrics`.
- Store `segments` in `RunMetrics.to_dict()` so per-config JSON includes
  them.

### `src/vad_bench/api.py`

- `/api/results/<config>` already returns full per-config JSON — the
  segments will flow through automatically. No endpoint change.

### `ui/index.html`

- Add `<div class="results-tabs">` inside the Results panel head:
  buttons for `Comparison` and `VAD breakdown`.
- Add `<section class="vad-breakdown" hidden>` after the existing
  results summary / table; contains a timeline div, a metrics strip,
  and a per-region table.

### `ui/style.css`

- Tab styling (already have flow-stepper tokens to reuse — same accent,
  similar geometry).
- Timeline: full-width track, height ~32px, scale = container width /
  audio_duration_s. Each region = absolute-positioned `<div>` whose
  width = `(end - start) / audio_duration_s * 100%`.
- Per-region table: existing table styling already covers it.

### `ui/app.js`

- New `i18n` keys for tab labels, region-table columns, tooltip strings.
- `renderVadBreakdown(configName)` fetches `/api/results/<config>`,
  computes per-region WER/CER, builds the timeline DOM and the table.
- Tab switching in `selectConfig()` so picking a row in the comparison
  table updates the VAD breakdown tab too.

## Self-test

`tests/test_metrics.py` — add a single test for `per_region_wer`:
synthetic ref + hyp segments, assert returned list has one entry per
ref segment with correct WER (0 for an exact match, >0 for substitution).

## Out of scope

- No audio waveform drawing (would need ffmpeg-extracted peaks; future).
- No precision/recall of VAD boundaries against reference (would need
  per-region frame-level labels; future).
- No segmentation-quality Python arm (silero-vad + torch). Out of
  scope per user ("point 3 nanti, saat update ai4db").
- No changes to compare-table; new tab is additive.