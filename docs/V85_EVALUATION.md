# V8.5 Evaluation

Date: 2026-11-15. All replay output is offline and uses `MockActuator`; no OS input was sent. Original `output/recording/run_*` and `output/assist/run_*` files were read-only.

## Fairness and clock model

The fixed-delay comparison uses the same 3,159 indexed frames from `run_20261106T164049_800126Z`, identical capture/acquired timestamps, 1–124 second simulated arm window, 2ms scheduler polling, geometry hash `7462e360c96e8ae5e4016699e42a0414ddbc9d4a2847f5249735f99b362db35a`, timing calibration hash `0f89988ee775b9dd1773b9cf4cf97dacabc629dc560ca69f18fe1698353cc034`, Engine, Tracker, Timing, Scheduler, and key map. `14ms` is an equal logical delay, not the wall time of perception. It admits all frames.

The measured-time test advances the provider clock by actual `Engine.observe + Engine.decide` time and applies one latest-frame slot. Pending acquired frames are overwritten while inference is busy. Video decode and output encoding are excluded. This mode measures live feasibility, not isolated visual quality.

## Fixed-delay causal Mock A/B

| Code | Mock key-down | Mean / P90 host compute | Posthoc 80ms key/time proximity | Rejections classified as late/expired |
|---|---:|---:|---:|---:|
| Legacy | 343 | 23.44 / 32.85ms | 105/341 | 6 |
| V8.4 Segmented | 213 | 33.11 / 46.50ms | 60/341 | 6 |
| V8.5 before component pruning | 199 | 40.75 / 54.35ms | 60/341 | 2 |
| V8.5 after component pruning | 199 | 39.81 / 53.88ms | 60/341 | 2 |

Fixed-delay baseline and post-optimization outputs are in `output/analysis_v85_early_identity/fixed_14ms/` and `fixed_14ms_after/`. Component pruning did not change any of the three providers' simulated key-down totals. The posthoc proximity score is not physical-note recall or game hit rate.

## Measured-time feasibility A/B

The first measured pass, before the neutral-component optimization, processed Legacy 3156/3159 frames (3 dropped), Segmented 3097/3159 (62 dropped), and V8.5 3009/3159 (150 dropped). Mock key-down totals were 321, 85, and 34 respectively. Compute mean/P90 was Legacy 20.64/26.98ms, Segmented 32.17/43.30ms, V8.5 36.44/47.75ms. This is a regression in V8.5 live feasibility; more key-downs or proximity cannot override that result.

The post-optimization repeat is recorded separately under `output/analysis_v85_early_identity/measured_realtime_after/`. It processed Legacy 3156/3159 (3 dropped), Segmented 3114/3159 (45 dropped), and V8.5 3048/3159 (111 dropped); Mock key-down totals were 339, 141, and 39. Mean/P90 compute was 17.01/24.15ms, 30.54/41.95ms, and 35.28/46.89ms respectively. Logged `input_paused` events with `stale_capture` reason were 231, 620, and 202. The earlier pass counted 235, 405, and 139. These repeat differences show host/runtime sensitivity, and the post-optimization V8.5 result still drops more frames and emits fewer Mock actions than both baselines.

The post-optimization V8.5 profile mean / P90 / P99 is: Normalize 1.00/1.23/1.53ms; Rectify 0.98/1.23/1.47ms; HSV 0.58/0.79/1.03ms; connected components 2.56/3.11/3.78ms; mask and component classification 13.92/20.27/25.59ms; V85 adapter 1.66/2.40/3.23ms; Tracker association 4.79/8.63/14.29ms; Engine decision 5.93/8.17/10.16ms. Stage details for all providers are in `frame_stage_latency.csv`. The full offline renderer reports 14.47ms mean segmentation and 13.39ms mean render/encoding work in separate columns; rendering/encoding is excluded from the replay inference profile.

## Action-loss attribution

Every Legacy key-down is paired to provider-local candidate tracks by same-frame geometry, lane/key, color and multi-frame vertical trajectory; provider UIDs are not used as cross-provider identity. The attribution output has one row per Legacy action and includes raw source-frame evidence, V85 pixel-component/mask evidence, tracker state, timing reason, scheduler outcome, and final mock down/up. Current V8.5 totals are:

| Attribution | Count |
|---|---:|
| V85 same-key Mock action | 116 |
| V85 Mock action on a different key | 29 |
| Engine eligibility gate | 49 |
| Timing gate | 8 |
| Track confirmation gate | 13 |
| Pixel role UNKNOWN | 5 |
| Unresolved after tracking / observation gap | 123 |
| **Legacy actions** | **343** |

The fixed-delay attribution CSV is `output/analysis_v85_early_identity/action_loss_attribution.csv`. The `UNRESOLVED_AFTER_TRACKING` bucket is intentionally not forced into a pixel, tracker, or timing diagnosis. Same-key action counts and the 80ms human-event comparison are auxiliary behavior only, not verified physical-note matches.

## Candidate scan and review clips

Four complete indexed runs were scanned: recording sessions `run_20261106T164049_800126Z`, `run_20261106T171405_612600Z`, and assist sessions `run_20261109T143554_007912Z`, `run_20261109T144952_721038Z`. The current pixel-only provider proposed 13,128 tracks and automatically confirmed 2,966 under its current motion/evidence rules. This is a count of detector tracks, not physical notes. The geometric midpoint birth zone (rectified y=176.75) remains provisional because no reviewed true-note distribution supports changing it.

The candidate-to-confirm tables report per-run, color, and semantic hint. They do not give reviewed recall. No genuine yellow Hold was confirmed by the scan (only one yellow Hold-hinted track in each recording run, neither confirmed); neutral faces mostly remain pending. Therefore early yellow Hold and gray-note behavior remain unevaluated and are not accepted.

`visual_before_verified/review_queue.csv` and `visual_after_verified/review_queue.csv` contain six continuous candidate windows with source frames, rectified frames, masks, overlays, and side-by-side videos. Source-frame hashes match across the two providers. `v84_v85_visual_comparison/v84_vs_v85_selected_windows.mp4` compares V8.4 and V8.5 at the 4.9s, 6.0s, and 14.9s Assist cases; corresponding before/after masks and overlays are PNGs in the same directory. At those snapshots the pixel masks are almost identical, so this is not visual-quality evidence of improvement. All review queue rows have `NOT_HUMAN_REVIEWED`; physical note and Hold owner labels remain UNKNOWN. The fixtures in `tests/fixtures/v85/` are local images with `human_reviewed:false`. No physical-note recall, false-positive rate, type-confusion rate, or head/tail owner accuracy is claimed.

## Safety, test and evidence limits

- Existing Scheduler safety bounds were not changed. No Active default was changed; `src/live.py` still uses Legacy Perception.
- No original media, user annotations, geometry, or timing calibration files were modified.
- Mock safety audit: no illegal keys, duplicate press UID, key-up failure, or down without release in fixed A/B.
- Continuous image windows are review-ready, but no human review was supplied during this run. Thus ID switch, false merge, physical-note recall, and visual false-positive counts remain `NOT_EVALUABLE`.
- Historical 4.9s, 6.0s, and 14.9s assist windows are represented in the offline review/render output; automated masks alone do not establish note truth.

Reproduce with the fixed and measured commands in `README.md`; use the exact birth-zone argument for byte-for-byte comparable configuration. For action attribution, run `tools/attribute_lane_action_losses.py --candidate-provider v85` against the corresponding fixed replay folder.
