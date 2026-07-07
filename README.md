# VAD Benchmark

Standalone VAD + STT benchmark for the **ai4db backend** on Indonesian audio.
Runs the same Silero-VAD + whisper.cpp stack ai4db runs, against a real
Indonesian podcast, and shows the results in a configurable single-page
dashboard.

Sister project: [`ocr-benchmark`](../ocr-benchmark/README.md) — same
architecture, same dashboard patterns, same self-test philosophy.

See [`docs/vad-benchmark-plan.md`](docs/vad-benchmark-plan.md) for the full
design rationale.

---

## What it measures

| Metric | Meaning |
|---|---|
| **WER** | Word error rate vs reference (lower better) |
| **CER** | Character error rate (robust to Indonesian word segmentation) |
| **RTF** | runtime ÷ audio length (< 1.0 = real-time) |
| **Silence removed** | 1 − speech/total (VAD aggressiveness) |
| **Segments** | # speech segments detected |
| **Resources** | avg/peak CPU/RAM/GPU/temperature during run |

## Quick start

```bash
# 1. Install deps (uv)
uv sync

# 2. Get the models (you probably want the Jetson for whisper-cli)
#    Either build whisper.cpp locally, or point WHISPER_CLI_CMD at it via SSH.
#    Example .env:
#      WHISPER_CLI_CMD=ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'
#
#    Drop ggml-tiny.id.bin and ggml-silero-v6.2.0.bin into models/
#    (or copy from ai4db/models/whisper.cpp/ on the Jetson)

# 3. Run the canonical 2-config comparison (~minutes for an 8 MB podcast)
uv run python -m scripts.run_benchmark

# 4. Open the dashboard
uv run vad-bench-serve
# → http://127.0.0.1:8770
```

The dashboard's **Run benchmark** panel mirrors the CLI: toggle VAD on/off,
sweep threshold/min-speech/min-silence sliders, pick the whisper model and
language, then click **Run benchmark** to watch live SSE progress.

## Configurable surface (the "configurable from frontend" requirement)

Every knob in `config.Settings` is overridable per-run from the dashboard
and the CLI:

| Setting | Default | Notes |
|---|---|---|
| `vad_enabled` | `true` | the headline switch — off = baseline |
| `whisper_model` | `ggml-tiny.id.bin` | any `.bin` in `models/` |
| `language` | `id` | `id` / `auto` / `en` |
| `vad_threshold` | `0.5` | whisper.cpp `--vad-threshold` |
| `vad_min_speech_ms` | `250` | `--vad-min-speech-duration-ms` |
| `vad_min_silence_ms` | `100` | `--vad-min-silence-duration-ms` |
| `vad_speech_pad_ms` | `30` | `--vad-speech-pad-ms` |
| `vad_max_speech_s` | `0` (= ∞) | `--vad-max-speech-duration-s` |
| `threads` | `4` | `-t` |
| `whisper_cli_cmd` | `whisper-cli` | bare binary, absolute path, **or shell command** |

**`WHISPER_CLI_CMD` is the magic knob**: it accepts any shell command, so a
Windows dev host with no local build can run on the Jetson via SSH —

```env
WHISPER_CLI_CMD=ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'
```

The runner `shlex.split`s the value (Windows-aware) and appends the model /
audio / VAD flags, so what ai4db runs and what the benchmark runs are byte-for-byte
the same CLI invocation.

## CLI overrides

```bash
# Canonical 2-config comparison
uv run python -m scripts.run_benchmark

# Single explicit config
uv run python -m scripts.run_benchmark \
    --config name=silero_t05,vad_enabled=true,vad_threshold=0.5

# Threshold sweep
uv run python -m scripts.run_benchmark \
    --config name=silero_03,vad_enabled=true,vad_threshold=0.3 \
    --config name=silero_05,vad_enabled=true,vad_threshold=0.5 \
    --config name=silero_07,vad_enabled=true,vad_threshold=0.7

# JSON output for piping
uv run python -m scripts.run_benchmark --json
```

## Outputs (gitignored)

```
reports/
├── summary.json              ← aggregated metrics across configs
├── summary.csv               ← one row per config
├── reference/
│   ├── reference.txt         ← cleaned YouTube transcript
│   └── segments.json         ← per-line timestamps
├── per_config/
│   ├── baseline_novad.json   ← transcript + word-level diff vs reference
│   └── silero_vad.json
├── history/                  ← past runs (newest first, capped at 50)
└── .run_status.json          ← live progress sidecar (read by /api/progress)
```

## Why standalone

The whole point is **moving VAD/STT benchmarking to a different device with
zero ai4db footprint**. We pin the same backend (whisper-cli + Silero VAD)
directly:

| | ai4db | vad-benchmark |
|---|---|---|
| Whisper binding | `whisper-cli` subprocess | `whisper-cli` subprocess |
| VAD integration | whisper.cpp `--vad --vad-model` | whisper.cpp `--vad --vad-model` |
| Audio format | 16 kHz mono int16 WAV | 16 kHz mono int16 WAV |
| Model | `ggml-tiny.id.bin` | `ggml-tiny.id.bin` (default) |
| Scoring | (not done in ai4db) | WER/CER via `jiwer` |

If ai4db's VAD knobs change (e.g. `vad_window_duration` matters when ai4db
moves to windowed STT), edit `src/vad_bench/config.py` to mirror and rerun.

## Dataset

| File | Role |
|---|---|
| `data/podcast.mp3` | Source audio (~8.1 MB, Indonesian speech) |
| `data/text_podcast.txt` | Ground-truth transcript (tactiq / YouTube auto-transcript) |

The transcript format is `HH:MM:SS.mmm <text>` per line, with `#` comment
headers and a `No text` placeholder to drop. See `reference.py` for the
exact cleaning rules.

## Layout

```
vad-benchmark/
├── pyproject.toml                # uv deps
├── README.md
├── Makefile
├── .env.example
├── src/vad_bench/
│   ├── __init__.py
│   ├── paths.py                  # shared paths (DATA_ROOT, MODELS_ROOT, REPORTS_ROOT, UI_ROOT)
│   ├── config.py                 # pydantic-settings: every knob overridable per-run
│   ├── audio.py                  # mp3 → 16k mono WAV via ffmpeg
│   ├── reference.py              # cleans the YouTube transcript
│   ├── engine.py                 # whisper-cli wrapper (mirrors ai4db's whisper_bridge)
│   ├── metrics.py                # WER/CER (jiwer) + RTF + silence-removed
│   ├── runner.py                 # orchestrator: SSE progress + history snapshots
│   ├── sysmon.py                 # CPU/RAM/GPU/temperature sampler
│   └── api.py                    # FastAPI app (this is what `vad-bench-serve` runs)
├── scripts/
│   └── run_benchmark.py          # CLI entrypoint
├── ui/
│   ├── index.html                # dashboard (warm stone theme)
│   ├── style.css                 # DM Sans + JetBrains Mono
│   └── app.js                    # vanilla JS, no build
├── data/                         # podcast.mp3 + text_podcast.txt
├── models/                       # whisper + silero .bin (gitignored)
└── reports/                      # generated (gitignored)
```

## Prerequisites

- `ffmpeg` on PATH (or set `FFMPEG_BIN=…`). `winget install Gyan.FFmpeg`
  works on Windows; `brew install ffmpeg` / `apt install ffmpeg` on macOS / Linux.
- `whisper-cli` (whisper.cpp). `brew install whisper-cpp` / `apt install whisper.cpp`,
  build from source, or run via SSH.
- Whisper model `ggml-tiny.id.bin` (and optional `base` / `small`) — copy from
  `ai4db/models/whisper.cpp/` on the Jetson, or download from
  `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.id.bin`.
- Silero VAD model `ggml-silero-v6.2.0.bin` — download from
  `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-silero-v6.2.0.bin`.

## Caveats

- **Ground truth is a YouTube auto-transcript**, not gold — WER is *relative*
  between configs, not absolute accuracy. The dashboard footer says so.
- **`tiny.id` is a small model** — absolute WER will be high; the **VAD
  on/off delta** is the signal, not the raw number.
- **`whisper.cpp`'s VAD ≠ standalone Silero** — this benchmark measures what
  ai4db ships, which is whisper.cpp's built-in VAD via `--vad --vad-model`.
- **Single audio file** for now — numbers are directional. Adding more clips
  later just means dropping them in `data/` and extending the reference loader.

## Why this repo is not in the ai4db package

Same reason as `ocr-benchmark`: ai4db is a production FastAPI app with many
dependencies (fastapi, sounddevice, piper-tts, scipy, liblouis, rapidocr, …).
Benchmarking only needs a thin wrapper around `whisper-cli` and `jiwer`.
Splitting it out means `uv sync` is fast, models download once, and the
benchmark can run on a different device with no ai4db checkout.

## Version drift — when ai4db updates its STT backend

1. Check the new flags ai4db uses in `src/ai4db/stt/whisper_bridge.py`.
2. If new knobs appear (e.g. `vad_max_speech_s`), add them to
   `src/vad_bench/config.py` and the UI sliders.
3. If ai4db moves away from `whisper-cli` entirely (e.g. to `faster-whisper`),
   replace `engine.py` — the runner, metrics, and dashboard stay unchanged.
4. Re-run the canonical comparison → new baseline numbers in `reports/`.
5. Commit the new config + refreshed `summary.csv`.