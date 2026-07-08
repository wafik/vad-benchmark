# VAD Benchmark — UI Flow + Metric Tooltips

**Date:** 2026-07-08
**Status:** approved (verbal, in chat)
**Scope:** UI-only — `ui/index.html`, `ui/style.css`, `ui/app.js`. No backend/API changes.

## Goal

Make the dashboard legible to a non-ML reviewer (ai4db team) without reading the
docs. Two pain points:

1. **What does the page do / in what order?** Add a 3-step flow marker.
2. **What do those numbers mean?** Add tooltips to the metric headers/tiles, and
   color-code the values that have a clear good/bad threshold.

## Decisions (from brainstorming)

- **Language:** English (consistent with the rest of the UI).
- **Stepper form:** 3-step horizontal indicator above the sysmon panel, mapped
  to the panels that already exist (run panel → SSE progress → results).
- **Tooltip form:** CSS-only (`data-tip` + `::after` on `:hover`/`:focus`).
- **Color coding scope:** RTF gets a real threshold (good/bad). WER/CER get
  relative-to-this-run coloring. Silence-removed / segments stay uncolored
  (two-way tradeoff, not "good=more").

## Changes

### 1. Stepper (`index.html` + `app.js` + `style.css`)

- New `<ol class="flow-stepper">` between the topbar `<main>` and the sysmon panel.
- Three steps: `① Configure`, `② Run`, `③ Compare results`. Each `<li>` is a
  button so reviewers can click to scroll the relevant panel into view (no
  navigation, just `scrollIntoView({ behavior: 'smooth', block: 'start' })`).
- Active step is driven by existing SSE state:
  - `running === true` → step 2 active
  - running false AND `summary.json` loaded → step 3 active
  - default → step 1 active
- `updateStepper(stage)` called from `onProgress()` and `tryLoadLastResults()`.

### 2. Metric tooltips (`index.html` + `style.css`)

- Each metric header (`<th>`) and each summary tile gets a small
  `<button class="tip" data-tip="…" aria-label="…">?</button>`.
- CSS `.tip { … }` + `.tip[data-tip]:hover::after, .tip[data-tip]:focus::after { content: attr(data-tip); }`
  shows the tooltip. The button has `tabindex="0"` natively, so keyboard
  focus also triggers the tooltip.
- Tooltip texts (English, ≤ 2 short sentences each):

  | Metric | Tooltip |
  |---|---|
  | WER | "Word Error Rate vs the reference transcript. Lower is better. The reference is a YouTube auto-transcript, not gold — compare configs against each other, not to an absolute target." |
  | CER | "Character Error Rate. Like WER, but on individual characters — more robust to Indonesian word-segmentation differences." |
  | RTF | "Real-Time Factor = runtime ÷ audio length. Below 1.0 means faster than real-time. Above 1.0 is slower than real-time and may need a smaller model or a faster device." |
  | Runtime | "Wall-clock seconds for the full whisper-cli invocation, including VAD pre-processing when enabled." |
  | Silence removed | "Share of audio that VAD dropped as silence. Higher means more aggressive trimming — but too aggressive can also drop real speech. Compare WER alongside this number, not in isolation." |
  | Segments | "Number of speech regions VAD found in the audio. Not 'good' or 'bad' on its own — depends on the speaker's style." |
  | Total runtime | "Sum of wall-clock seconds across all configs in this run (not the audio length)." |

### 3. Color-coded values (`app.js` + `style.css`)

- **RTF cell** — `value < 1.0` → `.metric-good`, else `.metric-bad`. Absolute
  threshold, makes sense without context.
- **WER / CER cells** — relative to the run: for each column, find min and max
  among configs, color the min `.metric-good` and the max `.metric-bad`. Ties
  all get the same color (don't artificially penalize an equally-good config).
- **Silence removed / Segments** — no color (the tooltip says why).
- **Runtime** — no color (already covered by RTF).
- Reuse existing tokens `--good`, `--good-bg`, `--bad`, `--bad-bg` from
  `style.css:16-21`. Add a small `.metric-cell` modifier that pads the value
  the same way the existing metric cells do (`.metric-wer/.metric-cer/.metric-rtf`
  are already styled for color — we add background and weight changes only).

  ```css
  .metric-cell.is-good { background: var(--good-bg); }
  .metric-cell.is-bad  { background: var(--bad-bg);  }
  ```
- Implementation: `renderResults()` recomputes good/bad classes per cell after
  building the table. RTF uses a small helper `isRtfRealTime(value)`.

## Out of scope (explicit YAGNI)

- No auto-generated verdict sentence. The existing `#best-line` text stays.
- No panel reorder. Sysmon, audio, run, results, history keep their current
  vertical order; the stepper sits above as a guide, not a replacement.
- No backend changes. Everything is driven by `/api/summary` and the SSE
  status payload that `app.js` already consumes.
- No new dependencies, no build step, no extra JS files.
- Tooltip text is hard-coded English — no i18n layer added.

## Self-check (one file, manual)

- `ui/app.js` will continue to boot via `init()` and render the stepper on
  page load. Self-test:
  ```bash
  uv run vad-bench-serve  # then open http://127.0.0.1:8770
  ```
  Expectation: stepper shows step 1 active initially, becomes step 2 during a
  run, becomes step 3 after a successful run; hover the `?` icons next to WER
  / RTF / silence-removed and see the tooltip text; the RTF cell turns green
  for sub-1.0 values and red for ≥ 1.0.
