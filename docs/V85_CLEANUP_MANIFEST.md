# V8.5 Cleanup Manifest

Created before cleanup on 2026-11-15. Every removal candidate was checked against repository text references in `README.md`, `docs/`, `tools/`, and `tests/`. No Git command was run. Paths below are repository-relative; sizes are bytes before removal.

## Removal candidates (not removed)

| Path | Bytes | Use / reference check | Status and reason | Backup / rebuild |
|---|---:|---|---|---|
| `.pytest_cache/` | 2,397 | Pytest cache; no runtime references. | REMOVE_PENDING_POLICY_BLOCK; disposable test cache. | Recreated by pytest; future runs use `-p no:cacheprovider`. |
| `src/__pycache__/` | 313,520 | Python bytecode cache. | REMOVE_PENDING_POLICY_BLOCK; source is authoritative. | Recreated by Python. |
| `tests/__pycache__/` | 131,061 | Python bytecode cache. | REMOVE_PENDING_POLICY_BLOCK; source and local fixtures remain. | Recreated by Python. |
| `tools/__pycache__/` | 193,227 | Python bytecode cache. | REMOVE_PENDING_POLICY_BLOCK; source is authoritative. | Recreated by Python. |
| `output/analysis_v85_early_identity/profile_smoke/` | 48,628 | Partial three-file smoke profile; superseded by the full four-run `birth_audit_after/`. No docs/tool/test reference. | REMOVE_PENDING_POLICY_BLOCK; partial duplicate. | Rebuild with `tools/profile_v85_birth.py`. |
| `output/analysis_v85_early_identity/birth_audit/` | 4,804,354 | Intermediate three-file candidate scan; superseded by retained `birth_audit_final/` (pre-optimization) and `birth_audit_after/` (current full four-run scan). No docs/tool/test reference. | REMOVE_PENDING_POLICY_BLOCK; intermediate duplicate. | Rebuild with `tools/profile_v85_birth.py`. |
| `output/analysis_v85_early_identity/visual_before/` | 12,530,120 | First six-case candidate videos; random MP4 seek produced source-frame/index mismatch. No docs/tool/test reference. | REMOVE_PENDING_POLICY_BLOCK; invalid render evidence, replaced by sequentially decoded `visual_before_verified/`. | Rebuild with `tools/render_v85_review_set.py`. |
| `output/analysis_v85_early_identity/visual_after/` | 12,530,108 | Paired first six-case render with the same seek/index issue. No docs/tool/test reference. | REMOVE_PENDING_POLICY_BLOCK; invalid render evidence, replaced by `visual_after_verified/`. | Rebuild with `tools/render_v85_review_set.py`. |
| `output/analysis_lane_filter_v84_rework/measured_realtime_partial600/` | 10,672,041 | 600-frame partial measured run; not cited by current reports. | REMOVE_PENDING_POLICY_BLOCK; partial data superseded by retained full measured profiles. | Rebuild with `tools/replay_lane_filter_measured.py --limit-frames 600` (or omit limit for full run). |
| `output/analysis_lane_filter_v84_rework/multi_latency_partial_600/` | 40,383,983 | 600-frame, multi-latency partial run; no current report/tool/test references. | REMOVE_PENDING_POLICY_BLOCK; partial sensitivity output; full fixed/measured canonical outputs remain. | Rebuild with `tools/replay_lane_filter.py --latency-ms ... --limit-frames 600`. |

The two V8.4 partial directories are under the named analysis directory only. Complete V8.4 outputs, action evidence, labels, original recording/assist data, fixtures, and canonical baseline are retained. No other path is eligible for deletion in this cleanup.

## Explicitly retained

| Path / scope | Status | Reason |
|---|---|---|
| `output/analysis_v85_early_identity/baseline_manifest.json` | KEEP | Pre-change file SHA-256s, replay config, test/runtime baseline. |
| `output/analysis_v85_early_identity/birth_audit_final/` and `birth_audit_after/` | KEEP | Reproducible pre/post candidate scan data and four-run summary. |
| `output/analysis_v85_early_identity/fixed_14ms/`, `fixed_14ms_after/`, `measured_realtime/`, `measured_realtime_after/` | KEEP | Separate full fixed-delay and repeated measured-time A/B, including failures and variance. |
| `output/analysis_v85_early_identity/visual_before_verified/`, `visual_after_verified/`, `v84_visual_before/`, `v85_visual_after/`, `v84_v85_visual_comparison/` | KEEP | Sequential source-aligned continuous windows, actual 4.9/6.0/14.9s V8.4 vs V8.5 video, masks and overlays. All human labels remain UNKNOWN. |
| `output/analysis_v85_early_identity/action_loss_attribution.csv` and `action_loss_evidence_v85/` | KEEP | One row per Legacy action and source/pixel evidence. |
| `output/analysis_lane_filter_v84_rework/fixed_14ms_verified/`, `measured_realtime_profiled/`, `action_loss_attribution.csv`, `action_loss_evidence_v4/`, `visual_verified/`, `annotations/`, `docs/V84_REGRESSION_ROOT_CAUSE.md` | KEEP | Canonical prior-round baseline, root-cause report, user annotation, and reproducibility evidence. |
| All `output/recording/run_*/`, `output/assist/run_*/`, `tests/fixtures/`, calibration/config files, `src/live.py`, `src/scheduler.py` | KEEP | Raw sources, human material, safety, or reproducibility-critical files. |
| Other complete V8.4 experiment directories and prior history docs | KEEP | Different complete outcomes are evidence of host/algorithm variation; not provably redundant from their names. |

## Execution attempt and validation without cleanup

No files were removed. The PowerShell execution policy rejected both a workspace-contained recursive removal of `.pytest_cache/` and a single-file removal within it (`blocked by policy`). I stopped deletion attempts rather than work around that block. All candidates above remain in place. To make the authorized cleanup executable locally, `tools/cleanup_v85_candidates.bat` now lists exactly these ten manifest paths, checks its workspace root, previews by default, and requires `--execute` plus a `Y` confirmation before deletion. Its preview mode was run successfully and showed all ten paths under this workspace without deleting anything. Validation ran without cleanup: `python -m compileall -q src tools tests` passed and `pytest -q` passed (20 tests); Replay, render, profile, attribution, and summary CLI help/import smoke passed; the full fixed-delay replay after the segmentation change completed. Raw recordings, assist runs, manual annotations, fixtures, calibration, safety files, and baseline manifest were not targeted.

```bat
tools\cleanup_v85_candidates.bat
tools\cleanup_v85_candidates.bat --execute
```
