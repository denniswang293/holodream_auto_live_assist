# V7.8.7 Replay Parity and Physical Identity

Run: `C:\Users\USER\Desktop\holodream\output\run_20261101T034646_232725Z`

## Parity

- Semantic assignment parity: **PARTIAL** (1654 recorded unique edges vs 1656 replay; missing 0, extra 2).
- Extra edges at frames 385 and 546 are classified as trace-semantics gaps, not silently removed.
- UID lifecycle parity remains PARTIAL because the original run lacks serialized Tracker/PF snapshots.

## Physical identity

- Rescue cases: 399/simple:5, 525/simple:12, 408/simple:5.
- Software replay: 2 stable, 1 unstable; physical identity: **0 manually verified**.
- Review rows: **28**, all initially `UNREVIEWED/UNKNOWN`.
- Negative-control software verdicts are separate from human identity verdicts.

## Decision

**SHADOW_ONLY_NEEDS_REVIEW. Active remains OFF.** No gate, timeout, detector, Hold or input policy was changed.

## Verification

- pytest exit code: **0**; see `pytest_v787.txt`.
- All alignment uses source frame and capture timestamp; no fixed-FPS substitution.
