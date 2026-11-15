# V8.4 Lane Filter regression: root cause and verified rework

Date: 2026-11-14  
Scope: complete same-source replay, current-pixel segmentation, per-action attribution, and measured inference feasibility. No production Active integration or OS key injection.

## Finding

The reported `72 vs 18` press gap and `46 vs 232` stale-pause gap are not trustworthy counts. The replay's Scheduler retained only its most recent 512 events. `updated` events consumed that buffer, so the old Legacy `mock_actions.csv` omitted earlier press and pause events. The full callback event stream now records all events before that display/history cap. On the original fixed-delay run, the complete event totals were 348 Legacy presses and 18 Segmented presses, with 232 input-pause events for each provider. Therefore the reported 54-press difference was an artifact of incomplete event logging; the uncapped original fixed replay's algorithm gap was 330 presses.

**Answer to the original 54-press question:** those 54 presses cannot be assigned to segmentation, adapter, tracker, Timing, Engine, or Scheduler. They were not a valid complete-stream difference: the Legacy view was truncated at 512 Scheduler events, while the Segmented view retained its full 350-event history. The corrected full callback stream changes the comparison to 348 vs 18. Likewise, 46 vs 232 pause events was a retention-window mismatch; the full stream contains 232 for both. Later 348/228, 343/213/199 (older V8.5 snapshot), and 343/221/179 (current V8.6 baseline) tables are different code/replay snapshots and must not be mixed with the original 72/18 snapshot.

After the perception/adapter fixes in this document, a complete fixed-14ms run yields 348 Legacy versus 228 Segmented Mock key-downs. The revised attribution below distinguishes 161 Legacy actions without a same-key paired action from 41 candidate actions not paired to a Legacy action; the net count gap is 120. These are provider-output comparisons, not physical-note recall. A separate measured-time replay yields a materially different gap because Segmented takes longer per frame and the live-style latest-frame admission drops frames. The two replay modes answer different questions and must not be combined.

## P0 — replay fairness and the 14ms / 64ms discrepancy

Both providers read the same 3,159 indexed frames from recording `run_20261106T164049_800126Z`; capture/acquired timestamp rows, 1–124s simulated Arm window, 2ms scheduler polling, Engine, Tracker, Timing, Scheduler, key map, geometry, and calibration inputs are shared. Geometry SHA-256 is `7462e360c96e8ae5e4016699e42a0414ddbc9d4a2847f5249735f99b362db35a`; timing calibration SHA-256 is `0f89988ee775b9dd1773b9cf4cf97dacabc629dc560ca69f18fe1698353cc034`. Geometry remains `pending_calibration`.

| Replay | Frame admission and processing clock | Complete result |
|---|---|---|
| Fixed-delay algorithm A/B | All 3,159 frames admitted; `processed_at = acquired_at + 14ms` for both providers. The 14ms is a synthetic logical delay, not measured compute. | Legacy 348 presses, 22.68ms mean / 30.18ms P90 host loop; Segmented 228 presses, 26.43ms mean / 36.29ms P90 host loop. |
| Measured-time feasibility A/B | Each provider is timed independently using `Engine.observe + Engine.decide`; inference time advances its clock. A single latest-frame slot replaces pending frames while inference runs. Decode, video render, and encode are excluded. | Latest profiled run: Legacy 3,157 processed / 2 dropped, 351 presses, 16.42ms mean / 22.97ms P90; Segmented 3,116 processed / 43 dropped, 158 presses, 31.45ms mean / 42.17ms P90. Input-pause events: 229 / 789. |

The earlier `64.31ms mean / 90.07ms P90` report did not represent the fixed 14ms injected delay. Its wall-time boundary was the older replay instrumentation. The current measured replay explicitly times observe plus decide and excludes offline decode/encoding; it measures Segmented at 31.45 / 42.17ms. A repeat before final profiling measured 28.36 / 38.40ms and 185 presses, demonstrating host/runtime sensitivity near stale limits. This run-to-run spread is itself a feasibility concern; the latest result is used consistently for the final table.

The measured mode intentionally has provider-specific frame admission, because real computation is the variable being evaluated. It is not a fair isolation of pixel recognition quality; use fixed-delay A/B for that. Conversely, fixed-delay A/B says nothing about whether current compute can meet a live frame budget.

All actions are from `MockActuator`; there was no OS keyboard injection. Human key events are consulted after replay only. The 80ms key/time proximity metric is an auxiliary diagnostic (latest fixed run: 107/341 Legacy and 69/341 Segmented) and is not game hit rate, physical-note recall, or ground truth.

## P1 — revised action attribution with exact Tracker/component provenance

The previous CSV assigned a nearby pixel component independently of the matched Tracker track, which can misstate which segmentation input caused a decision. That file and its summary are preserved as `action_loss_attribution_pre_provenance_fix.csv` and `action_loss_attribution_summary_pre_provenance_fix.csv`; their stage counts below are historical and **superseded**. The current canonical `action_loss_attribution.csv` was regenerated from the same immutable fixed-14ms replay. Cross-provider pairing still uses same-frame geometry, lane/key, color, and motion; a component is linked to the matched track only with an exact provider + video-frame + Tracker-UID trace edge. A spatially nearby detection without that edge is reported separately and does not prove a component-to-track cause. Stale observations without a fresh exact-frame link remain low-confidence `TRACK_ASSOCIATION_UNVERIFIED`.

| Revised per-Legacy-action outcome | Count | Interpretation |
|---|---:|---|
| Segmented action, same key | 144 | Same-key paired Mock action. |
| Segmented action, wrong key | 43 | Paired candidate action used another key. |
| Tracker association unverified | 86 | Candidate track/component linkage is not proven at the reference frame. |
| Track not active at reference frame | 38 | No matching candidate decision exists at that exact frame. |
| Engine eligibility gate | 12 | Exact-linked track has a recorded Engine eligibility reason. |
| Timing insufficient observations | 1 | Exact-linked track has too few observations. |
| Scheduler rejection | 2 | Exact-linked candidate action was rejected by Scheduler. |
| UNKNOWN | 22 | No supported stage assignment; left unresolved. |
| **Total Legacy actions** | **348** | One row per Legacy Mock key-down. |

Only 78/348 rows have an exact current-frame Tracker-UID-to-component link; 270 rows have a spatially overlapping but unverified detection. Physical-note labels remain `UNKNOWN`. In net press totals, 161 rows lack a same-key paired action and 41 candidate Mock presses are not paired to Legacy rows, giving a 120-count net gap (348 vs 228). Do not read that net difference as recall or 161 confirmed missed physical notes. The corrected per-action CSV and source images are in `output/analysis_lane_filter_v84_rework/` and `attribution_revision_0012/`.

Frame 97 is now classified `TRACK_ASSOCIATION_UNVERIFIED`, not as a confirmed Timing loss: the matched candidate track's last observation is stale, and the current-frame spatially overlapping cyan component remains `UNKNOWN` without a Tracker UID link. Frame 177 is a same-key Segmented action in this V8.4 run; it must not be confused with the separate V8.5 replay's unassigned Tap at that frame. The revised attribution manifest is `output/analysis_lane_filter_v84_rework/attribution_revision_0012/attribution_manifest.json`.

### Iteration 0013 Tracker trace follow-up

The 86 `TRACK_ASSOCIATION_UNVERIFIED` V8.4 rows were inspected with opt-in same-frame Tracker edge diagnostics, selected component IDs, and source-space candidate regions. The refinement is: 73 spatial components were dropped before Tracker input by the semantic adapter, six were assigned to an existing cap, four were ambiguous, one prior cap was outside the 240ms live-association window, one exact component hit a hard gate, and one remains unresolved. These are candidate-region execution facts, not 86 physical-note misses; all physical-note links remain UNKNOWN.

Frame 97 gives a concrete boundary record: Segmented component 83 has cyan pixels, bbox `(0,250,209,73)`, area 4,023, role `unknown`, and conversion `dropped_semantic_gate`. The raw component is broad and vertically extended; the available trace does not prove that it is the Legacy Tap, so it remains UNKNOWN and was not made executable. Full trace and per-case refinement are in `output/analysis_v86_autoloop/iteration_0013/`; no Scheduler, Tracker gate, calibration, or Live default changed.

### Superseded attribution (pre-provenance audit)

The historical table below is retained only to explain earlier reports. Its adapter/segmentation/Timing/Engine counts were derived before exact Tracker-UID-to-component linkage was required, so they are no longer accepted as causal stage counts.

| Per Legacy action outcome | Count | Confidence and interpretation |
|---|---:|---|
| Segmented action, same key | 144 | High; a same-key candidate action is visible along a trajectory. |
| Segmented action, wrong key | 43 | High; visual trajectory was present, but its simulated key differed from the Legacy lane key. This is not a missed detection. |
| Timing gate | 61 | High: 58 `stale_observation`, 3 `motion_uncertainty`. |
| Engine eligibility gate | 51 | 23 high / 28 medium; 42 `insufficient_motion_or_late_origin`, 8 `hold_head_not_verified`, 1 `no_reliable_key_coverage`. |
| Adapter conversion drop | 14 | High; Segmented component existed but its `UNKNOWN`/non-executable role was dropped at the old Detector interface. |
| Segmentation role UNKNOWN | 8 | Medium; overlapping pixel evidence remained unknown rather than being forced into a note type. |
| Tracker/state unresolved | 25 | Medium; `insufficient_observations`; trajectory did not establish an action. |
| Scheduler rejection | 2 | High; late. |
| **Total Legacy actions** | **348** | Sum of mutually exclusive attribution rows. |

The 144 same-key outcomes account for 144 of the 348 Legacy actions; 43 more had a visually paired action on the wrong key. The remaining 161 are accounted for by the timing, engine, adapter, unknown-role, tracker, and scheduler stages. These are trajectory-correspondence findings, not a human-labeled physical-note recall score. Ambiguous causes remain in their explicit UNKNOWN/unresolved buckets.

Frame 77 is a concrete confirmed Hold example: the previous segmentation produced a body but no executable head; current pixels now yield a connected `hold_head` at rectified bbox `(181,287,97,28)`, alongside the ribbon body/tail evidence. The trajectory is confirmed and produces the same-key Mock action. Frame 97 demonstrates a different failure stage: the Segmented track exists, but its observation is stale and Timing gates it. Per-case evidence triptychs are under `output/analysis_lane_filter_v84_rework/action_loss_evidence_v4/`.

## P2 — pixel segmentation and adapter corrections

Changes in `src/lane_segmentation.py` and the adapter in `src/lane_filter.py`:

- Hold head/tail terminal caps are derived from stable endpoint rows of the current connected green ribbon. Body, endpoint boxes, and observed pixels have explicit connection evidence; the Detector adapter now preserves `HOLD_HEAD`, `HOLD_BODY`, and `HOLD_TAIL` roles instead of reducing every component to a generic box.
- Cyan/yellow Tap recovery proposes a horizontal face core with morphology, constrained to the playable ROI. The accepted mask is clipped to current-frame HSV-class pixels; it does not fill a rectangle and uses no output from `Perception.detect()`. Sparse flashes and thin strokes fail face density/shape gates. Overlapping/uncertain pixels remain `UNKNOWN`.
- Connected components remain separated by color class, use tight component ROIs, and retain independent component IDs. This avoids unrelated colors joining one component and avoids repeated full-frame label masks.
- A regression fixture uses an actual recording frame for the curved green Hold endpoint; another fixture checks a Tap panel joined to a thin effect stroke.

These changes recovered segmented fixed-delay Mock presses from the old full-stream 18 to 228. This is a real simulated-action improvement, but the 43 wrong-key actions, 8 unknown-role cases, and 14 adapter losses show that role/key ownership is not finished. The overlapping multi-Hold case at 14.9s is still not accepted as correctly owned solely from these masks.

## P3 — processing breakdown

The latest measured-time run's per-frame stage profile (`stage_profile_by_frame.csv`) separates production inference from offline video output. Mean / P90 milliseconds:

| Stage | Legacy | Segmented |
|---|---:|---:|
| Normalize | 0.69 / 0.97 | 0.95 / 1.17 |
| Rectify | inside Legacy perception | 0.93 / 1.14 |
| HSV conversion | inside Legacy perception | 0.49 / 0.61 |
| Gray conversion | inside Legacy perception | 0.13 / 0.21 |
| Connected components | Legacy detector's internal perception | 1.66 / 1.99 |
| Mask/classification work (Tap recovery separately profiled) | inside Legacy perception | 12.03 / 18.12; Tap ROI recovery 2.12 / 3.12 |
| Data conversion | inside Legacy perception | 1.15 / 1.80 |
| Tracker association | 1.49 / 2.66 | 3.57 / 6.81 |
| Engine decision | included in observe+decide total | included in observe+decide total |
| Observe + decide total | 16.42 / 22.97 | 31.45 / 42.17 |

Legacy's internal perception does not expose directly comparable HSV/gray/mask sub-stages. Segmented's measured profile totals should not be summed with the observe+decide row; they are nested timings. A separate offline render reports approximately 29.50ms/frame for combined rendering, output writes, mask compression, and video encoding. That workload is excluded from measured inference and must not be presented as recognition latency.

The Tap morphology proposal is ROI-limited; component extraction works on local bounding boxes; full-frame normalization/rectification is performed once; the offline renderer reuses the rectified frame. Remaining cost is dominated by mask/classification and Tracker/decision work, not HSV or gray conversion.

## P4 — visual/action review and remaining limits

Full visual output was regenerated for all 3,159 frames. It includes `side_by_side.mp4`, `filtered_video.mp4`, `debug_overlay.mp4`, `baseline_legacy_boxes.mp4`, lossless channel mask chunks, and raw/rectified/gray/mask/overlay bundles at 4.9s (frame 294), 6.0s (360), 13.2s (792), 14.9s (894), and 16.9s (1014). These are actual current-frame outputs, not boxes painted into candidate masks.

`pytest -q`: 13 passed. `python -m compileall -q src tools tests`: passed. The full fixed and measured replays are complete and both action streams show balanced Mock key-down/key-up events; no illegal keys, key-up failures, or unreleased press IDs were found. No Active path was enabled.

The current evidence is sufficient to repair the observed endpoint and panel-mask defects and to identify losses in Timing, engine eligibility, adapter conversion, key selection, and compute admission. It is not sufficient to claim validated physical-note recall or promote Active: the geometry is still pending calibration; no small reviewed Tap/Hold/effect/occlusion/negative-label set has been completed; multi-Hold ownership remains uncertain; and measured Segmented processing is slower, drops more frames, and causes more stale-pause events than Legacy. Keep Active disabled pending a reviewed sequence set and a repeatable real-time improvement.

## Reproducible output paths

- Fixed-delay full A/B: `output/analysis_lane_filter_v84_rework/fixed_14ms_verified/run_20261106T164049_800126Z/`
- Measured-time full A/B: `output/analysis_lane_filter_v84_rework/measured_realtime_profiled/run_20261106T164049_800126Z/`
- Attribution CSV: `output/analysis_lane_filter_v84_rework/action_loss_attribution.csv`
- Corrected action evidence images: `output/analysis_lane_filter_v84_rework/attribution_revision_0012/action_loss_evidence_v4/`
- Full video and masks: `output/analysis_lane_filter_v84_rework/visual_verified/run_20261106T164049_800126Z/`

Original `output/recording/run_*` and `output/assist/run_*` inputs were read only. No Git commands were run.


## Iteration 0046 ? preserve Hold connection lineage

Added a per-frame `connection_group_id` shared by each source hold connected region's body, derived head, and derived tail; propagated it through LaneObservation CSV, both provider conversion traces, and replay tracker-input rows. Masks, semantic gates, timing, Tracker, Engine, Scheduler, and actions were not changed. Full fixed 3,159-frame 14ms Replay is byte-identical to iteration 0037 for mock actions, safety audit, frame summary, physical-note decisions, and posthoc action comparison (343/221/194 downs; all safety counters zero). Group audit: 28,120 groups, 44,754 grouped rows, zero endpoint groups without body; tracker inputs carry groups for Segmented 22,213/22,213 and V8.5 8,317/8,317. Targeted 24 and full 69 tests pass. A 15-instance assistant-visual label seed and source/rectified masks were created for frames 294, 360, 894; they are provisional, not human truth. Status remains OFFLINE_NOT_PASSED. See `output/analysis_v86_autoloop/iteration_0046/iteration_report.md`.
