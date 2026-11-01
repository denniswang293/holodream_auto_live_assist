# V7.8.4 Targeted PF-Assisted Reacquisition

Run: `C:\Users\USER\Desktop\holodream\output\run_20261101T034646_232725Z`

## Evidence

- Coast episodes (correct denominator): **119**
- Eligible rescue episodes: **73**
- Episodes with a real unassigned candidate: **117**
- Targeted proposal-only pairs: **0**
- Stable Shadow recoveries (two subsequent real observations): **0**
- Negative controls: **25** (`PASS_DATA_UNREVIEWED`)
- Game accuracy: **UNKNOWN**

### Recovery buckets

- `UNKNOWN`: **5**
- `all_gates_reject`: **27**
- `ambiguous_multi_track`: **2**
- `baseline_recovered_same_uid`: **44**
- `legacy_candidate_assigned_elsewhere`: **2**
- `no_valid_pf_state`: **39**

## Interpretation

The existing run contains PF proposal rows, but they were recorded before the V7.8.4 post-Legacy rescue boundary. The analyzer therefore filters them by real coasting state, candidate assignment and capture timestamp; it does not count baseline matches as new recovery and does not promote proposal-only rows to stable recovery without an isolated state replay.

## Decision

**Remain Shadow. Do not enable Active.** Stable incremental recovery is zero in this evidence package, and all manual controls still need visual review. No gate was widened.

## Files

- `baseline_coast_episodes.csv`
- `eligible_rescue_attempts.csv`
- `pf_shadow_targeted_proposals.csv`
- `episode_ab_comparison.csv`
- `confirmed_not_fired_audit.csv`
- `false_attach_negative_controls.csv` and `candidate_identity_case_crops/`
- `input_manifest.json`, `signature_parity.json`, `v784_ab_summary.json`, `safety_regression.md`

## Verification

- pytest exit code: **0**; see `pytest_v784.txt`.
- All matching uses capture timestamp/source frame; no fixed-FPS time substitution.
