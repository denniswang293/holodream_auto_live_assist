# V7.8.8 Decision Report

Review source: `C:\Users\USER\Desktop\holodream\output\v788_visual_identity_review\physical_identity_review_completed.csv`

## Human review

- Cases: **30** (rescue=3, negative controls=25, parity=2).
- `manual_review_complete`: **False**.
- Physically verified incremental rescue: **3**.
- False attach verified: **0**.
- Negative controls verified: **0**.
- Unreviewed/unknown cases are not treated as successes or failures.

## Software A/B (not physical truth)

- Legacy and Shadow results remain separate; Shadow produced three simulated rescue transitions, two stable and one unstable.
- `FIRED`, key_down, UID continuity and replay recovery are not game judgments.

## Parity

- Semantic replay parity: **PARTIAL**; recorded 1654 unique edges vs replay 1656 (extra=2, missing=0).
- 0 extra/0 missing is required for PASS. Frame 385 and 546 remain trace-semantic audit cases; no replay edge was deleted.

## Gate

**SHADOW_ONLY_NEEDS_REVIEW**

- PF Active remains OFF; Legacy remains the real input path.
- Game accuracy: **UNKNOWN** (no direct game judgment source).
- No detector, tracker, planner, scheduler, Hold or safety gate was modified by this aggregation.
- Full pytest result: see `pytest_v788.txt`.
