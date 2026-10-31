# HoloDream V7.5.5 Tracker Association Instrumentation Report

## Scope

- Base commit: `f3dbf26` (V7.5.4).
- Source: `output/assist/run_20261031T181722_597143Z/live_source.mp4`.
- Replay uses `source_video_frame -> capture_timestamp` from the matching `live_video_index.csv`; missing or non-increasing timestamps fail fast. No `frame / 60` fallback is used.
- Legacy Planner + Particle Filter remain the real input path. Simplified Planner and Linear ETA remain diagnostic-only.
- No Detector, Tracker, PF, Planner, Scheduler, Hold or safety decision threshold was changed.

## PR-0 alignment

- 1,443 source frames / 1,443 index rows; timestamp coverage 100%.
- Timestamp fallback rows: 0; alignment audit errors: 0.
- The source video and index distinguish processed/video frame, capture sequence and source video frame in `frame_alignment_audit.csv`.

## Trace output

- Detector trace rows: 92,654.
- Tracker pair rows: 76,603.
- Tracker state rows: 10,618.
- Diagnostic dropped rows: 0.
- Candidate IDs are explicitly frame-scoped (`frame:stage:ordinal`); they are not treated as cross-frame physical identities.
- Replay UID mapping to live UID is `UNKNOWN` unless independently matched; `tracker_root_cause_cases.csv` does not force integer IDs to match.

The trace records detector raw contours, merge proposals, candidate gates, final candidates, pair-cost gates, assignment competition, coasting, last real observation timestamp and actual termination reason. Trace is bounded and disabled by default.

## Diagnostic off/on A/B

`diagnostic_off_on_ab.json` reports:

- Detector candidate signature differences: 0 frames.
- Tracker state signature differences: 0 frames.
- Legacy input path changed: false.
- Shadow active: false.

This confirms the instrumentation did not alter replay candidate order or tracker state. Replay has no live scheduler, so key-action equivalence remains `UNKNOWN` and no input was sent.

## Root-cause status

The 153 DETECTED-only and 22 confirmed-but-not-current cases are indexed in `tracker_root_cause_cases.csv`. The new trace can identify candidate availability and pair-cost gates for the replay, but live UID ↔ replay UID matching is not guaranteed. Cases without a reliable match remain `UNKNOWN`; no gate was relaxed.

Five Legacy/Shadow cases, pink UID `1000005` plus the ten single-frame pink candidates, and the expired UID `1000129` have paired review rows and evidence frames under `case_crops/`. Pink remains an ordinary Tap path; no Flick behavior was added.

## Regression and safety

`py -m pytest -q` → **111 passed**.

Added regression coverage for optional detector tracing, matched association tracing, coasting last-observation timestamps and max-gap termination reasons. Existing Hold, stale/focus/ROI, scheduler and input-safety tests remain green.

## Rollback

Keep `detector.association_diagnostics.enabled` set to `false` to disable trace collection. Removing the bounded diagnostic block restores the previous behavior. The instrumentation has no active planner switch and does not send input.

