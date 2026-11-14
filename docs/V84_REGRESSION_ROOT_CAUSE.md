# V8.4 Lane Filter regression: root cause and verified rework

Date: 2026-11-14  
Scope: complete same-source replay, current-pixel segmentation, per-action attribution, and measured inference feasibility. No production Active integration or OS key injection.

## Finding

The reported `72 vs 18` press gap and `46 vs 232` stale-pause gap are not trustworthy counts. The replay's Scheduler retained only its most recent 512 events. `updated` events consumed that buffer, so the old Legacy `mock_actions.csv` omitted earlier press and pause events. The full callback event stream now records all events before that display/history cap. On the original fixed-delay run, the complete event totals were 348 Legacy presses and 18 Segmented presses, with 232 input-pause events for each provider. Therefore the reported 54-press difference was an artifact of incomplete event logging; the uncapped original fixed replay's algorithm gap was 330 presses.

After the perception/adapter fixes in this document, a complete fixed-14ms run yields 348 Legacy versus 228 Segmented Mock key-downs. The remaining 120-count difference is traced per Legacy action below. A separate measured-time replay yields a materially different gap because Segmented takes longer per frame and the live-style latest-frame admission drops frames. The two replay modes answer different questions and must not be combined.

## P0 — replay fairness and the 14ms / 64ms discrepancy

Both providers read the same 3,159 indexed frames from recording `run_20261106T164049_800126Z`; capture/acquired timestamp rows, 1–124s simulated Arm window, 2ms scheduler polling, Engine, Tracker, Timing, Scheduler, key map, geometry, and calibration inputs are shared. Geometry SHA-256 is `7462e360c96e8ae5e4016699e42a0414ddbc9d4a2847f5249735f99b362db35a`; timing calibration SHA-256 is `0f89988ee775b9dd1773b9cf4cf97dacabc629dc560ca69f18fe1698353cc034`. Geometry remains `pending_calibration`.

| Replay | Frame admission and processing clock | Complete result |
|---|---|---|
| Fixed-delay algorithm A/B | All 3,159 frames admitted; `processed_at = acquired_at + 14ms` for both providers. The 14ms is a synthetic logical delay, not measured compute. | Legacy 348 presses, 22.68ms mean / 30.18ms P90 host loop; Segmented 228 presses, 26.43ms mean / 36.29ms P90 host loop. |
| Measured-time feasibility A/B | Each provider is timed independently using `Engine.observe + Engine.decide`; inference time advances its clock. A single latest-frame slot replaces pending frames while inference runs. Decode, video render, and encode are excluded. | Latest profiled run: Legacy 3,157 processed / 2 dropped, 351 presses, 16.42ms mean / 22.97ms P90; Segmented 3,116 processed / 43 dropped, 158 presses, 31.45ms mean / 42.17ms P90. Input-pause events: 229 / 789. |

The earlier `64.31ms mean / 90.07ms P90` report did not represent the fixed 14ms injected delay. Its wall-time boundary was the older replay instrumentation. The current measured replay explicitly times observe plus decide and excludes offline decode/encoding; it measures Segmented at 31.45 / 42.17ms. A repeat before final profiling measured 28.36 / 38.40ms and 185 presses, demonstrating host/runtime sensitivity near stale limits. This run-to-run spread is itself a feasibility concern; the latest result is used consistently for the final table.

The measured mode intentionally has provider-specific frame admission, because real computation is the variable being evaluated. It is not a fair isolation of pixel recognition quality; use fixed-delay A/B for that. Conversely, fixed-delay A/B says nothing about whether current compute can meet a live frame budget.

All actions are from `MockActuator`; there was no OS keyboard injection. Human key events are consulted after replay only. The 80ms key/time proximity metric is an auxiliary diagnostic (latest fixed run: 107/341 Legacy and 69/341 Segmented) and is not game hit rate, physical-note recall, or ground truth.

## P1 — where Legacy actions are lost in the fixed-delay A/B

`action_loss_attribution.csv` contains one row per each of the 348 Legacy key-downs. Cross-provider pairing uses same-frame geometry, lane/key, color, and a multi-frame vertical trajectory. Provider UIDs are used only to collect each provider's own tracks; they are not treated as cross-version identities. Each row includes source frame/time, source image evidence, pixel-mask/component evidence, both candidates and tracker state, Timing reason, Scheduler outcome, key-down/key-up, confidence, and an evidence-image path.

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
- Action evidence images: `output/analysis_lane_filter_v84_rework/action_loss_evidence_v4/`
- Full video and masks: `output/analysis_lane_filter_v84_rework/visual_verified/run_20261106T164049_800126Z/`

Original `output/recording/run_*` and `output/assist/run_*` inputs were read only. No Git commands were run.
