# Simple Core dependency inventory

| Component | Responsibility | Dependencies | Current owner/use |
|---|---|---|---|
| `src/detector.py` | Produces colored, geometry-mapped candidates | OpenCV, NumPy, `geometry.py`, `hold_visual.py` | Shared unchanged by V6 and Simple Core |
| `src/simple_tracker.py` | One-to-one short-gap motion association; robust linear or particle ETA; no re-identification handoff | `Candidate`, `assignment.assign`, `Predictor`, optional `ParticlePredictor` | New Tap-only tracker in `--tap-core simple` |
| `src/tap_planner.py` | Requires confirmed Tap, stable covered key, forward ETA and bounded uncertainty; assigns one key per action | `SimpleTrack`, `assignment.assign`, `common.KEYS` | New Tap planner |
| `src/tap_intent.py` | Owns immutable accepted key/deadline and terminal lifecycle | `ActionIntent`, `TapProposal`, scheduler callbacks | Sole lifecycle owner for Simple Tap intents |
| `src/simple_core.py` | Composes tracker, planner and intent manager | The three new Tap modules | Optional Tap core selected by config/CLI |
| `src/live_input.py` | Manual arm, generation isolation, focus/PLAYING/ROI/freshness checks, lateness, conflicts, SendInput error release, Hold duration | Windows actuator interface | Shared final safety boundary for both Tap cores and Hold |
| `src/live_engine.py` | Capture-time coordination; keeps Hold route and V6 fallback; selects which Tap tracker/planner runs | Detector, gameplay gate, both tracker paths, scheduler | Existing coordinator with a Simple opt-in branch |
| `src/tracker.py` | Existing V6 motion/identity association; legacy Hold tracking | `Predictor`, optional `ParticlePredictor`, assignment | Retained for V6 rollback and current Hold path; not yet simplified |
| `src/particle_predictor.py` | Position and ETA posterior only | NumPy | Optional ETA comparator under Simple Core; it owns no note identity or scheduling |
| `src/live.py` | CLI, CSV, runtime safety wiring and summary | Windows runtime, capture worker, engine, scheduler | Adds `--tap-core` and Simple lifecycle/performance columns |
| `tools/replay_simple_core.py` | Same-source A/B/C with recorded timestamps and MockActuator | LiveEngine, OpenCV, CSV/JSON | New offline validation tool; never instantiates Windows SendInput |

## State ownership

- `SimpleTracker` owns only short motion associations and track evidence.
- `TapPlanner` creates proposals; it cannot mutate scheduler state.
- `TapIntentManager` owns an accepted Tap's key and deadline until `FIRED`, `CANCELED` or `EXPIRED`.
- `TapScheduler` remains the final authority for safety and input delivery.
- The Hold visual path remains separate and uses the existing bounded scheduler Hold behavior.
