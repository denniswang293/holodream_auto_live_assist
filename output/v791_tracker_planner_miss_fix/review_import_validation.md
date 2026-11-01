# Review import validation

- Completed review rows: **30**.
- `REVIEWED`: **10**; `UNREVIEWED/UNKNOWN`: **20** (excluded from the evaluated denominator).
- Human `SAME_PHYSICAL_NOTE`: **10**.
- User-entered PERFECT/GOOD/MISS values: **4**, retained as `HUMAN_REPORTED_UNVERIFIED`; no automatic game accuracy was calculated.
- Duplicate case IDs/conflicting verdicts: **0** in the merged file.
- Source/evidence fields were not changed by the partial merge importer.

The 20 unreviewed cases are retained but are not PASS/FAIL and do not block this offline audit. They do block any claim of complete identity coverage or Active promotion.
