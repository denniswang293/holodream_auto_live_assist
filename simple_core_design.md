# Simple Assist Core design

```text
Shared Capture → 720×404 normalize → Gameplay gate → Detector
                                           ├─ ordinary cyan/yellow Tap → SimpleTracker
                                           │     → TapPlanner → TapIntentManager ─┐
                                           └─ green/yellow Hold path → V6 Hold route ├→ TapScheduler
                                                                                      → final safety checks → actuator
```

## SimpleTracker

- Matches current Tap candidates one-to-one using timestamp gap, forward vertical motion, horizontal step, compatible lane keys and body-span ratio.
- Collapses only same-frame contours whose appearance, keys, near-identical vertical position and horizontal span overlap all match. Two stacked same-lane detections remain separate tracks.
- Uses the existing Theil–Sen + MAD predictor or the existing particle filter. It does not add a new estimator or hand off particle identity state.
- Keeps a track through bounded short missed-frame gaps. It never writes to the scheduler and never treats `lost` as a cancellation command.
- Emits an intent UID from one monotonically increasing tracker ID; IDs are not recycled during a session.

## TapPlanner

- Requires a current confirmed ordinary Tap, stable candidate key evidence, a current covered key that is explicitly allowed by the geometry-bound user rule, a finite future ETA inside the existing horizon, and uncertainty within the configured limit.
- Does not use overlay boxes as authorization and does not relax ETA or tracking thresholds.
- Assigns one key to each proposal using lane coverage and current key/time reservations. It does not merge notes on same-key/close-time alone.
- Proposals remain mutable until accepted. Once accepted, the key and `hit_at` are frozen.

## TapIntentManager

Lifecycle: `UNSCHEDULED → PENDING → FIRED | CANCELED | EXPIRED`.

- Calls the existing scheduler only when it is armed and its latest context is ready.
- A pending Simple intent is namespaced and skipped by the old V6 retention loop.
- Tracker dropout does not replace, extend, or cancel a pending key/deadline.
- Scheduler focus, PLAYING, ROI, freshness, generation, lateness, key conflict, stop and actuator-failure checks remain authoritative.
- Terminal UIDs cannot be re-scheduled.

## Hold

Hold detection, selected start key, visible-tail release, maximum duration, emergency release and input safety stay in the existing Hold code path. Simple Tap control does not send or release Hold actions.
