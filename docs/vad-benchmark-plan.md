# VAD Benchmark — Plan

> **Beauty-design, lazy-where-it-doesn't-hurt, full-where-it-must.**
> Standalone VAD + STT benchmark for the **ai4db backend** on Indonesian audio.
> Runs the same Silero-VAD + whisper.cpp stack ai4db runs, against a real
> Indonesian podcast, and shows the results in a configurable single-page
> dashboard — the same shape as the sibling `ocr-benchmark` project.
>
> **Portability**: this repo does **not** depend on the `ai4db` package. It
> pins the same VAD + STT backend (`whisper-cli` + `ggml-silero`) directly, so
> it runs on any device with `uv sync` + the two CLI binaries.

---

## 1 · Why this exists

ai4db ships an STT pipeline that uses **Silero VAD inside whisper.cpp** to strip
silence before transcription (deafblind assistive platform — the user speaks,
the platform transcribes to braille). The team needs to know **what VAD
actually buys us**: does it improve transcription accuracy, how much silence it
removes, and at what speed cost — on real Indonesian speech.

This repo measures it and ships a dashboard that makes the answer legible to a
non-ML reviewer, **configurable from the frontend** (toggle VAD, sweep
thresholds, pick model/window — then hit Run and watch it live).

### How ai4db actually uses Silero VAD (the thing we replicate)

Traced from the ai4db source — VAD is **not** a standalone Python library there;
it is delegated to `whisper.cpp`:

| Where (in ai4db) | Detail |
|---|---|
| `stt/whisper_bridge.py` | `whisper-cli -m <model> -f <wav> -l <lang> -t 4 --no-prints --no-timestamps [--vad --vad-model <silero.bin>]` |
| `stt/audio_capture.py` | Only fixed-window buffering (`vad_window_duration`, default 3.0 s) — no real VAD in Python |
| `config.py` | `whisper_vad_enabled=True`, `whisper_vad_model_path="models/whisper.cpp/ggml-silero-v6.2.0.bin"`, `vad_window_duration=3.0` |
| Audio format | 16 kHz, mono, float32 → int16 WAV |
| STT model | `ggml-tiny.id.bin` for Indonesian |
| No-speech handling | whisper.cpp prints `failed to process audio` → treated as empty transcript, not an error |

So the benchmark's engine is a thin wrapper around `whisper-cli` with exactly
these flags, plus the extra `--vad-*` tuning knobs whisper.cpp exposes.

### Dataset that fits the target

| Property | Value |
|---|---|
| Language | **Indonesian** (target ✔) |
| Audio | `data/podcast.mp3` (~8.1 MB, single speaker interview/podcast) |
| Ground truth | `data/text_podcast.txt` — tactiq/YouTube transcript export |
| GT shape | `HH:MM:SS.mmm <text>` per line (226 lines); `#` header lines + a `No text` placeholder line to drop |

The transcript is a **YouTube auto-transcript**, not gold — so WER is *relative*
(compare configs against each other), not absolute. The dashboard footer says so.

---

## 2 · Scope

| In | Out |
|---|---|
| Wrap the same `whisper-cli --vad` stack ai4db runs | Re-training any model |
| VAD ON vs OFF as the headline comparison | Multi-engine VAD shootout (Silero is the one under test) |
| Segment audio → transcribe each config → score vs reference | Manual transcription / gold labeling |
| Metrics: WER, CER, RTF (speed), silence-removed, segment count | Online/persistent storage, auth, multi-user |
| **Frontend-configurable** run (VAD toggle, thresholds, model, window) | Multi-page React app, build pipeline |
| Live progress (SSE), run history, system-resource monitor | — |
| Beautiful single-page dashboard (mirrors ocr-benchmark) | — |

### What the benchmark measures

1. **Recognition** — normalized WER + CER of the whisper transcript vs the
   cleaned reference, VAD on vs off.
2. **VAD behavior** — total speech duration kept, silence removed (%), number of
   speech segments detected.
3. **Speed** — wall-clock runtime and **RTF** (runtime ÷ audio length; < 1.0 =
   faster than real-time).
4. **(Optional) segmentation quality** — compare VAD segment boundaries against
   the reference timestamps (speech/silence agreement).

---

## 3 · Architecture (mirrors `ocr-benchmark`)

Same stack the sibling repo uses: **FastAPI backend + vanilla-JS single-page
dashboard, no build step**, `.env`-driven config via `pydantic-settings`, per-run
config overrides sent from the UI, live progress over Server-Sent Events, run
history, and a system-resource monitor.

```
vad-benchmark/
├── pyproject.toml            # uv; deps: fastapi, uvicorn, jiwer, pydantic-settings,
│                             #          numpy, scipy, psutil, pydub/ffmpeg-python
├── README.md
├── Makefile                  # make install / run / serve / test / clean
├── .env.example
├── src/
│   └── vad_bench/
│       ├── __init__.py
│       ├── paths.py          # PACKAGE_ROOT, DATA_ROOT, REPORTS_ROOT, HISTORY_ROOT, UI_ROOT, MODELS_ROOT
│       ├── config.py         # pydantic-settings Settings + get_settings() (@lru_cache)
│       ├── audio.py          # mp3 -> 16k mono wav (ffmpeg), duration probe
│       ├── reference.py      # text_podcast.txt -> cleaned reference (+ timestamped segments)
│       ├── engine.py         # whisper-cli wrapper (mirrors ai4db whisper_bridge); VAD flags + tuning
│       ├── metrics.py        # WER/CER via jiwer (NFKC/lower/collapse), RTF, silence-removed
│       ├── runner.py         # orchestrator: runs configs, writes reports/ + history/, SSE status sidecar
│       ├── sysmon.py         # CPU/RAM/GPU/temp sampler (copy from ocr-benchmark, unchanged)
│       └── api.py            # FastAPI app (this is what `vad-bench-serve` runs)
├── scripts/
│   ├── __init__.py
│   ├── prepare_audio.py      # mp3 -> wav CLI
│   └── run_benchmark.py      # CLI entrypoint (headless / CI)
├── ui/
│   ├── index.html            # dashboard (warm stone theme, DM Sans + JetBrains Mono)
│   ├── style.css             # copy ocr-benchmark palette; trim OCR-only rules
│   └── app.js                # vanilla JS, no build
├── models/                   # whisper + silero .bin  (gitignored)
├── data/                     # podcast.mp3, text_podcast.txt, podcast_16k.wav (wav gitignored)
├── reports/                  # generated (gitignored): summary.json/.csv, per_config/, history/, .run_status.json
└── docs/
    └── vad-benchmark-plan.md # this file
```

### Config registry (the frontend-configurable surface)

`config.py` — every knob defaults to the ai4db value so a fresh clone reproduces
production behavior. Each is overridable per-run from the UI (`POST /api/run`
query params, exactly like ocr-benchmark's `api_run`).

| Setting | Default | UI control | Notes |
|---|---|---|---|
| `vad_enabled` | `true` | toggle | the headline switch — off = baseline |
| `whisper_model` | `ggml-tiny.id.bin` | dropdown | tiny/base/small if downloaded |
| `language` | `id` | dropdown | `id` / `auto` |
| `vad_model_path` | `ggml-silero-v6.2.0.bin` | (read-only badge) | Silero model file |
| `vad_threshold` | `0.5` | slider 0.1–0.9 | whisper.cpp `--vad-threshold` |
| `vad_min_speech_ms` | `250` | slider | `--vad-min-speech-duration-ms` |
| `vad_min_silence_ms` | `100` | slider | `--vad-min-silence-duration-ms` |
| `vad_speech_pad_ms` | `30` | slider | `--vad-speech-pad-ms` |
| `vad_max_speech_s` | `∞` | number | `--vad-max-speech-duration-s` |
| `threads` | `4` | number | `-t` |
| `serve_host` / `serve_port` | `127.0.0.1` / `8770` | `.env` | pick a port distinct from ocr-benchmark's 8765 |

> whisper.cpp VAD flag names should be confirmed against the installed
> `whisper-cli --help` during Step 4 (they've been stable but verify the exact
> spelling/units before wiring sliders to them).

---

## 4 · API surface (same contract as ocr-benchmark)

```
POST /api/run                 run benchmark (background; poll /api/progress). Query params = every knob in §3.
GET  /api/progress            live run status (running, total, completed, current)
GET  /api/progress/stream     Server-Sent Events: push status on change
GET  /api/summary             aggregated metrics (configs compared)
GET  /api/results/<config>    per-config detail: transcript, segments, per-segment timing
GET  /api/config              current runtime config + which knobs are overridable
GET  /api/models              whisper/silero models present in models/
GET  /api/system              live CPU/RAM/GPU/temp snapshot (always-on widget)
GET  /api/history             past runs (newest first)
GET  /api/history/<id>        one past run
GET  /api/audio               serve podcast_16k.wav (for the in-page player)
GET  /                        dashboard (ui/index.html)
```

Reuse the ocr-benchmark patterns verbatim: background task + `.run_status.json`
sidecar with atomic `os.replace` (+ Windows retry), `_is_stale` lock detection,
`_RUN_GEN` supersede counter so a new Run cancels the old one, SSE that diffs the
status payload every 1 s, `_NoCacheStaticFiles` so UI edits land without a hard
refresh.

---

## 5 · Steps

### Step 1 — Scaffold from ocr-benchmark
Copy the skeleton (`paths.py`, `config.py`, `sysmon.py`, `api.py` structure,
`runner.py` status/history/SSE plumbing, `ui/style.css`, Makefile, pyproject,
`.env.example`) and strip OCR-specific pieces (dataset/labelme/matcher/corrector,
TTS). Keep the resource monitor and history verbatim.

### Step 2 — Prepare audio (`audio.py` + `scripts/prepare_audio.py`)
```bash
ffmpeg -y -i data/podcast.mp3 -ar 16000 -ac 1 -c:a pcm_s16le data/podcast_16k.wav
```
Probe and record duration, sample rate, channels. Cache: skip if wav is newer
than mp3.

### Step 3 — Build the reference (`reference.py`)
- Drop `#` header lines and any line whose text is exactly `No text`.
- Split each remaining line into `(timestamp, text)`; keep both a
  **plain joined text** (for WER/CER) and the **timestamped segment list** (for
  the optional boundary analysis).
- Normalize identically to the hypothesis (NFKC, lowercase, collapse whitespace,
  strip) — reuse `metrics.normalize`.

### Step 4 — Engine (`engine.py`)
Thin wrapper around `whisper-cli`, mirroring ai4db's `whisper_bridge.py`:
- Build the base command (`-m -f -l -t --no-prints --no-timestamps`).
- Append `--vad --vad-model <silero>` + the `--vad-*` tuning flags **only when
  `vad_enabled`**.
- Run with a timeout; treat the `failed to process audio` marker as empty output.
- Parse transcript from stdout; parse **segment count / speech duration** from
  whisper.cpp's verbose/progress output when VAD is on (fall back to "n/a" if the
  build doesn't print it).
- Return `EngineResult(text, runtime_s, n_segments, speech_seconds, cmd)`.

### Step 5 — Runner (`runner.py`)
For each requested config (default: `baseline_novad` + `silero_vad`):
1. Ensure `podcast_16k.wav` exists (Step 2).
2. Run the engine, time it (`time.perf_counter`).
3. Score against the reference (Step 6).
4. Write `reports/per_config/<config>.json` (transcript, diff-friendly aligned
   words, segments, metrics) + append to `reports/summary.json`/`.csv`.
5. Stream progress via the `.run_status.json` sidecar; snapshot to `history/`
   with the full config + rolled-up resource usage — same as ocr-benchmark.

### Step 6 — Metrics (`metrics.py`)
Reuse ocr-benchmark's `normalize`/`cer`/`wer` (jiwer). Add:
- `rtf = runtime_s / audio_duration_s`
- `silence_removed = 1 - speech_seconds / audio_duration_s` (VAD arm)
- optional: word-level alignment for the UI diff view (jiwer
  `process_words` gives aligned ops for highlighting).

### Step 7 — Dashboard (`ui/`)
Single page, warm-stone theme copied from ocr-benchmark. Sections:
- **Topbar**: title `VAD Benchmark · ai4db · Indonesian audio`, VAD/model badge,
  last-run time.
- **System resources**: reuse the sysmon widget as-is.
- **Run panel** (the configurable surface): VAD on/off toggle, model dropdown,
  language, and the VAD threshold/duration **sliders**; "Run benchmark" button.
  Disabled/greyed controls when a model file is missing (mirror the
  `*_available` greying pattern).
- **Audio player**: `<audio>` on `/api/audio` so the reviewer can listen.
- **Results**: config comparison table (WER, CER, RTF, silence-removed, segments,
  runtime) with the VAD arm highlighted; a **transcript diff** view
  (reference vs hypothesis, insert/delete/substitute colored) per config.
- **History**: past runs table, newest first (reuse the component).
- **Footer**: the honesty caveat (YouTube GT → relative WER; tiny model → high
  absolute WER; the delta is the signal).

### Step 8 — CLI + Make + README
- `scripts/run_benchmark.py` — `--vad/--no-vad`, `--model`, `--threshold`, etc.,
  same knobs the UI sends; usable headless / in CI.
- `Makefile`: `install`, `run`, `serve`, `test`, `clean` (mirror ocr-benchmark).
- README with quick-start, model download links, metric definitions, caveats,
  and an "honest finding" section like ocr-benchmark's corrector table.

### Step 9 — (Optional) segmentation-quality arm
Add a Python `silero-vad` (torch) arm that runs `get_speech_timestamps` directly
and compares boundaries to the reference timestamps (frame-level speech/silence
agreement, precision/recall on speech regions). Clearly label it as *different
from the ai4db path* (which uses whisper.cpp's built-in VAD), behind an opt-in
extra so the default install stays light.

---

## 6 · Metrics summary

| Metric | Meaning | Source |
|---|---|---|
| **WER** | word error rate vs reference (lower better) | jiwer |
| **CER** | char error rate (robust to ID word segmentation) | jiwer |
| **RTF** | runtime ÷ audio length (< 1.0 = real-time) | wall clock |
| **Silence removed** | 1 − speech/total (VAD aggressiveness) | whisper.cpp / silero |
| **Segments** | # speech segments detected | VAD output |
| **Runtime** | wall-clock seconds | perf_counter |
| **Resources** | avg/peak CPU/RAM/GPU/temp during run | sysmon |

---

## 7 · Prerequisites

- `ffmpeg` on PATH (audio decode/resample).
- `whisper-cli` (whisper.cpp) — `brew install whisper-cpp` / `apt install whisper.cpp`.
- Whisper model `ggml-tiny.id.bin` (+ optional `base`/`small`) in `models/`.
- Silero VAD model:
  `curl -L -o models/ggml-silero-v6.2.0.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-silero-v6.2.0.bin`
- Python: `jiwer`, `numpy`, `scipy`, `fastapi`, `uvicorn`, `pydantic-settings`,
  `psutil`. Optional `silero-vad` + `torch` only for the §9 arm.

Missing binaries/models degrade gracefully: the dashboard still serves, the Run
panel greys the affected controls, and `/api/run` returns a clear error instead
of a stack trace (same pattern as ocr-benchmark's 503 for the missing voice).

---

## 8 · Quick start (target UX, once built)

```bash
uv sync
# download models into models/  (see §7)
uv run python scripts/run_benchmark.py          # baseline_novad + silero_vad
uv run vad-bench-serve                           # → http://127.0.0.1:8770
```
Or drive it entirely from the dashboard: open the page, set the VAD toggle +
sliders, click **Run benchmark**, watch progress live, read the comparison.

---

## 9 · Caveats (surfaced in the UI footer)

- **Ground truth is a YouTube auto-transcript**, not gold — WER is *relative*
  between configs, not absolute accuracy.
- **Single audio file** — numbers are directional. Adding more clips later just
  means dropping them in `data/` and extending the reference loader.
- **`tiny.id` is small** — absolute WER is high; the **VAD on vs off delta** is
  the real signal.
- **whisper.cpp's VAD ≠ standalone Silero** — the §9 Python arm measures the
  library directly; the main arm measures what ai4db actually ships.
- Keep generated `*.wav` and `models/*.bin` out of git (large binaries).

---

## 10 · Deliverables

1. Runnable repo mirroring ocr-benchmark: FastAPI backend + configurable
   single-page dashboard + CLI + Makefile.
2. `reports/summary.json` + `.csv` + `history/` snapshots.
3. Transcript diff view and config-comparison table in the UI.
4. README with metric definitions, model download, and an honest-findings
   section (VAD on vs off verdict + recommended `WHISPER_VAD_*` settings for
   ai4db).
