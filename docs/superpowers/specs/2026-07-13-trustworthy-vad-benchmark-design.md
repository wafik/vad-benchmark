# Trustworthy VAD Benchmark Design

## Goal

Make each result answer a bounded question: with the same model, audio,
reference, and host, what is the end-to-end effect of a declared VAD pipeline?
The bundled single clip remains an exploratory smoke dataset and its reference
is labelled `silver`.

## Scope

This work changes the benchmark pipeline, artifacts, dashboard, and tests. It
does not add new audio or gold-labelled references.

## VAD Modes

`vad_mode` replaces the ambiguous VAD boolean across settings, API requests,
result artifacts, UI rows, and verdict inputs.

| Mode | Behavior | Status |
|---|---|---|
| `off` | Transcribe the complete WAV without VAD flags. | Control |
| `builtin` | Run `whisper-cli --vad --vad-model` on the complete WAV. | Canonical production candidate |
| `presegmented` | Use the standalone segmenter, transcribe its chunks without Whisper VAD flags. | Explicit experiment |

`builtin` is the default VAD-on comparison. A mode never falls back to another
mode. Missing executables, models, or segment output fail that configuration
with a visible error and leave no comparable score.

## Timing and Metrics

Each configuration starts `total_s` immediately before its first
configuration-specific operation and ends after Whisper output is available.
`rtf = total_s / audio_duration_s` is the only ranking and verdict timing
metric.

Diagnostic timings are persisted independently:

- `segment_prep_s`: standalone segmentation only; zero for `off` and `builtin`.
- `staging_s`: copies required for remote execution.
- `transcription_s`: Whisper invocation only.
- `total_s`: wall time for the configuration; it includes all preceding costs.

Per-region WER/CER accepts the `Segment` reference structure correctly. It is
labelled `reference-caption region`, because caption timestamps do not provide
gold speech-boundary annotations. Metric computation failures produce a
persisted `metric_status: "error"` and explanatory error text; they are not
converted to empty results.

## Run Manifest

Every run writes `reports/history/<run-id>.manifest.json`. The summary and
each per-config artifact store `run_id` and `manifest_path`.

The manifest contains:

- run ID, UTC timestamp, source revision, and dirty state;
- full effective config for each row, mode, and resolved command;
- SHA-256 values for audio, reference, Whisper model, and applicable VAD model;
- audio/reference identity and reference quality (`silver`);
- host OS, CPU, RAM, GPU, thread count, and known tool version data;
- timing scope plus total and component timings for every configuration.

The manifest is immutable after a run finishes. Current-summary files may be
overwritten, but history files are not used as mutable state.

## Verdict and UI

A recommendation is permitted only when the request identifies an explicit
control/candidate pair. Both must use the same model, audio, language, threads,
explicit experimental mode, which is named in the verdict. A sweep receives no
recommendation.

For a paired comparison, slower VAD is reported as `rtf_candidate / rtf_control`.

The dashboard displays mode, total RTF, timing components, reference quality,
run ID, and metric status. It labels the one-clip dataset as exploratory. The
resource card uses CPU average/peak percent, process RSS peak MiB, GPU-memory
peak MiB, and GPU-temperature peak Celsius when available; unavailable values
are rendered explicitly.

## Verification

`make test` is the documented test command. It must install the `dev` extra and
run without collection errors.

Tests cover:

- command generation for all three modes and no mode fallback;
- total timing boundaries and components;
- per-region scoring from `Segment` objects plus visible metric errors;
- manifest identity, hashes, and per-config linkage;
- verdict eligibility, pairing validation, and slowdown arithmetic;
- resource schema and dashboard payload compatibility.

## Acceptance Criteria

- Every scored row exposes exactly one `vad_mode` and `total_s`.
- A canonical VAD comparison uses only `builtin` versus `off`.
- RTF includes every configuration-specific operation.
- A metric is either computed or visibly classified as unavailable/error.
- Every result is traceable to a manifest with immutable input and environment
  identity.
- The UI never labels caption overlap as VAD boundary quality.
- `make test` succeeds in a clean environment after its declared dependency
  sync.
