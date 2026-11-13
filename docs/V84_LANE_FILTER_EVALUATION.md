# V8.4 lane-filter evaluation status

## Dataset and selected rendering

Local inventory found 8 manual recording runs and 12 assist runs. All 20 videos
decoded and their encoded frame counts matched index row counts. All indexed
timestamps were present and monotonic. The 8 manual runs are `USABLE`; the 12
Assist runs are `PARTIAL` because their recorded source capture sequence has
18,178 gaps (session counters report 18,151 dropped capture frames). All Assist
session metadata also leaves `video_integrity_verified` false. The audit records
focus/Arm context, key-event and marker counts, and capture-to-acquired timing
in `dataset_audit.csv` and `baseline_environment.json`.

Across manual runs, per-run median capture-to-acquired delay ranges from
18.23–19.22 ms; across Assist runs it ranges from 3.38–4.31 ms. The 8 manual
runs contain 5,672 key events, retained as human action references only.
Assist indexes contain 1,351 unfocused rows and 64,726 rows marked armed; these
are logged context, not replay guarantees.

The complete short assist run `run_20261109T143554_007912Z` was rendered:

| Item | Result |
|---|---:|
| Decoded / indexed frames | 1,149 / 1,149 |
| Missing index rows | 0 |
| Capture timestamp reversals | 0 |
| Recorded source dimensions | 720 × 404 |
| Role observations | 7,504 |
| Mean offline render wall time, observed across runs | 22.97–40.27 ms/frame |
| P90 offline render wall time, observed across runs | 28.56–49.35 ms/frame |
| 60 FPS budget | 16.67 ms/frame |

Wall time includes detection, mask construction, and video encoding, so it is a
conservative pipeline measurement rather than isolated CPU time. Observed runs
exceed the 60 FPS budget. No active integration is justified.

## Physical-note metrics

The output is an adapter around V8.3 perception, not an independent V8.4
detector. No reviewed physical-note annotation set was present or created in
this execution. Consequently, the following are **not evaluable**, rather than
zero or inferred from note UIDs:

| Metric | Status |
|---|---|
| Physical-note recall, false positives/minute, Tap/Hold confusion | Not evaluable: no physical-note and negative-interval labels |
| Identity switches, false merges, fragment duplication | Not evaluable: no physical-note identity labels |
| Hold head/tail owner accuracy, release reference error | Not evaluable: no verified head/tail/release labels |
| Matched reference-action recall, unmatched human actions | Not evaluated as note truth; human key events are not complete judgment labels |
| Baseline/candidate timing error, deadline misses | Not run: no shared replay harness/adapter |
| Game grade | `UNVERIFIED` |

The historical labels 273/282, 498/513, 1151/1162 were not treated as physical
truth or cross-run identity. They need reconstruction against source-video
provenance before a valid sequence comparison. The existing `actions.csv`
files, where present, represent injected actions and do not establish game
judgment.

## Known failure cases and decision

No before/after claim is made for 273/282, 498/513, or Hold-tail ownership.
The renderer's sample and observation stream make frames inspectable, but the
new lane filter has not independently resolved those cases. The remaining
blockers are (1) independent perception and same-frame semantic masks,
(2) annotated physical-note identities/owners and isolated evaluation data,
and (3) an A/B replay adapter using the same tracking/timing/mock scheduler.
Until these exist, perception recall and action improvements cannot be
attributed or claimed. Active remains unchanged.
