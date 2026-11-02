# V7.14.3 Tap SLOW diagnosis

Run: `output\run_20261102T164222_347975Z`

Eight representative frame overlays were manually reviewed, but no per-UID manual labels were available. Frame-only grades are recorded with UID UNKNOWN; per-UID FAST/SLOW/PERFECT/GOOD/BAD/MISS remain **UNKNOWN**.
This report separates scheduling/execution timing from game-side judgement.

## Run counts

- Tap key_down rows: **168**
- Hold key_down rows (control): **60**
- Global READY ratio: **0.8951861181080325**
- Tap review rows with grade UNKNOWN: **168**
- Manually reviewed visual overlay samples: **8** (UID remains UNKNOWN)

## Execution timing (not game input latency)

- final deadline → key_down P50/P90: **2.073754367302172 / 3.337247340823524 ms**
- first → final deadline drift P50/P90: **6.5059402550105006 / 37.8631726052845 ms**
- amendment count P50/P90: **1.0 / 4.0**
- video-index capture/PTS residual P50/P90: **29.02451757267066 / 49.16682043015186 ms**

A positive deadline→key_down residual means the actuator woke after the scheduled deadline; it does not prove SLOW without a game label.

## Required manual review

Fill `tap_judgment_review.csv` only when the video frame, lane, note type, key and game grade can be aligned. Keep ambiguous rows UNKNOWN.
Hold rows are not included in Tap grade ratios; use them only as a control for scheduler/input health.

Review CSV: `tap_judgment_review.csv`
