# Pipeline Flow — from `podcast.mp3` to scored text

> Trace of everything that happens between "click Run" and a WER number on
> screen. Companion to [`vad-benchmark-plan.md`](vad-benchmark-plan.md) (the
> *why*/*scope*) — this doc is the *how*, file by file.

---

## 0 · One-line summary

```
podcast.mp3 --ffmpeg--> podcast_16k.wav --whisper-cli(+VAD)--> stdout segments
    --score vs reference--> RunMetrics --persist--> reports/ + history/ --serve--> UI
```

---

## 1 · Inputs prepared once per run

| Step | Function | File | Output |
|---|---|---|---|
| Decode audio | `ensure_wav()` | `audio.py` | `data/podcast_16k.wav` — 16 kHz mono PCM16, cached (skipped if newer than the mp3) |
| Measure duration | `wav_duration()` | `audio.py` | seconds, via the WAV header only (`wave.getnframes()/getframerate()`, no decode) |
| Load reference | `load_reference()` | `reference.py` | normalized silver-reference string + list of timestamped caption `Segment`s |
| Snapshot reference | `write_reference_artifacts()` | `reference.py` | `reports/reference/{reference.txt, segments.json}` |

`ensure_wav()` shells out to ffmpeg exactly once:

```
ffmpeg -y -i data/podcast.mp3 -ar 16000 -ac 1 -c:a pcm_s16le data/podcast_16k.wav
```

The reference parser (`reference.py`) reads `data/text_podcast.txt` — a
tactiq/YouTube export, one line per caption: `HH:MM:SS.mmm text`. Rules:
drop `#` comment lines, drop literal `No text` lines, strip the timestamp,
fill each segment's `end_s` with the *next* segment's `start_s`. The joined
text is normalized (NFKC + lowercase + collapsed whitespace) with the same
`normalize()` used for scoring, so reference and hypothesis are compared on
equal footing.

---

## 2 · Per-config loop (`runner.run()`)

For each `{name, overrides}` in the requested config list (default: `baseline_novad` vs `silero_vad`):

1. **Merge settings** — `parse_settings_overrides(overrides, base)` returns
   `base.model_copy(update=overrides)`. `base = Settings()` picks up
   `.env`/env-var defaults (`config.py`).
2. **Write status** — `.run_status.json` updated so `/api/progress` (polled)
   and `/api/progress/stream` (SSE) can show "current: {name}" live.
3. **Run the declared mode** — `off` transcribes the whole WAV without VAD;
   `builtin` calls Whisper with `--vad --vad-model` (Silero, in-process);
   `presegmented` first runs the standalone Silero segmenter binary and
   transcribes its chunks without Whisper VAD; `rms_energy` computes speech
   regions in pure Python (`rms_vad.compute_rms_segments`, no Silero model,
   no external binary) and transcribes those chunks the same way
   `presegmented` does. There is no mode fallback.
4. **Time and transcribe** — `total_s` starts before the mode's first operation
   and stops when Whisper output is available. `segment_prep_s`, `staging_s`,
   and `transcription_s` remain diagnostic components.
5. **Score** — `_score()` builds a `RunMetrics`, including `metric_status` and
   `metric_error` if optional reference-caption region scoring fails.
6. **Slice chunks** — if VAD was on and produced segments, `slice_wav_segments()`
   cuts one WAV per detected region.
7. **Persist per-config** — `reports/per_config/<slug>.json` = `rm.to_dict()`.

A global `_RUN_GEN` counter makes a fresh `POST /api/run` supersede an
in-flight one — the old loop notices `gen != _RUN_GEN` and bails via
`_Superseded` instead of clobbering the new run's output.

---

## 3 · `engine.transcribe()` — the whisper-cli call

This is the actual STT step, and it mirrors ai4db's `stt/whisper_bridge.py`
almost line-for-line.

### 3.1 Command built

```
whisper-cli -m <model.bin> -f <podcast_16k.wav> -l id -t 4 --print-progress \
  [--vad --vad-model <silero.bin>
   --vad-threshold <t>              (if != 0.5)
   --vad-min-speech-duration-ms <ms> (if != 250)
   --vad-min-silence-duration-ms <ms> (if != 100)
   --vad-speech-pad-ms <ms>          (if != 30)
   --vad-max-speech-duration-s <s>   (if > 0)]
```

Built by `_whisper_flags()` (`engine.py:180`). Paths are emitted POSIX-style
(`.as_posix()`) even on Windows, since whisper-cli and the SSH transport
both want forward slashes.

**Deliberate difference from ai4db production:** `--no-timestamps` is
*omitted*. ai4db uses it (it only wants the bare transcript for the
braille pipeline); this benchmark keeps timestamps on purpose so whisper-cli
prints one `[start --> end] text` line per detected speech region on
stdout — that's what feeds the VAD-breakdown timeline and the per-region
chunk player in the UI.

### 3.2 Local vs remote execution

`WHISPER_CLI_CMD` (env var, default `whisper-cli`) decides how the binary
runs:

- **Bare binary / absolute path, no spaces** → run directly as a list,
  `shell=False`. Validated with `shutil.which()` up front for a clean error.
- **Anything with spaces or shell operators** (e.g.
  `ssh jetson-nano-ssh 'whisper.cpp/build/bin/whisper-cli'`) → treated as a
  shell command string, `shell=True`, flags appended `shlex.quote`d.

For the SSH form, `_maybe_sync_remote()` runs first: it `scp`s the WAV,
whisper model, and VAD model to a stable remote scratch dir
(`/tmp/vad-bench-scratch`, hash-prefixed filenames so same-named files from
different local paths don't collide), then `_rewrite_remote_paths()` swaps
every local path token in the resolved command for its remote counterpart.
This is what lets the Windows dev host drive the Jetson's whisper-cli
transparently — no manual scp step.

### 3.3 Running + parsing the result

`subprocess.run(cmd, capture_output=True, timeout=600, text=True, shell=use_shell)`.

- **No-speech case**: if `returncode != 0`, VAD was on, and stderr contains
  `failed to process audio` → treated as an empty transcript, not an error
  (matches ai4db's `_NO_SPEECH_MARKER` handling — a fully silent input
  shouldn't crash the run).
- **Any other non-zero exit** → `RuntimeError` with the command + stderr tail.
- **Success** → two regexes pull structure out of the raw text streams:

  | Regex | Source | Extracts |
  |---|---|---|
  | `_VAD_REDUCTION_RE` | stderr | `whisper_vad: Reduced audio from N to M samples (P% reduction)` → `silence_removed` fraction, `speech_seconds` |
  | `_SEGMENT_RE` | stdout | `[HH:MM:SS.mmm --> HH:MM:SS.mmm] text` → list of `(start_s, end_s, text)` |

  The final `transcript` is the joined text of all parsed segments (falls
  back to raw stdout if no segment lines matched, e.g. VAD off with a
  whisper-cli build that doesn't print regions the same way).

`transcribe()` returns an `EngineResult` — transcript, runtime, VAD stats,
segments, and the raw cmd/stdout/stderr for debugging.

---

## 4 · Scoring (`runner._score()` → `metrics.py`)

| Metric | Function | Definition |
|---|---|---|
| WER | `wer(ref, hyp)` | `jiwer.wer` on NFKC-lowercased, whitespace-collapsed text |
| CER | `cer(ref, hyp)` | `jiwer.cer`, same normalization |
| RTF | `RunMetrics.__post_init__` | `total_s / audio_duration_s` — < 1.0 = faster than real-time |
| Word alignment | `word_alignment(ref, hyp)` | per-word `equal/substitute/insert/delete` tags from `jiwer.process_words`, for the UI's colored diff |
| Reference-caption region WER/CER | `per_region_wer()` | server-side greedy IoU match of each caption window against the closest hyp segment; it is not VAD-boundary quality |

All of this becomes one `RunMetrics` dataclass (`metrics.py:150`) per config,
serialized via `.to_dict()`.

---

## 5 · Chunk slicing (`audio.slice_wav_segments()`)

When a config ran with VAD on and whisper-cli reported ≥1 region,
`slice_wav_segments(wav, result.segments, CHUNKS_ROOT / slug(name))` cuts
one WAV per region using **stdlib `wave` only** — no per-chunk ffmpeg call,
because the source WAV is already the exact 16 kHz mono PCM16 whisper-cli
consumed, so raw frame-index slicing (`start_s * framerate` → `readframes`)
is correct and cheap.

Retention is intentionally asymmetric:

- **Audio chunks** (`reports/chunks/<slug>/NNNN.wav`) — latest run only;
  wiped at the top of every `run()` call (`shutil.rmtree(CHUNKS_ROOT)`).
- **Segment text + timing** — kept indefinitely in `reports/history/*.json`
  (50-run rolling index), because `_record_from_metrics()` always includes
  `segments: [{start, end, text}, ...]` regardless of whether the audio
  still exists.

---

## 6 · Persistence

| Path | Written by | Contents |
|---|---|---|
| `reports/summary.json` | `runner.run()` | aggregate, run ID, manifest path, silver reference quality, per-config metrics, verdict, normalized resources |
| `reports/summary.csv` | `_write_summary_csv()` | flat table, one row per config |
| `reports/per_config/<slug>.json` | `runner.run()` | full `RunMetrics.to_dict()` incl. transcript + alignment |
| `reports/chunks/<slug>/NNNN.wav` | `slice_wav_segments()` | per-region audio (latest run only) |
| `reports/history/<run_id>.json` | `_save_to_history()` | full snapshot for that run |
| `reports/history/<run_id>.manifest.json` | `manifest.write_manifest()` | immutable effective settings, commands, input/model hashes, revision, host/tools, timing scope, and reference quality |
| `reports/history/index.json` | `_save_to_history()` | full run index, paginated by the History API |
| `reports/.run_status.json` | `_write_status()` | live progress sidecar (atomic write w/ Windows AV-scanner retry) |

---

## 7 · Serving to the dashboard (`api.py`)

| Endpoint | Reads |
|---|---|
| `GET /api/summary`, `/api/results`, `/api/results/{config}` | `reports/summary.json`, `reports/per_config/*.json` |
| `GET /api/chunks/{config}/{index}` | `reports/chunks/<slug>/NNNN.wav` |
| `GET /api/reference/segments` | `reports/reference/segments.json` (fallback: `reference.load_reference()` live) |
| `GET /api/progress`, `/api/progress/stream` | `reports/.run_status.json` (SSE = 1s diff poll) |
| `GET /api/history`, `/api/history/{id}` | `reports/history/index.json`, `reports/history/<id>.json` |

`ui/app.js` renders declared mode, total/component timings, metric status/error,
run ID/manifest path, silver exploratory-reference label, and normalized
resources directly from these JSON payloads. Reference-caption WER/CER are
server-computed; the browser does not reconstruct proxy metrics.

---

## Self-check

Every function named above already has one of:
- a module `if __name__ == "__main__":` self-check (`metrics.py`, `engine.py`, `runner.py`), or
- a `tests/test_*.py` covering it (`test_metrics.py`, `test_audio.py`, `test_reference.py` if present).

Run `make test` for the canonical clean-environment check. It syncs the `dev`
extra and runs the complete suite without excluding tests.
