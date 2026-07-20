# Audit: Making VAD Benchmark Results Trustworthy

## Scope

This audit reviews the current VAD-on versus VAD-off benchmark, its result
artifacts, dashboard claims, and testability. It does not assess model quality.
The goal is a result that answers one precise question:

> With the same model, input, and runtime environment, what is the end-to-end
> effect of enabling the production VAD path?

The findings below describe the pre-remediation baseline. The current contract
addresses them: modes are explicit, RTF uses end-to-end total time, manifests
are immutable, metric failures are visible, resources have one normalized
schema, and verdicts require a named comparable pair. Results remain
exploratory because the bundled one-clip reference is silver.

## Current Result Contract

- `off` transcribes the complete WAV without VAD flags; `builtin` is the
  canonical `whisper-cli --vad --vad-model` candidate; `presegmented` is a
  separately named standalone-segmenter experiment. No mode falls back.
- `total_s` covers configuration-specific work through available Whisper
  output. `segment_prep_s`, `staging_s`, and `transcription_s` are persisted
  components; RTF, ranking, and verdicts use `total_s / audio_duration_s`.
- Every run has a run ID and immutable `reports/history/<run-id>.manifest.json`
  with effective settings, commands, hashes, revision/dirty state, host/tool
  identity, timing scope, and `silver` reference quality.
- A verdict needs explicitly named control/candidate records whose effective
  settings differ only in `vad_mode`; sweeps have no recommendation.
- Reference-caption WER/CER are server-computed comparison metrics, not VAD
  boundary quality. Metric failures retain their error text and resources show
  unavailable values explicitly.
- `make test` is the canonical verification command; it syncs the `dev` extra
  before running the full test suite.

## Historical Findings (Resolved)

### P0: `VAD on` can mean two different pipelines

`runner.run()` first attempts standalone pre-segmentation and passes the
resulting WAV chunks to Whisper with `skip_vad=True`
([`runner.py:189-217`](../src/vad_bench/runner.py#L189-L217)). In that path,
`engine.transcribe()` removes all `--vad*` flags
([`engine.py:422-469`](../src/vad_bench/engine.py#L422-L469)). If
pre-segmentation is unavailable, the run falls back to Whisper's built-in VAD.

The UI and documentation describe this as one `VAD on` arm, even though the
input topology, executable, and VAD implementation may differ. That makes the
reported WER/CER/RTF difference impossible to attribute to one variable.

**Recommendation:** Make `whisper-cli --vad --vad-model` the only canonical
VAD-on arm because it mirrors ai4db. If pre-segmentation is still needed for
experiments, make it a separately named mode, for example `presegmented_vad`,
and persist that mode in every result row. Never silently switch modes.

### P0: RTF excludes VAD-on work

Pre-segmentation, chunk creation, and any required staging happen before the
timer inside `transcribe()` ([`engine.py:422-509`](../src/vad_bench/engine.py#L422-L509)).
`runner._score()` uses that partial `runtime_s` to calculate RTF
([`runner.py:325-350`](../src/vad_bench/runner.py#L325-L350)). VAD-off does not
have equivalent work.

The displayed RTF can therefore make VAD-on look faster than the actual
end-to-end request, especially when the VAD path creates many chunks or copies
them to a remote host.

**Recommendation:** Time each configuration from immediately before its first
VAD-specific operation through final transcription output. Persist
`vad_s`, `staging_s`, `transcription_s`, and `total_s`; calculate headline RTF
from `total_s / audio_duration_s`. The dashboard may show components, but must
rank configurations only by the total.

### P0: Per-region WER/CER is silently unavailable

`load_reference()` returns `Segment` objects, while `per_region_wer()` expects
iterable `(start, end, text)` tuples ([`reference.py:50-83`](../src/vad_bench/reference.py#L50-L83),
[`metrics.py:114`](../src/vad_bench/metrics.py#L114)). `runner._score()` catches
the resulting exception and converts it to an empty list
([`runner.py:336-340`](../src/vad_bench/runner.py#L336-L340)). The dashboard then
renders missing values as if no score were available.

**Recommendation:** Convert reference segments explicitly before scoring and
make score status explicit: `available`, `not_applicable`, or `error`. A metric
calculation error must appear in the report and run status, not become empty
data. Do not show per-region WER/CER as a benchmark result until its test passes.

### P1: Runs lack a reproducible identity

`RunMetrics.to_dict()` stores scores and transcript data but not the effective
settings, command, binary/model hashes, input/reference hashes, git revision,
History saves only a subset of settings ([`runner.py:364-390`](../src/vad_bench/runner.py#L364-L390)).

This means a later result cannot establish whether an improvement came from VAD,
hardware.

**Recommendation:** Write one immutable `manifest.json` per run and embed its
ID in `summary.json`, CSV rows, and each per-config result. At minimum record:

| Field | Purpose |
|---|---|
| Run ID and UTC timestamp | Locate an exact execution |
| Git revision and dirty state | Identify source code |
| Full effective configuration | Prove only intended variables changed |
| VAD pipeline mode | Distinguish built-in and pre-segmented execution |
| Resolved command and `whisper-cli --version` | Identify executable behavior |
| SHA-256 of model, VAD model, audio, and reference | Pin inputs |
| OS, CPU, RAM, GPU, driver, thread count | Explain performance deltas |
| Timing scope and component timings | Make RTF interpretable |
| Dataset/clip ID and reference quality | Bound accuracy claims |

### P1: The automatic verdict overstates the evidence

When several configurations exist, `build_verdict()` independently selects the
lowest-WER VAD-on and VAD-off records before recommending a setting
([`verdict.py:63-77`](../src/vad_bench/verdict.py#L63-L77),
[`verdict.py:129-145`](../src/vad_bench/verdict.py#L129-L145)). This compares
best-of-sweep values rather than a paired control. Its slowdown branch also
uses the inverse speed ratio ([`verdict.py:105-118`](../src/vad_bench/verdict.py#L105-L118)).

**Recommendation:** Generate a deploy/no-deploy verdict only for an explicitly
paired baseline and candidate where every non-VAD setting is identical. Treat a
threshold sweep as exploration: show all rows and name the selected candidate,
`rtf_on / rtf_off` as the slowdown factor.

### P1: One auto-transcript clip is directional, not an accuracy benchmark

The dataset is one Indonesian podcast with a YouTube auto-transcript
([`README.md:180-197`](../README.md#L180-L197)). This is useful as a smoke test,
reference errors encountered in production.

**Recommendation:** Keep this clip as `smoke-podcast-01`, then add a small,
versioned evaluation set before using the result for a decision. A practical
first target is 10-20 manually checked clips stratified by speech density,
noise, speakers, and short/long pauses. Report macro-average and duration-
weighted WER/CER with a per-clip table. Label auto-transcribed references as
`silver`; reserve `gold` for manually verified transcripts.

### P2: Resource output does not match its labels

The resource monitor stores RAM as percentages and does not persist temperature
summary ([`sysmon.py:167-175`](../src/vad_bench/sysmon.py#L167-L175)), while the
UI requests `ram_peak_mb` ([`ui/app.js:841-845`](../ui/app.js#L841-L845)) and
the README promises CPU/RAM/GPU/temperature metrics.

**Recommendation:** Use a single schema and labels. The minimal useful set is
CPU average/peak percent, process RSS peak MiB, GPU memory peak MiB, and GPU
temperature peak Celsius when available. Show `unavailable` when no sensor is
present, not a blank value.

### P2: The verification command could not run in the prior environment

The old command omitted the development extra and the suite had an import-path
problem. The suite now includes runner timing, manifest, metric, resource,
verdict, API payload, and UI-contract coverage.

**Resolution:** `make test` syncs the `dev` extra and runs the complete suite.

## Recommended Result Format

Use this as the dashboard's primary comparison table. One row is one
configuration over one dataset version and one repeat.

| Run | Config | Mode | Dataset | WER | CER | Total RTF | VAD | Stage | Decode | Status |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `2026...` | `baseline` | `off` | exploratory silver clip | 0.000 | 0.000 | 0.000 | - | - | 0.0 s | verified |
| `2026...` | `built_in_vad` | `builtin` | exploratory silver clip | 0.000 | 0.000 | 0.000 | 0.0 s | 0.0 s | 0.0 s | verified |

Place these rules directly below the table:

- `Total RTF` includes all configuration-specific work.
- A verdict only compares a named control/candidate pair.
- `verified` requires an immutable manifest, passing metric checks, and no
  suppressed metric errors.
- WER/CER are relative when the reference is silver.
- A multi-clip summary must show clip count, aggregation method, and spread
  such as min/median/max or a confidence interval.

For a threshold sweep, show a plot or table of threshold versus WER, silence
removed, segment count, and total RTF. Select a candidate with a pre-declared
rule, for example: lowest total RTF among candidates whose WER is no more than
1 percentage point worse than the paired baseline. Do not choose the best row
after seeing the score without recording that selection rule.

## Delivery Order

1. Separate and label VAD modes; make built-in Whisper VAD the canonical
   production comparison.
2. Measure end-to-end configuration time and fix the per-region metric type
   mismatch/error handling.
3. Add the immutable run manifest and display its ID, dataset, and mode.
4. Replace auto-verdicts with explicit paired comparisons; correct the slowdown
   calculation.
5. Repair the test command and add mocked tests for the P0 behavior.
6. Expand from the smoke clip to a versioned, labelled evaluation set.

## Acceptance Criteria

- A VAD-on row always records exactly one declared pipeline mode; no fallback
  changes that mode silently.
- Total RTF covers every configuration-specific operation and has component
  timings that sum to it within rounding.
- Per-region WER/CER either has a tested value or a visible, classified reason
  why it is unavailable.
- Every output file links to a manifest containing code, model, dataset,
  environment, and full configuration identity.
- A recommendation only appears for an explicitly paired run over the
  versioned evaluation set; a one-clip result is labelled exploratory.
- `make test` completes without collection errors after its declared dependency
  sync.
