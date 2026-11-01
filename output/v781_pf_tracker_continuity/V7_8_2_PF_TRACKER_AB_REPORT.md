# V7.8.2 PF-assisted Tracker Continuity A/B

Run: `C:\Users\USER\Desktop\holodream\output\run_20261101T034646_232725Z`

## Result

- PF Shadow proposal rows: **12689**
- Shadow reacquisition proposals: **8**
- Baseline already assigned the same UID: **8**
- Incremental reacquisition opportunities: **0**
- Candidate conflict rows: **1337**
- Possible identity-mismatch risk rows: **2054** (see `pf_mismatch_risk_cases.csv`)
- Physical/game hit truth: **UNKNOWN** (no game judgment source)

## Continuity

- Coasting episodes: **270**
- Classification: `{'transient_coast_recovered_same_uid': 101, 'lost_without_reacquisition': 169}`
- Short occlusion cases with same-UID recovery: **20**

## Manual cases

- Review queue: **40** rows; crops: **40**
- Short occlusion CSV/crops: **20** cases
- Gray, pink, and overlap CSVs are separated for visual review.
- Software FIRED/key_down is not treated as a game hit.

## Safety

- Active Tracker, Legacy Planner, Hold, scheduler gates, safety stop, and frame acquisition were not modified.
- PF layer is Shadow/offline-only and `input_sent` remains false.

## Verification

- pytest exit code: **0**; see `pytest_v782.txt`.
- A/B matching uses capture timestamps and source frame index; no fixed-FPS substitution.
