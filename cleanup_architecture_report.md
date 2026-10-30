# HoloDream V7 Simple Core — implementation report

## Scope completed in this iteration

- Confirmed the worktree started at the requested V6 Beta 1.2.3 baseline: `e1e73ea125c28a5356529f2e9d40223e671b0349`.
- Added a separate ordinary-Tap path: `SimpleTracker → TapPlanner → TapIntentManager → existing TapScheduler`.
- Added a `--tap-core simple|v6` selector. The checked-in default remains `v6` until independent note/judgment labels exist.
- Simple mode sends only ordinary cyan/yellow Tap candidates through the new core. The V6 tracker and visual Hold path remain available; Hold scheduling, tail release, maximum duration and the safety executor stay in the existing route.
- Added same-source A/B/C Mock replays. No real SendInput calls were made.
- Added an eight-case Simple Core test file and extended two Hold cases to exercise both Tap-core settings.
- Created the requested local branch `cleanup/simple-assist-core`; changes are uncommitted. No commit, push or history rewrite was performed.
- Updated `.gitignore` for runtime output. Backed up the 15 files in the real run to `C:\Users\USER\Downloads\holodream_output_backup_v7_20261030` (72,765,264 bytes verified) and staged only their removal from the local Git index with `git rm --cached`. The original files remain in `output/run_20261030T132141_738544Z`; no commit, push, or history rewrite was performed.

## Same-recording Mock replay

All modes processed the same 3,165 indexed frames from `output/run_20261030T132141_738544Z/live_source.mp4`, with its recorded timestamps, geometry, detector, arm/focus history and MockActuator.

| Mode | Unique scheduled IDs | Tap key-downs | Hold key-downs | Canceled/abstained | Replay FPS | Processing P95 |
|---|---:|---:|---:|---:|---:|---:|
| A: V6 + Particle | 148 | 92 | 8 | 61 | 80.91 | 19.04 ms |
| B: Simple + Linear | 106 | 83 | 8 | 16 | 73.34 | 20.39 ms |
| C: Simple + Particle | 43 | 28 | 8 | 8 | 73.22 | 19.52 ms |

Each mode had zero repeated key-downs for the same intent ID. The duplicate-note audit found four cross-ID pairs requiring visual review (three in B, one in C). They remain unclassified: their ETA gaps are 4.4?31.9 ms while capture-time gaps are 118.9?201.5 ms and observed vertical gaps are 21.5?42 px. Similar lane span and close ETA alone do not establish physical identity; no automatic merge was added. All real-game accuracy and ETA error remain **UNVERIFIED**. Lower action counts do not establish fewer misses or false presses.

The recorded V6 live baseline was 3,239 acquired / 3,165 processed / 74 dropped frames, 58.26 processing FPS, 27.61 ms latency P95, and 120 Tap + 8 Hold key-downs. Its accuracy is also unverified. The replay FPS is a separate offline measurement and must not be compared directly to the live FPS.

## Architecture size

At baseline, the four cited files were 1,466 (`live_engine.py`), 530 (`tracker.py`), 357 (`particle_predictor.py`) and 368 (`live_input.py`) lines. Now they are 1,570, 530, 357 and 368. The four new core modules total 603 lines. Therefore this iteration has **not** met the plan's code-size or old-V6 deletion goals: the Simple path is separated, but V6 remains selectable for rollback and the old tracker remains in use for Hold. Removing overlapping V6 retention code is deferred until the physical-note audit and cancellation review can show it is safe.

The final full pytest run for this worktree was **253 passed in 9.49s** (`pytest_full.txt`).

## Decision

Keep V6 as the formal default for now. Simple + Linear had similar but fewer Tap key-downs than V6 in this replay, while Simple + Particle produced substantially fewer. Without independent physical-note and crossing-time labels, there is no evidence that either Simple setting reduces misses without increasing false presses. The Simple route is implemented and replayable, but it has not passed the plan's accuracy acceptance gate and should not yet be selected for a live test.

See `cleanup_validation_report.md` under `output/v7_simple_core_ab/` for generated metrics; `simple_core_design.md`, `cleanup_dependency_inventory.md`, `cleanup_deletion_matrix.md` and `next_live_test.md` cover implementation and the remaining steps.
