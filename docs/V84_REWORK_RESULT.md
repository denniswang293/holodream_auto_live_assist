# V8.4 Lane Filter Rework Result

> **Superseded for replay counts and processing timings.** This was the preliminary report. Its `72 vs 18` press counts and `46 vs 232` pause counts came from a capped event history, which truncated Legacy events. See [V84_REGRESSION_ROOT_CAUSE.md](V84_REGRESSION_ROOT_CAUSE.md) for the complete event-stream audit, rerun A/B results, action attribution, and current timing boundaries.

Date: 2026-11-13  
Scope: pixel segmentation, review tooling, and causal offline Mock A/B. No production Active integration and no OS keyboard injection.

## Acceptance summary

| Gate | Result | Evidence / remaining work |
|---|---|---|
| S1 visual | Partial | Candidate masks are sourced from current-frame pixels and the five requested source frames have provenance-linked review crops. The 6.0s green Hold ribbon is retained as a continuous body region. Tap/head/tail ownership and the overlapping 14.9s multi-Hold case still need review; unresolved regions remain `UNKNOWN`. |
| S2 quantitative | Not complete | Annotation GUI, guide, and guarded mask evaluator are present. No labels are marked human-reviewed, so precision/recall/IoU, object recall/false positives, and Hold owner accuracy are intentionally not reported. |
| S3 replay | Replay complete; evidence limited | Same-run full Legacy/Segmented Mock replay completed. Human key events are used only after replay for proximity summaries; no trusted physical-note pairing exists, so this is not game-grade accuracy. |
| S4 live | Not integrated | No Active or OS input path was used. |

This work does not establish that V8.4 is ready to enable.

## Frozen inputs and review fixtures

The input audit inventoried 8 `USABLE`, 12 `PARTIAL`, and 0 unusable recording/Assist runs. The source MP4 and index row counts aligned; timestamps were present for the audited frames. Human key events are retained as posthoc action references only. Geometry remains `pending_calibration`; the baseline code/config hashes are stored in `output/analysis_lane_filter_v84_rework/baseline_environment.json`.

Five source-provenance frames were extracted from Assist run `run_20261109T143554_007912Z`: preview selections 4.9s, 6.0s, 13.2s, 14.9s, and 16.9s map to video frames 294, 360, 792, 894, and 1014. The manifest records corresponding indexed source frames 294, 360, 931, 1086, and 1261 plus capture/acquired timestamps. Preview seconds are not used as action timestamps. Their case notes are visual review prompts, explicitly not ground truth. All five remain `NOT_HUMAN_REVIEWED` and `UNASSIGNED` for split.

The polygon annotator writes draft masks and keeps Hold ownership/physical IDs unknown until a reviewer supplies evidence. `annotations/annotation_queue.csv` lists the requested classes and review fields for each crop. The evaluator refuses draft annotations and emits no accuracy metrics until labels are explicitly marked reviewed. This prevents candidate output from becoming its own truth.

## Pixel segmentation and video artifacts

`src/lane_segmentation.py` segments current-frame color pixels into lane, tap face, Hold head/body/tail, effect/artifact, unknown, and judgment-line channels. It does not derive masks from `Perception.detect()` boxes. The lane mask follows the configured valid geometry, and the judgment line is separate metadata/visualization. The filter preserves observed masks separately from causal past-only association.

The full 1,149-frame Assist run is rendered under `output/analysis_lane_filter_v84_rework/run_20261109T143554_007912Z/`, including `filtered_video.mp4`, `side_by_side.mp4`, `debug_overlay.mp4`, `baseline_legacy_boxes.mp4`, indexed compressed masks, detections, frame summaries, five review-frame bundles, `audit.json`, and `quality_report.json`. The 6.0s mask shows the green ribbon body. In the 14.9s view multiple curved ribbons are visible, but separating their head/tail ownership is unresolved and marked for review rather than claimed as solved.

Measured standalone segmentation processing was 55.34 ms/frame mean and 74.32 ms/frame P90; the legacy perception measurement was 10.67 ms/frame mean. Encoding/rendering added 23.04 ms/frame mean. These offline measurements do not establish real-time FPS.

## Causal Mock replay

Full A/B used recording run `run_20261106T164049_800126Z`, all 3,159 indexed frames, the same capture/acquired timestamps, 14 ms configured processing latency, and an explicit simulated Arm window from 1s to 124s. Both providers used the production `Engine`, `Tracker`, `Timing`, and `Scheduler` logic with in-memory `MockActuator`; no OS keyboard injection occurred. Human key events were excluded from decisions and consulted only afterward. See `output/analysis_lane_filter_v84_rework/run_20261106T164049_800126Z/`.

| Provider | Mean / P90 processing ms/frame | Mock presses | Human key-down references in window | Proximity matches / recall | Extra mock presses | Signed timing p10 / p50 / p90 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 22.24 / 28.61 | 72 | 341 | 23 / 6.74% | 49 | -28.20 / -2.87 / 18.93 |
| Segmented | 64.31 / 90.07 | 18 | 341 | 7 / 2.05% | 11 | 0.58 / 16.79 / 24.59 |

The 80 ms key/time proximity calculation is only an action-reference comparison. It does not establish game hits or physical-note matches. There were 318 unmatched human references for Legacy and 334 for Segmented. All replay rows are `UNVERIFIED` for game grade. The candidate is slower and has fewer posthoc proximity matches in this replay.

A separate 600-frame partial comparison varied simulated latency at 8, 18, 25, and 40 ms. Legacy produced 38, 38, 34, and 0 presses; Segmented produced 0 at each latency. This partial window is not a complete-song result. Its manifest records `partial: true`.

Mock safety audit found balanced press/release events, no duplicate press UIDs, no unreleased UIDs, no illegal keys, and no key-up errors in the full run. There were 2 late rejections for Legacy and none for Segmented. Stale-input pauses were 46 and 232 respectively; the higher segmented count is a safety/availability concern, not evidence of better detection.

## Tests and delivered interfaces

`python -m pytest -q`: **9 passed**. `python -m compileall -q src tools tests`: passed. Added test coverage includes current-frame pixel segmentation, filter isolation, dataset audit, replay isolation, and mask/object metrics. The evaluator counts even one-pixel isolated components in object false positives so thin artifacts cannot disappear from the denominator.

Available tools include `tools/render_lane_filter.py` (`baseline`, `filtered`, and `compare`), `tools/extract_lane_review_frames.py`, `tools/annotate_lane_masks.py`, `tools/evaluate_lane_masks.py`, `tools/replay_lane_filter.py`, `tools/audit_lane_dataset.py`, and `tools/audit_mock_actions.py`.

## Remaining acceptance work

1. A reviewer must annotate positive and negative source pixels, physical note IDs, Hold ownership, occlusion, effects, and split assignment for the five cases and contiguous temporal windows. The 273/282, 498/513, and 1151/1162 historical physical cases cannot be reconstructed from current evidence without validated cross-run identity; they remain unresolved rather than inferred from tracker UIDs.
2. Run the guarded evaluator on reviewed annotations, then add a sequence-level annotated sample for connectivity, identity switches, false merges, recovery, and per-minute errors. Until then S2 is incomplete.
3. Reassess segmentation latency and candidate thresholds against the reviewed set. Current A/B does not support enabling the candidate.
4. Keep the production Active path unchanged until S1–S3 pass with no severe regressions; any later live trial is a separate decision.

## Cleanup performed

Removed only the generated first-round experiment directory `output/analysis_lane_filter_v84/`, its temporary snapshot `output/v84_rework_pre_snapshot.json` if present, and the stale first-round generated design/evaluation/result docs. The copied baseline environment and dataset audit, extracted review fixtures, and all final rework artifacts remain under `output/analysis_lane_filter_v84_rework/`. Original `output/recording/run_*` and `output/assist/run_*` source data were preserved.
