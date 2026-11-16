# Project Cleanup Manifest

Date: 2026-11-16
Status: COMPLETE

Scope: keep the launchers and their project dependencies, the repository metadata, project source/configuration/tests/docs/tools, and `output/recording/`. Remove generated offline-analysis outputs and prior Assist-run outputs. No Git command was run.

## Exact deletion targets

| Path | Files | Bytes | Reason | Rebuild / recovery |
|---|---:|---:|---|---|
| `output/analysis_lane_filter_v84_rework/` | 1,746 | 991,178,124 | Offline replay, masks, videos, and benchmarks; not used by either launcher. | Can regenerate analysis from retained recordings and tools; exact host timings may differ. |
| `output/analysis_v85_early_identity/` | 528 | 384,884,350 | Offline candidate audits, replay outputs, and rendered comparisons; not used by either launcher. | Can regenerate candidate/replay outputs; human/provisional review state is not equivalent to physical truth. |
| `output/analysis_v86_autoloop/` | 8,633 | 8,884,804,135 | Iteration diagnostics, traces, case videos, and analysis outputs; not used by either launcher. | Some reports can be regenerated from recordings; exact intermediate outputs are not guaranteed. |
| `output/assist/` | 52 | 99,363,760 | Prior runtime logs and optional video outputs; the normal launcher creates a fresh run directory as needed. | Old sessions cannot be recreated exactly. User explicitly requested removing non-recording outputs. |
| `output/v84_pre_delegate_snapshot.json` | 1 | 1,711 | Historical analysis snapshot; not a launcher dependency. | Not required for runtime. |

Total removed from output: 10,360,232,080 bytes (about 9.65 GiB).

## Preserved

This list records the state immediately after the first output cleanup. The later offline source cleanup below supersedes its `src/`, `docs/`, `tests/`, and `tools/` entries.

- `output/recording/`: 40 files, 1,877,541,918 bytes at pre-cleanup inventory. This exact directory is outside every deletion target.
- `.git/` metadata; no Git commands will be used.
- `src/`, `config/`, `tools/launch_assist_clean.cmd`, `tools/launch_assist.cmd`, Python dependency manifests, `README.md`, `docs/`, `tests/`, and other project source/maintenance files.

## Verification

The five exact targets were removed successfully. Post-cleanup checks found all five absent; `output/recording/` remains present with the same 40 files and 1,877,541,918 bytes inventoried before deletion. Both launchers and the required source/configuration files remain present. `python -B -m src.live --help` exited 0 without starting input or creating output. The exact-path cleanup BAT was removed after use, and obsolete `tools/cleanup_iteration_0088_duplicate_replays.bat` was removed after its targets were deleted. No Git command was run.

## Offline experiment source cleanup (2026-11-16)

Following the follow-up request, removed the offline experiment implementation as well as its generated outputs. The exact categories removed were:

- All `tools/*` offline replay, segmentation, attribution, profiling, rendering, audit, and experiment cleanup utilities. Only `tools/launch_assist.cmd` and `tools/launch_assist_clean.cmd` remain.
- `src/early_perception.py`, `src/lane_filter.py`, and `src/lane_segmentation.py`, which were not imported by the live Legacy runtime.
- All `tests/fixtures/` image fixtures and the tests dedicated to offline segmentation, replay, output attribution, and V8.5/V8.6 experiment workflows.
- Historical V8.4–V8.6 experiment plans, evaluation reports, and result reports.

Retained tests cover runtime decision recording, key choice, Hold label recovery, tracker identity/association, and scheduler safety. Three retained tests were renamed to remove experiment version labels. The project README now describes the cleaned project and no longer gives commands for deleted offline tools. `output/recording/` was not targeted and remains read-only.

No Git command was used. Tests were not run during this file cleanup.
