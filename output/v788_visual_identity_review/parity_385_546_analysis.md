# V7.8.8 parity 385/546 visual analysis

The two V7.8.7 replay-extra edges remain visible; no edge is deleted or relabeled as PASS.

| edge | source frame | candidate | replay track | root cause | confidence |
|---|---:|---|---|---|---|
| extra_385 | 385 | `385:candidate:0` | `1000003` | `TRACE_SEMANTICS` | `HIGH` |
| extra_546 | 546 | `546:candidate:11` | `1000014` | `TRACE_SEMANTICS` | `HIGH` |

## Evidence interpretation

At each center frame the target candidate is present in the candidate trace, but the retained Live assignment-attempt trace has no matching assignment row for that candidate. The trace contains duplicate pair/assignment rows for other edges. This supports `TRACE_SEMANTICS` as the highest-confidence software explanation, but the original run lacks serialized Tracker/PF snapshots, so a full replay PASS cannot be claimed.

The paired images in `cases/parity_385/` and `cases/parity_546/` show original and annotated source frames. Physical identity and game judgment remain UNKNOWN until human review.
