# V7.14.6 Tap Geometry / ETA Shadow Report

Run: `C:\Users\USER\Desktop\holodream\output\assist\v7147_experiment\run_20261103T055219_493952Z`
Source video: `output\assist\v7147_experiment\run_20261103T055219_493952Z\live_source.mp4`

## Scope and safety
This is an offline shadow replay. It does not change the active geometry, input lead, Planner, Scheduler, Hold path, or safety gates.
FIRED/key_down/event counts are not game hit truth; grades remain UNKNOWN unless a one-to-one manual label is supplied.

## Runtime facts (SUPPORTED)
- Runtime physical hit y: **325.500**; input trigger y: **295.500**; input advance: **30.000px**.
- Timing source: `global_physical_calibrated`; actual input lead from run: **60.000 ms**.
- Recorded config label: `timing-lead-60ms`. The numeric run value is authoritative; labels are diagnostic metadata.
- Geometry snapshot status: `pending_calibration`; geometry SHA: `e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4`.
- The legacy `config.json.playfield.hit_y` is not assumed to be the Live Assist physical target; Live Assist uses the loaded calibration geometry and records it in `tracking_completion_y`.

## Visual replay
- Track UIDs with usable real bbox observations: **266**; hypotheses: **35910**.
- Crossing statuses: `{'BOUNDED_EXTRAPOLATION': 18800, 'INTERPOLATED': 2820, 'NO_CROSSING_IN_VISIBLE_TRACK': 14290}`.
- Tap key-down rows reviewed: **183**; grade distribution: `{'UNKNOWN': 183}`.
- Per-UID model/planner reason coverage: `{'eta_outside_horizon': 133, 'eta_uncertainty_too_high': 59, 'insufficient_independent_tracks': 4, 'press_time_not_future': 45, 'ready': 183, 'speed_variation_too_high': 72, 'track_not_current_confirmed': 344}`.
- Deadline amendments: **1722** actions over **154** event IDs; amendment delta samples: **1722**.
- `key_down - final_deadline` is an execution offset only: n=183, median=2.200860937591642 ms.
- Frame probe extraction: `OK`; probes written: **489**.
- Anchor comparisons are only geometric timing proxies. A bbox can be clipped or altered by effects; such rows are marked `UNRELIABLE_BBOX`.

## Candidate hypotheses
Top, center and bottom are evaluated independently. Each anchor's own coordinate is used for both crossing and velocity-free interpolation; no center-distance/bottom-position mixing is performed.
The y offsets and lead values are shadow hypotheses, not an active A/B result. No best anchor or hit line is selected without one-to-one game labels.

## Evidence classification
- **SUPPORTED:** the run used the physical calibrated target recorded above and a 60 ms numeric lead; the old `lead-10ms` label was inconsistent and is corrected for future runs in memory.
- **POSSIBLE:** a fixed anchor or target offset may explain SLOW; the current files provide visual crossings and key-down timing but no per-note game grade.
- **UNRESOLVED:** whether top, center or bottom matches the game's judgment anchor; whether the 60 ms improvement is input latency, geometry offset, or song/timing variation.
- **NOT_SUPPORTED:** treating key-down/FIRED, overlay text, or candidate counts as PERFECT/HIT accuracy.

## Missing evidence / next single operation
Manually label the generated `tap_game_grade_review.csv` rows using the adjacent ±300 ms images, retaining UNKNOWN when UID/lane/type/key/grade is not one-to-one. Then run this tool again; only the labelled subset can rank anchor or y hypotheses.
