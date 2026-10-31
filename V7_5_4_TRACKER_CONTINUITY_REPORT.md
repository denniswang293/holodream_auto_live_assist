# HoloDream V7.5.4 Tracker Continuity Report

## Status

PR-0 and PR-1A diagnostics completed against commit `947b7dc` and run `run_20261031T181722_597143Z`. No decision threshold or active planner was changed.

## Evidence

- 248 UID were detected; 153 never exceeded DETECTED in the recorded lifecycle. Their final decision reason is `track_not_current_confirmed`, but the run does not contain per-candidate association costs, detector rejection stage, or competition track IDs. They cannot be honestly split into detector miss versus association failure from these files alone.
- 22 UID reached CONFIRMED and later failed the current-track gate before scheduling. One additional confirmed UID ended at `eta_outside_horizon`, and one at `below_event_min_y`.
- 83 frames were dropped while processing ran at 52.06 FPS versus 58.25 FPS capture. This is a plausible pressure source, not proof of a game miss.
- Five unresolved Legacy/Shadow cases remain PF-posterior-width candidates; 16 of 21 Shadow-advantage UIDs later FIRED through Legacy.
- Pink has 11 UID and 1 FIRED; the other 10 are single-frame candidates with no physical truth.

## Root-cause decision

The available run supports a **current/confirmation loss cluster**, but not a safe tracker-gate patch. Existing logs cannot prove whether the first break was detector absence, association rejection, or a competing track. Therefore PR-1B is intentionally not implemented.

## Required next evidence

Enable an optional per-frame diagnostic profile that records candidate-to-track pair costs, reject gates, competing track IDs, detector rejection stage and timestamp gaps. Re-run the same source with fixed seed before changing any gate.

## Rollback / safety

No algorithm changes were made. Legacy Planner, Particle Filter, Shadow-only comparison, Hold ownership, stale/focus/ROI disarm and scheduler dedup remain unchanged.

## Outputs

- `v754_replay_manifest.json`
- `v754_baseline_funnel.csv`
- `tracker_continuity_cases.csv`
- `association_audit.csv`
- `shadow_disagreement_cases.csv`
- `deadline_timeline.csv`
- `v754_ab_summary.json`
- `V7_5_4_BASELINE.md`
- `shadow_case_review.md`
- `deadline_jitter_summary.md`
- `expired_1000129_case.md`

`py -m pytest -q`: 108 passed in 2.94 s.
