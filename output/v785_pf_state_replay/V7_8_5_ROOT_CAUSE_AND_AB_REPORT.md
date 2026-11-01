# V7.8.5 PF State Recovery and True Replay A/B

Run: `C:\Users\USER\Desktop\holodream\output\run_20261101T034646_232725Z`

## Result

- Baseline replay parity: **PARTIAL**
- Baseline same-UID recoveries: **79**
- B Shadow rescue transitions: **3**
- B stable incremental recoveries (2 later real observations): **2**
- Failed/unstable rescues: **1**
- Negative controls: **25** (`PASS_DATA_UNREVIEWED`)
- GAME_ACCURACY: **UNKNOWN**

## PF state first-root causes

- `PF_NEVER_INITIALIZED`: **38**
- `SOURCE_TRACE_INSUFFICIENT`: **1**

## Gate blockers

- `candidate_competition`: **3**
- `horizontal_span_incompatible`: **10**
- `identity_coast_expired`: **10**
- `innovation_outside_pf_gate`: **4**
- `original_key_not_supported`: **11**
- `unknown_has_special_or_competing_visual_features`: **1**

## Decision

Active remains disabled. The replay is isolated and never calls input, Planner or Scheduler. No coast/uncertainty gate was widened. Manual identity truth remains UNKNOWN.

## Verification

- pytest exit code: **0**; see `pytest_v785.txt`.
- All replay ordering uses capture timestamps and source frame index; no fixed FPS conversion.
