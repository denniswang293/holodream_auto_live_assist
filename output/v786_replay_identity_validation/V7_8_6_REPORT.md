# V7.8.6 Replay Parity and Identity Validation

Run: `C:\Users\USER\Desktop\holodream\output\run_20261101T034646_232725Z`

## Parity

- Raw live/replay assignment rows: **3308 / 1656**
- Semantic unique edges: **1654 / 1656**
- Semantic parity: **PARTIAL**; extra=2, missing=0
- UID lifecycle parity: **PARTIAL**
- Exact duplicate live rows are retained in raw counts and removed only for semantic comparison.

## Target cases

- simple:5 frame 399, simple:12 frame 525, simple:5 frame 408 were replayed again.
- Stable software-continuity cases: **2**; unstable: **1**.
- These are Shadow simulation results, not game hits.

## Identity review

- Review rows: **28**; all initially `UNREVIEWED/UNKNOWN`.
- 25 negative controls have adjacent-frame crops; no automatic physical identity verdict was assigned.

## Decision

**SHADOW_ONLY / NEEDS_REVIEW. Active remains OFF.** Semantic parity is not PASS and no physical identity case has been manually confirmed.

## Verification

- pytest exit code: **0**; see `pytest_v786.txt`.
- All replay alignment uses capture timestamp and source frame; no fixed-FPS substitution.
