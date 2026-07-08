# Audio chunk review — design spec

## Problem

Right now the dashboard shows *that* VAD removed silence and *what* whisper
transcribed, but not the actual audio that was forwarded to whisper for each
detected speech region. To verify VAD quality by ear (not just by WER/CER
numbers), the user needs to hear each chunk whisper actually saw.

Separately: clicking "Run benchmark" doesn't play the audio under test, so
there's no way to follow along while a run is in progress.

## Scope

- Slice the source WAV into one file per VAD-detected speech region, for
  configs where VAD is enabled (VAD-off configs have no "passed VAD" concept
  — their whisper-internal segmentation isn't a VAD decision).
- Persist chunk **audio** for the most recent run only (disk is tight on the
  Jetson target). Persist chunk **text + timing** in run history indefinitely
  (same 50-run retention as today), since text is cheap.
- Surface chunks in the dashboard's existing VAD breakdown tab as a playable
  list.
- Auto-play the source podcast when "Run benchmark" is clicked.

Out of scope: waveform visualization, chunk editing/export, chunk audio for
VAD-off configs, chunk retention beyond the latest run.

## Backend

### `audio.py` — `slice_wav_segments`

```python
def slice_wav_segments(src: Path, segments: list[tuple[float, float, str]], out_dir: Path) -> None
```

Stdlib `wave` only — no ffmpeg subprocess per chunk (there can be dozens of
segments per run; spawning ffmpeg that many times is wasteful when the
source is already 16 kHz mono PCM16, exactly what whisper-cli consumed).

For each `(start_s, end_s, _)` in order: seek to `int(start_s * framerate)`,
`readframes(int((end_s - start_s) * framerate))`, write to
`out_dir / f"{index:04d}.wav"` using the same sample width/channels/framerate
as the source. `out_dir` is created if missing.

### `runner.py`

- At the start of `run()`, delete `REPORTS_ROOT / "chunks"` entirely (latest-run-only retention) before processing any config.
- After `transcribe()` for a config where `s.vad_enabled and result.segments`, call `slice_wav_segments(wav, result.segments, REPORTS_ROOT / "chunks" / _slug(name))`.
- `_score()` / `RunMetrics` gains a `chunks_available: bool` field — `True` when the config is VAD-enabled and has non-empty segments. Serialized in `to_dict()`. This lets the UI decide whether to render the chunk list without guessing from `vad_enabled` alone (parsing could still fail).
- `_record_from_metrics()` (used for history) gains a `segments` field (list of `{start, end, text}` dicts — text and timing only, no audio reference) so history retains per-chunk *text* even after the audio files are wiped by the next run.

### `api.py`

New endpoint:

```
GET /api/chunks/{config}/{index}
```

Serves `reports/chunks/<slug(config)>/<index:04d>.wav` as `audio/wav` via
`FileResponse`. 404 if the file doesn't exist (expected for VAD-off configs,
or history runs older than the current one — the UI must treat this as
"not available", not an error state).

### Tests

`tests/test_audio.py` gains a `slice_wav_segments` test: write a small
synthetic WAV, slice two known-time segments, assert output file count,
frame counts, and that sample rate/channels/width match the source.

## Frontend

### VAD breakdown tab — chunk list

New sub-section below the existing per-region table, inside
`renderVadBreakdown()` (`ui/app.js`). Rendered only when the selected
config's detail response has `chunks_available: true`. One row per segment,
in the same order as `segments` (row index == chunk file index):

| # | Waktu | Durasi | Teks whisper | Audio |
|---|-------|--------|--------------|-------|
| 1 | 00:00–00:08 | 8.5s | "Halo semua, hari ini..." | native `<audio controls>` |

Each row's audio player is a plain `<audio controls src="/api/chunks/<config>/<index>">` — no custom player JS, the browser supplies play/pause/seek.

When `chunks_available` is `false` (VAD-off config selected, or an older
history run whose chunk files were already cleared by a newer run), show a
quiet note instead of an error: *"Potongan audio hanya tersedia untuk config
VAD-on pada run terakhir."*

New i18n keys (`vad.chunks.*`) for the section title, table headers, and the
unavailable-note text, in both `en` and `id` locales, following the existing
`I18N` dict pattern in `ui/app.js`.

### Auto-play on Run click

In the `#btn-run` click handler (`ui/app.js`), call
`$("#audio-player").play().catch(() => {})` as the first line — before the
`fetch("/api/run…")` call. This fires inside the click's user-gesture
context so browsers won't block autoplay; `.catch()` swallows the rare case
where the audio element isn't ready yet.

## Data flow summary

```
whisper-cli (VAD on) → stdout w/ [start-->end] text lines
        │
        ▼
engine._parse_segments()  →  EngineResult.segments: [(start_s, end_s, text)]
        │
        ├──► audio.slice_wav_segments()  →  reports/chunks/<config>/0000.wav, 0001.wav, …
        │
        └──► RunMetrics.segments  →  per_config/<config>.json (+ history record, text only)
                                          │
                                          ▼
                                   GET /api/results/<config>  →  { segments, chunks_available }
                                   GET /api/chunks/<config>/<i>  →  audio/wav
                                          │
                                          ▼
                                   ui/app.js renderVadBreakdown() → chunk list w/ <audio> per row
```

## Error handling

- Missing chunk file (retention wiped it, or config is VAD-off): 404 from
  the API, `chunks_available: false` from the JSON — UI shows the quiet
  note, never a broken `<audio>` element with a 404 src.
- `slice_wav_segments` on an empty `segments` list: no-op, no files written
  (mirrors `_parse_segments`'s empty-list contract).
- Corrupt/zero-duration segment (`end <= start`): already filtered out by
  `_parse_segments` (`if end < start: continue`) before it reaches the
  slicer, so the slicer can assume non-negative durations. A `start == end`
  edge case still reaches the slicer as a zero-length chunk when it's the
  minimum-duration filter that admits it (parser only checks `end < start`,
  not `end <= start`) — `slice_wav_segments` writes a valid, empty-audio WAV
  rather than raising, since a 0-length recording is harmless downstream.
