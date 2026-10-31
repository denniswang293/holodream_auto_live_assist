# Tap pipeline simplification results

## Scope

The refactor is staged. Safety checks, Hold behavior, Particle Filter, key
ownership, deadline revisions, and the 30 px baseline remain unchanged.

## Implemented

- Added `motion_reliable` and `timing_reliable` summaries to Tap decision traces.
- Added `timing_quality` as a diagnostic score instead of silently treating
  every quality input as an unrelated decision.
- Added `LinearTimingEstimator` as a capture-timestamp based PF shadow. It does
  not drive real input until paired replay shows it is no worse than PF.
- Added `simplified_tap_planner` and `linear_timing` feature flags. The planner
  simplification is currently shadow/off; linear timing is shadow-only.
- Existing amendment generation, freeze window, ownership and scheduler safety
  remain authoritative.
- Gray Tap appearance continuity and detector rejection diagnostics remain in
  the active path. Static gray lines still require motion before confirmation.

## Baseline limits

The available runs contain track and key-down telemetry but no reliable
one-to-one game judgment labels. Detector recall, game hit rate, and MISS/Fast/
Late improvements therefore remain `UNKNOWN`/`UNVERIFIED`.

## Rollback

Set `simplified_tap_planner.enabled` to `false` and keep
`linear_timing.mode` as `shadow`; this restores the existing PF-driven Tap
decision path while retaining the diagnostic fields. No real keyboard safety
gate is controlled by either flag.

## Verification

```text
py -m pytest -q  # 88 passed
```
