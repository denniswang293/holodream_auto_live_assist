# V7.8.9 UID Mapping, Parity and Miss Root Cause

Run: `C:\Users\USER\Desktop\holodream\output\run_20261101T034646_232725Z`

## Scope

- Reviewed scope: **10**; excluded unreviewed: **20**.
- Unreviewed cases remain OUT_OF_SCOPE_UNREVIEWED and are not in any evaluated denominator.

## UID mapping

- Cross-namespace mappings for rescue candidates remain AMBIGUOUS: same candidate/frame evidence supports a local correspondence, but no serialized cross-run Tracker/PF state proves global UID equivalence.
- Frame 408 and 525 ownership are separated by namespace; no false attach or double ownership is asserted.

## Parity

- Recorded semantic assignments: 1654; replay: 1656; extra=2, missing=0.
- Status: **PARTIAL_SOURCE_INSUFFICIENT**; frame 385 and 546 remain visible.

## Miss pipeline

- 18 CONFIRMED_NOT_FIRED software UIDs were classified; this is not 18 proven game MISS.
- See `confirmed18_lifecycle_root_cause.csv` and `neutral_pink_tap_cases.csv`.
- Pink remains ordinary Tap; neutral/gray remains a separate UNKNOWN class.

## Human evidence

- Human same-note labels: 10 in reviewed scope.
- Stable/unstable software recoveries: 2 / 1; causally proven hardware hits: 0/UNKNOWN.
- User game labels are HUMAN_REPORTED_UNVERIFIED; aggregate game accuracy remains UNKNOWN.

## Decision

**SHADOW_ONLY_NEEDS_REVIEW. Active remains OFF.**

- pytest exit code: 0; see `pytest_v789.txt`.
- No live input, detector/tracker gate, Planner, Scheduler, Hold or safety policy was changed.
