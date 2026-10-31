# V7.7 Safety Regression

- Replay never invokes Scheduler or Actuator.
- Legacy Planner + Particle Filter remain the active input path.
- Simplified Planner and Linear ETA remain Shadow-only.
- No focus/stale/ROI/disarm/key-release/Hold/duplicate protections were relaxed.
- `key_down` and `FIRED` are lifecycle events, not game judgment truth.
- Geometry remains `pending_calibration`; no coordinates were changed.
