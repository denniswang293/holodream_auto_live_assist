# V7.9.1 trace snapshot schema

The optional `diagnostics.trace_snapshot` block is **disabled by default**. If enabled, the bounded asynchronous identity writer emits `live_trace_snapshots.csv` with schema `v791.1`.

Each row is keyed by `run_id + source_frame + capture_timestamp + track_id`; it records candidate/track state, `confirmed_now`, match/coast timing, last real observation timestamp, PF availability/ETA/uncertainty, Planner lifecycle/reason and a diagnostic-only scheduler summary. `input_sent` is always false in this file. Rows are bounded by `max_rows` per frame and writer queue health reports drops.

The snapshot is write-only telemetry. It is not read by Tracker, Planner, Scheduler or Actuator, does not create observations, and cannot retroactively repair old runs that lack serialized state. `source_frame` and `capture_timestamp` are authoritative; no fixed-FPS time conversion is used.
