# Jetson Telemetry and History Design

## Goal

Show trustworthy live Jetson Nano resource telemetry in the VAD benchmark UI
and retain compact per-run resource summaries for comparison in paginated
history.

## Collection

- On Jetson, collect a one-shot `tegrastats` sample for CPU core usage,
  RAM, swap, GR3D GPU usage, GPU memory, thermal zones, clocks, and power
  when those fields are present.
- Keep the existing psutil and `nvidia-smi` collector as the best-effort
  fallback for non-Jetson hosts.
- Missing values remain `null`; a missing sensor must never fail a benchmark.
- Live snapshots poll every three seconds. Active benchmark monitors sample
  every two seconds.

## API and Stored Results

- `GET /api/system` returns normalized live fields plus availability metadata,
  warning state, and timestamp.
- Each completed run stores only derived resource data: average and peak CPU,
  RAM, swap, GPU, temperatures, disk, power, and elapsed high-load or thermal
  warning time.
- Raw sample time-series is deliberately not persisted.

## UI

- The system panel presents CPU total and core detail, RAM, swap, GR3D GPU,
  GPU memory, CPU temperature, GPU temperature, disk, and optional power or
  clock information.
- Bars use normal, warning (75 percent), and critical (90 percent) states;
  temperature warnings begin at 80 C.
- Unavailable hardware fields render as unavailable rather than zero.
- Result and history detail views show the stored resource summary for each
  run so VAD modes can be compared alongside resource cost.

## History Pagination

- The history endpoint accepts page and page-size parameters and returns the
  requested records plus pagination metadata.
- The UI renders previous/next controls, current page, and total run count.
- History detail loading remains by immutable run id and is unaffected by
  paging.

## Verification

- Unit tests cover tegrastats parsing, fallback behavior, threshold states,
  resource aggregation, and paginated history metadata.
- API and UI contract tests cover normalized unavailable values, pagination,
  and the telemetry element ids used by the dashboard.
- Verify on Jetson with a live `/api/system` sample, a completed benchmark,
  and history navigation.
