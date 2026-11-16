# V8.6 Offline Evaluation

## Latest iteration 0088 — Hold group extent and provenance repair

Iteration **0088** fixes a confirmed V85 adapter defect at Assist video frame 894/source frame 1086 (~14.9s): green Hold head component 26, group 25, previously reported `above=68, below=80` because the global Hold-mask union included the overlapping yellow body from group 47. The adapter now measures only the endpoint's exact same-frame group ROI and preserves endpoint ambiguity evidence; the source frame reports `above=68, below=0`. Segmentation thresholds/masks and all Tracker, Timing, Scheduler, and Live safety behavior remain unchanged.

The first implementation encoded each Hold row as Python run tuples and was rejected: full measured V85 P90 rose to 47.37ms, 104 frames dropped, 1,083 stale pauses. The final implementation stores the already-materialized local Boolean ROI by connection group, without copying a full frame. Full suite: **103 passed**. Full fixed 14ms A/B processed 3,159 frames and produced 342/294/259 Legacy/Segmented/V85 Mock presses with zero hard safety counters. Only one V85 Hold release changed versus the 0086 fixed baseline, moving 4ms earlier; presses did not change.

Two separate full measured-time repeats processed all 3,159 frames with no drops and 226 stale pauses for each provider. V85 compute P90 was 25.67/27.02ms versus 28.44/28.56ms in 0084 repeats; V85 Mock downs were 242/237 and are host-sensitive simulator outputs, not accuracy. Current action-loss attribution still has 122 `TRACK_ASSOCIATION_UNVERIFIED` rows. Physical-note labels remain UNKNOWN; V85 remains offline and Live remains Legacy. Detailed report and evidence: `output/analysis_v86_autoloop/iteration_0088_hold_group_extent_repair/iteration_report.md` and `iteration_manifest.json`. Paired source-indexed previews, masks, and clips are in that directory's `case_windows/`; matching prior windows are in `iteration_0087_current_case_windows/`.

## Latest provisional visual windows - iteration 0087

Rendered 26 source-indexed continuous windows from current 0086 attribution/Replay and the required Assist run. All 26 have a preview, clip, and timeline; the Assist previews map frame 294?294, 360?360, and 894?1086 (video frame?source frame). The ~4.9 s top-clipped green object remains unresolved; the ~6.0 s green ribbon is connected in the current mask but endpoint ownership and persistent identity remain unproven; the ~14.9 s overlap/flash case still has broad effect contamination and no certified Hold ownership. These are provisional observations only: physical-note truth UNKNOWN, no recall/hit score, and status **OFFLINE_NOT_PASSED**. Artifacts: `output/analysis_v86_autoloop/iteration_0087_current_case_windows/`.

## Latest exact-frame Tracker diagnostic - iteration 0086 (not performance eligible)

The complete fixed 14 ms compare replay processed all 3,159 indexed frames with a sparse Tracker trace at the 116 unique reference frames from iteration 0085. Its 342/294/259 Legacy/Segmented/V85 actions and six semantic outputs are byte-identical to 0084. The trace logged 166,890 association rows across the three providers; hard Mock safety counters stayed zero and OS input was disabled. Timing from this instrumented replay is not used as performance evidence.

The generic attribution still has 122 `TRACK_ASSOCIATION_UNVERIFIED` rows. A supplemental exact-frame join preserves that label while reporting the nearest spatial evidence: 65 components were non-action `effect_or_artifact`/`hold_body` observations; 35 accepted components were assigned to a different provider-local tracker UID; 20 were left `ambiguous_unassigned`; and 2 had no spatial component. Among the 55 accepted components, 41 have explicit association-edge evidence (13 lost global assignment competition, 17 ambiguous, 11 rejected by vertical/motion guards) and 14 have no edge for the trajectory-matched UID. These are processing facts, not proof that the spatial component is the same physical note as the Legacy action. No ID switch or physical-note miss is asserted.

The first all-frame trace attempt was stopped after about 10 minutes at approximately 6.5 GiB resident memory; sparse frame tracing completed at approximately 1.61 GiB observed resident memory. Latest measured matrix and full suite remain 0084; status remains **OFFLINE_NOT_PASSED**. See `output/analysis_v86_autoloop/iteration_0086_tracker_trace/`.

## Latest current-source attribution - iteration 0085 (analysis only)

The 0085 attribution pass reused the complete iteration 0084 fixed 14 ms Replay and the immutable indexed source run. It produced one row per 342 Legacy Mock downs using same-frame geometry, lane/key/color and motion; provider UIDs remain local. Categories: 123 same-key auxiliary V85 action pairings, 25 wrong-key pairings, 122 track-association-unverified, 18 not active at the exact reference frame, 16 Engine eligibility, 13 type pending, 9 association ambiguous, 4 timing insufficient observations, 3 Timing, 3 scheduled-action unresolved, 2 after-tracking unresolved, 2 Scheduler rejects, and 2 UNKNOWN. All 342 evidence paths resolve to 300 unique source-aligned multi-panel frames.

The 122 association-unverified rows are not force-labelled as a cause: exact-frame detection-to-track identity evidence is missing. The 80 ms action-event proximity is only a post-hoc aid, not a hit/recall score, and action totals cannot be interpreted as 83 distinct physical-note losses. Physical truth and calibration remain UNKNOWN; status remains **OFFLINE_NOT_PASSED**. Gzip CSV reading passed 20 focused tests; the last full suite was 100 passed in 0084 and was not repeated for this analysis-only reader change. Details: `output/analysis_v86_autoloop/iteration_0085_current_action_attribution/`.

## Latest measured microtrial - iteration 0084 (OFFLINE_NOT_PASSED)

The cyan tiled pass now prunes a proposal before density and HSV calculations when its final observed-pixel bbox is already covered by a known cyan Tap face under the existing 0.55 overlap rule. No morphology, ROI, threshold, mask, or scheduler behavior changed. On the 32 source frames selected in iteration 0083, role-mask hashes, ordered component hashes, and component counts all matched exactly. The full fixed 14ms replay preserved the 342/294/259 Legacy/Segmented/V85 Mock actions and all seven semantic artifacts from iteration 0075.

Two counterbalanced fresh-process measured repeats covered all three providers and all 3,159 frames with exact timestamp joins, no drops, and zero hard-safety failures. V85 P90 was 28.437/28.560ms. After subtracting the same-repeat Legacy control shift, the improvement against iteration 0082 is 0.682/0.342ms. Tap recovery mean/P90 improved 0.225/0.198ms and 0.454/0.513ms. This is a small compute saving, not improved visual recall. Performance-only output has no note attribution; measured Mock counts are not accuracy evidence. Physical labels remain UNKNOWN, stale pauses persist, Live remains Legacy, and status remains **OFFLINE_NOT_PASSED**. Full suite: **100 passed**. Evidence: `output/analysis_v86_autoloop/iteration_0084_cyan_duplicate_prefilter/`.

The delegated worker reported one accidental read-only `git diff`, contrary to the no-Git instruction; it reported no Git state change. The primary agent ran no Git commands.


## Latest analysis diagnostic - iteration 0083 Tap recovery profile (not an A/B)

Iteration 0083 selected 24 high `class_component_loop_ms` frames and 8 controls from the two iteration 0082 V85 measured profiles, then sequentially decoded all 3,159 indexed frames. Tap timers/counters were opt-in and `cProfile` was enabled; the resulting timings are diagnostic and not comparable as A/B performance evidence. Yellow mean/P90 was 0.652/1.088ms (150 proposals, 14 geometry-qualified, 13 accepted, 1 duplicate rejection); cyan_global was 0.955/1.548ms (642, 66, 64, 2); cyan_tiled was 2.016/2.900ms (744, 84, 39, 45). The tiled pass accepted 39 faces in this 32-frame sample, so its removal is unsupported. The full sequential cyan-mask census found 0/3,159 empty masks; pixel-count P50/P90/P99/max was 22,100/40,024/52,538/66,790. No useful empty-mask fast path is indicated for this recording. Duplicate efficiency remains unproven.

No source changes, tests, or full replay were performed. Keep iteration 0082 as latest full fixed/measured replay and latest full suite (99 passed); iteration 0083 is latest analysis only. Runtime candidate remains 0075. Physical labels remain UNKNOWN, Live remains Legacy, and status remains **OFFLINE_NOT_PASSED**. Artifacts: `output/analysis_v86_autoloop/iteration_0083_tap_recovery_profile/`.
## Latest current-source measured optimization - iteration 0081 (OFFLINE_NOT_PASSED)

Iteration 0081 skips output-only per-note decision-row dictionaries when `Engine.decide(record_decisions=False)` is requested. Decision branches, Note/identity updates, Scheduler operations, and scalar decision-row counting remain active. The default detailed mode keeps its existing rows and schema. This reduces instrumentation/serialization cost; it does not change perception or establish note accuracy.

The fixed 14ms replay processed all 3,159 indexed frames. Seven semantic outputs are byte-identical to iteration 0075: candidate trace, frame summary, Mock actions, safety audit, per-note decisions, posthoc reference actions, and replay manifest. Timing aggregates and stage profile are expected to differ.

Two counterbalanced fresh-process measured repeats covered baseline, Segmented, and V8.5 in performance-only mode. All six processed 3,159/3,159 frames with verified capture/acquisition timestamp joins; video decode/output encoding were excluded and no OS keyboard input occurred.

| Repeat | V8.5 decision-loop mean, 0079 to 0081 | Change | V8.5 processing P90, 0079 to 0081 | Change | Stale pauses / timeout disarms (0081) | Mock downs (0081) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 5.588 to 1.228ms | -78.0% | 36.643 to 31.114ms | -15.1% | 231 / 0 | 222 |
| 2 | 5.662 to 1.253ms | -77.9% | 36.486 to 31.101ms | -14.8% | 232 / 0 | 225 |

Both measured gates passed in each repeat. The matrix is host and wall-clock dependent: V8.5 scalar decision-row totals changed from 207,583/207,535 in 0079 to 207,275/207,275, and measured Mock downs varied. Performance-only runs omit per-note rows, so they cannot support note-level attribution. These results are not perception gains, physical-note accuracy, game hits, or recall evidence. Hard safety counters were zero. Physical-note labels remain UNKNOWN; stale pauses persist; V8.6 remains **OFFLINE_NOT_PASSED** and Live uses Legacy. Full suite: **98 passed**. Details and hashes: `output/analysis_v86_autoloop/iteration_0081_decision_row_opt/`.

## Latest current-source A/B - fixed and measured iteration 0075 (retained runtime candidate; OFFLINE_NOT_PASSED)

## Retained current-source change - iteration 0075

Iteration 0075 defers EarlyPixelProvider's exact full-frame connected-component labels until Hold recovery reaches a parent-region comparison. Raw identity trace still explicitly materializes labels. Full fixed 14ms action/decision/safety outputs match current-source baseline hashes; downs remain 342/294/259 and all safety counters are zero. Source hashes are pinned in `output/analysis_v86_autoloop/iteration_0075_lazy_labels/source_manifest.json`.

| Repeat | Provider | Processing P90 / P99 baseline → candidate (ms) | Capture-age P90 baseline → candidate (ms) | Drops baseline → candidate | Stale pauses baseline → candidate | Timeout disarms | Mock downs baseline → candidate |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | V8.5 | 38.66 / 46.02 → 37.90 / 45.08 | 59.51 → 57.75 | 20 → 18 | 448 → 369 | 0 → 0 | 205 → 211 |
| 2 | V8.5 | 38.28 / 46.40 → 37.76 / 45.55 | 58.88 → 57.64 | 19 → 16 | 393 → 361 | 1 → 1 | 206 → 214 |

V8.5 perception mean fell by 0.481/0.475ms; per-note decision work did not materially change. Legacy and Segmented controls moved less and inconsistently, supporting a narrow gain beyond host drift. Capture-age P90 still exceeds the source interval P90 of 41.22ms; 16–18 dropped frames, 361–369 stale pauses, and a timeout disarm remain. Mock action totals are diagnostic only. Full suite: **97 passed**; compileall passed. Keep this narrow change, but status remains **OFFLINE_NOT_PASSED**.

### Iteration 0074 unmodified current-source measured baseline

Iteration 0073 ran the normal full 14ms compare over 3,159 indexed frames using the current source. A read-only line trace counted label-region checks; frame-summary and Mock-action hashes matched iteration 0061 exactly. The trace run is not used for timing. Iteration 0074 then ran two counterbalanced fresh-process measured repeats on current source, with identical geometry/timing hashes, arm window 1–124s, birth boundary 176.75, per-processed-row timestamp verification, and video encoding excluded. Exact code hashes and run parameters are in `output/analysis_v86_autoloop/iteration_0074_current_source_baseline/source_manifest.json`.

| Provider | Fixed 14ms Mock downs | Measured processing P90 / P99 (repeat 1 / 2, ms) | Capture-age P90 / P99 (ms) | Drops | Stale pauses | Timeout disarms | Measured Mock downs |
|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy | 342 | 23.76 / 24.34; 31.41 / 31.06 | 42.69 / 43.52; 50.98 / 50.80 | 4 / 3 | 232 / 232 | 0 / 0 | 333 / 336 |
| V8.4 Segmented | 294 | 31.62 / 32.02; 37.58 / 38.11 | 50.66 / 50.88; 57.54 / 58.56 | 3 / 3 | 243 / 240 | 0 / 0 | 253 / 257 |
| V8.5 | 259 | 38.66 / 38.28; 46.02 / 46.40 | 59.51 / 58.88; 86.11 / 86.20 | 20 / 19 | 448 / 393 | 0 / 1 | 205 / 206 |

All measured processed rows have capture/acquired timestamp verification; every provider has zero illegal keys, duplicate press UIDs, unreleased presses, and key-up failures. V8.5 remains slower than both comparators, drops 19–20 frames, and has 393–448 stale pauses plus one timeout disarm in the second repeat. Its capture-age P90 exceeds the source frame interval P90 of 41.22ms. These action counts remain Mock output, not physical-note recall or game-hit rate. Status is **OFFLINE_NOT_PASSED**.

### Historical iteration 0061 artifact (source provenance incomplete)

Iteration 0061 remains useful historical context, but its manifest explicitly says invocation-time source hashes were **not** captured; its later recorded `current_source_sha256` for `src/lane_segmentation.py` differs from the current file. Do not treat that matrix as current-source timing. Its fixed-delay and measured-time modes used the same 3,159-row index, geometry hash `7462e360...db35a`, timing calibration hash `0f89988e...cc034`, 1–124s arm window, and birth boundary 176.75; measured timing excluded encoding.

| Provider | Fixed 14ms Mock downs | Measured P90 processing (repeat 1 / 2, ms) | Capture-age P90 (ms) | Drops | Stale pauses | Timeout disarms | Measured Mock downs |
|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy | 342 | 25.11 / 26.16 | 44.03 / 45.14 | 4 / 3 | 235 / 234 | 0 / 0 | 334 / 334 |
| V8.4 Segmented | 294 | 30.36 / 31.01 | 49.32 / 50.06 | 3 / 3 | 238 / 239 | 0 / 0 | 259 / 259 |
| V8.5 | 259 | 37.58 / 37.22 | 57.43 / 56.93 | 21 / 17 | 356 / 353 | 1 / 1 | 213 / 212 |

The fixed Replay has zero illegal Mock keys, duplicate press IDs, unreleased presses, and key-up failures. Its 80ms action proximity columns are auxiliary comparisons against recorded human key events and are not physical-note recall or game hit rate. Measured P90 V8.5 compute remains below the source capture-interval P90 of 41.22ms, but capture-age tails, 17–21 dropped frames, 353–356 stale pauses, and a stale-timeout disarm each run mean the practical freshness gate fails. The V8.5 action totals are not comparable to the fixed-delay totals as quality scores. Full artifacts: `output/analysis_v86_autoloop/iteration_0061/`.

### Performance experiments after iteration 0061

Iterations 0067–0074 were diagnostics or rejected optimization trials. Iteration 0075 is the first later performance change retained: it defers one full-frame CCL call until the Hold recovery path reaches a real parent-region comparison. Iteration 0073 counted zero such comparisons in the full fixed replay. The 0075 change preserved fixed-replay semantic outputs and yielded lower whole V8.5 processing P90 and stale pauses in both current-source measured repeats. Detailed reports and paired data are under each iteration directory.

The current retained source passes **97 tests** and compileall. The 0075 candidate also completed a full fixed replay and two-repeat measured matrix; those show a narrow performance gain but do not clear freshness gates. Physical-note ground truth remains UNKNOWN: the cross-session queue has 11 clips but no human-reviewed labels, so Tap/Hold recall, precision, Hold endpoint ownership accuracy, and game hit rate remain unevaluable. Status remains **OFFLINE_NOT_PASSED**; Live defaults to Legacy.

The cache cleanup script `tools/cleanup_generated_caches.bat` removed six Python/pytest cache directories on 2026-11-16 and returned exit code 0. Exact paths are recorded in `output/analysis_v86_autoloop/cache_cleanup_manifest_20261116.csv`; later Python execution can recreate caches.

Iteration 0048 corrected the segmented outer-edge cyan window omission: source frame 373 now has separate Tap-face pixel masks `[0,286,120,31]` and `[238,286,119,31]`, with no Tap pixels in the 984-pixel bridge. This is provisional source-mask evidence; the immediate-parent renderer hash is unavailable and a continuous before/after video was not produced.

Iteration 0049 changes only Engine key selection for exact ambiguity: equal historical coverage votes plus equal current-center distance now yield `ambiguous_key_coverage` and no Scheduler offer. At frame 1004, the prior arbitrary S action for note:623 is absent. This does not prove D or any other physical key was correct. The geometry is marked pending calibration, and two broad/effect-obscured candidates remain unverified.

| Provider | Fixed 14ms Mock downs | Measured mean/P90 repeat 1 (ms) | Measured mean/P90 repeat 2 (ms) | Measured drops | Stale pauses |
|---|---:|---:|---:|---:|---:|
| Legacy | 342 | 11.31 / 12.80 | 11.55 / 13.10 | 1 / 1 | 231 / 231 |
| Segmented | 293 | 13.01 / 15.56 | 13.21 / 15.61 | 1 / 1 | 230 / 230 |
| V8.5 | 259 | 15.42 / 18.72 | 15.57 / 18.87 | 9 / 9 | 231 / 230 |

All fixed safety counters and measured duplicate/illegal/unreleased/key-up-failure counters are zero. Fixed mode uses a synthetic 14ms scheduler clock and admits all 3,159 indexed rows; it does not set compute time to 14ms. Measured mode uses actual per-frame `Engine.observe + Engine.decide`, latest-frame-slot admission, fresh process per provider, two counterbalanced repeats, and excludes rendering/encoding. The source capture interval P90 is 41.22ms. Segmented remains slower than Legacy; V8.5 still drops 9 frames each repeat, and stale pauses remain near 230 for all providers. These results do not satisfy the measured freshness gate.

The Legacy-action attribution denominator is 342 in iteration 0049 because the shared Engine also abstains on one exact key tie in Legacy. Segmented categories are 174 same-key paired actions, 41 different-key actions, and 71 association-unverified; V8.5 categories are 123, 25, and 122. Compared with iteration 0048, differing-key diagnostics changed 45→41 and 27→25. These are heuristic cross-provider time/trajectory pairings and do not measure physical-note precision, recall, or game hit rate. Posthoc 80ms proximity likewise remains auxiliary only. Detailed rows are retained in `iteration_0049/action_attribution_segmented/action_loss_attribution.csv` and `action_attribution_v85/action_loss_attribution.csv`.

Tests: iteration 0049 targeted 8 passed and full suite 78 passed; iteration 0050 renderer tests 6 passed and full suite **84 passed**; compileall passed. All raw source data remained read-only; no OS keyboard injection, calibration edit, or Scheduler safety-bound change occurred. During later evidence-manifest maintenance, a bare `git` command was accidentally invoked; it printed usage help only, with no repository subcommand or state-changing operation. This violated the user's no-Git-command instruction.

Iteration 0050 adds a sequential 25-frame source/rectified/mask clip for frames 361–385. It verifies all frame/index joins and separates normalize/rectify/segmentation (16.26ms mean in this window) from panel composition/video encoding (5.50ms mean). These rendered-window measurements are not a production measured Replay. A provisional frame-1004 geometry audit estimates bottom UI keycap centers at x `[89,197.5,306,414.5,523,631.5]`; configured geometry lane centers at y=373 are `[109.1,209.4,309.8,410.1,510.4,610.7]`. Their offset trend suggests a possible alignment issue but UI keycap centers are not verified chart-lane ground truth; calibration remains unchanged. The clip is current-output evidence, not before/after. See `output/analysis_v86_autoloop/iteration_0050/iteration_report.md` and `source_window_361_385_corrected/manifest.json`.

Iteration 0051 adds a sequential four-panel edge-recovery comparison for frames 361–385. The pre-change side reconstructs the documented iteration-0047 outer-ROI behavior by omitting lane indices 0 and 5; it is **not an exact historical source snapshot**. At frame 373 it produces zero cyan edge Tap components, while the current segmenter produces two observed components at `[0,286,120,31]` and `[238,286,119,31]` with 3,176 and 3,103 pixels. The relevant bridge band has zero Tap pixels. All 25 source/index rows are verified. The archived frame-373 mask panel differs from the reconstructed parent's preview in 17,990/145,440 pixels, so the old build is not pixel-exactly reproduced. This is provisional mask evidence, not physical-note truth. The 25-frame segmentation timing was 7.16ms reconstructed / 7.62ms current; it is not a production benchmark. Runtime code did not change; the full Replay and 84-test result remain iterations 0049 and 0050. The incomplete first-run MP4 is listed in `iteration_0051/cleanup_manifest.json`; a preview-only manual cleanup BAT is available. See `output/analysis_v86_autoloop/iteration_0051/iteration_report.md` and `edge_recovery_ab_361_385_final/manifest.json`.

Overall status remains **OFFLINE_NOT_PASSED** because no independent physical-note labels exist, geometry is uncalibrated, action attribution has substantial unresolved identity/stale/unknown cases, and the exact immediate-parent source for the continuous comparison is unavailable. See `output/analysis_v86_autoloop/iteration_0049/iteration_report.md`, `iteration_0050/iteration_report.md`, and `iteration_0051/iteration_report.md`.

Iteration 0052 traces the two source-frame-373 edge components from exact Segmented component bboxes through adapter acceptance, confirmed provider-local Tracker IDs, the `deadline_freeze_window` timing state, Scheduler-pending state, and Mock down/up. The left bbox `[0,286,120,31]` follows `note:156` and produces D down/up; the right bbox `[238,286,119,31]` follows `note:155` and produces K down/up. Each has accepted/pressed/released events and no per-UID rejection. This proves pipeline traversal for those two replay traces only; physical-note identity and key correctness remain `UNKNOWN`. The lifecycle CSV and input hashes are in `output/analysis_v86_autoloop/iteration_0052/`; runtime code, full Replay, and the 84-test result were unchanged from iterations 0049/0050.

## Historical candidate evaluation - iteration 0037 (provisional; iteration 0036 broad rule rejected)

Full fixed 14ms Replay: **343/221/194** Legacy/Segmented/V85 Mock presses, 3,159 frames, all safety counters zero. A fresh-process full fixed baseline using the archived 0034 `early_perception.py` produced 343/221/186 under the same source run, geometry/timing hashes, arm window, and simulated delay. Candidate versus baseline posthoc same-key 80ms proximity matches were 59/57, and extra/wrong proximities were 135/129. These are not physical-note accuracy measures. A same-key ±80ms event comparison had 13 candidate additions and 5 losses; exact-index source review found note-like faces but could not uniquely attribute several crowded windows.

Iteration 0037 adds suppression for the exact 12×8 neutral component signature verified inside a complete Tap face. Its trace contains 333 suppressed rows total, but a same-frame+bbox baseline comparison shows 203 were already suppressed by the baseline bottom-bevel rule; the new 12×8 condition adds 130 candidate-only rows. The complete face at frame 186 now receives a confirmed Tracker identity and remains scheduled. All 58 tests passed at that iteration. The broader 0036 containment rule was rejected: 3,530 suppressions, full fixed V85 actions 208, increased extra/wrong posthoc actions, possible valid losses, and a small fixed-mode compute regression.

In separate full fixed processes on the current host, V85 compute_wall_ms mean/P90/P99 was 15.68/19.82/24.12ms for the 0034 source and 15.42/19.60/24.64ms for 0037. Legacy and Segmented also ran about 40% faster than their 0034 files, demonstrating a host/load shift; the small V85 delta is not evidence of a speedup.

Two latest-frame measured matrices for each source used fresh processes, the same indexed run/timestamps, geometry and timing hashes, 1?124s arm, and birth-zone y=176.75. V85 baseline/candidate repeat 1 compute P90/P99 was 18.22/23.21ms vs 17.91/22.29ms; repeat 2 was 18.10/21.79ms vs 18.04/22.38ms. Capture-age P90/P99 was 37.09/43.78ms vs 36.82/42.53ms and 37.03/42.60ms vs 36.98/42.57ms. Both versions dropped 5 frames in both repeats, had 229?231 stale pauses, and no stale-timeout disarm. Candidate Mock downs were 197/196 vs baseline 187/187; these are simulator outputs and not note accuracy. Compute changes are small and P99 is mixed; no reliable performance gain is claimed. Candidate measured-stage P90s were segmentation 9.25ms, class-component loop 5.30ms, Tracker association 3.08ms, and Engine decision 3.35ms. Rendering/encoding are outside these inference timers.

The iteration-0037 measured matrix provides a same-host feasibility comparison, but high stale-pause counts and unverified physical-note/action ownership remain. Physical-note GT is absent, so visual precision/recall and Hold ownership are NOT_EVALUABLE. Status: **OFFLINE_NOT_PASSED**.

## Stale-pause root cause (iteration 0038)

The 60ms Scheduler freshness bound remains unchanged. In the four same-host V85 measured runs, every stale-pause event occurs before the next indexed frame's acquired timestamp; pause-age median is about 60.9ms, and 149–150 of each run's 229–231 events are followed by that acquisition within 5ms. The source capture-to-acquire delay is P50/P90/P99 18.74/20.20/24.07ms and capture interval P50/P90/P99 is 38.98/41.22/47.21ms. Thus capture cadence plus acquisition latency crosses the existing safety limit while the prior frame is still the latest available input. This is not a V85 perception regression and does not justify changing the bound. At frame 1310.456s, an L action already scheduled by V85 was rejected late during this pause. Event-level rows are in `output/analysis_v86_autoloop/iteration_0038/stale_pause_boundary_events.csv`; no production source changed.

Physical-note ground truth and human-reviewed Tap/Hold/occlusion/negative labels remain absent. Visual precision/recall and Hold ownership are NOT_EVALUABLE. Status remains **OFFLINE_NOT_PASSED**. Details: `output/analysis_v86_autoloop/iteration_0036/iteration_report.md`, `iteration_0037/iteration_report.md`, and `iteration_0037/action_delta_review/findings.md`.

Date: 2026-11-15. Run: `output/recording/run_20261106T164049_800126Z` (3,159 indexed frames). All decisions were offline with `MockActuator`; human key events are post-hoc only. Original recording and assist folders were read-only.

## Replay fairness and the initial reported gap

The initial 72 Legacy / 18 Segmented press count and 46 / 232 stale-pause count used a Scheduler event history limited to 512 events. `updated` rows evicted early Legacy events. The complete callback stream instead showed 348 / 18 presses and 232 stale-pause events for both providers in that original fixed-delay run. The claimed 54 action difference is therefore not attributable to an algorithm stage; it was a truncated-log artifact. The corrected complete-stream action gap was 330.

For this evaluation, fixed-delay replay used the same source frames, `capture_timestamp` and `acquired_timestamp`, geometry, timing calibration, key map, Engine, Tracker, Timing, Scheduler, Arm window (1–124s), and 2ms scheduler polling for Legacy, V8.4 Segmented, and V8.5. It admitted all 3,159 frames and used `processed_at = acquired_at + 14ms`. **14ms is a synthetic logical delay**. The replay's separate host-loop timing is not the synthetic delay and includes simulator work; it is not measured-time feasibility.

Measured-time replay advanced processing by actual `Engine.observe + Engine.decide` time and modeled a single latest-frame slot. Frames that arrived while inference ran could overwrite the pending frame. Decode, rendering, file I/O, and encoding are excluded from inference time. The measured-mode providers do not process identical admitted-frame sets by design; this measures feasibility, not isolated perception quality. Indexed capture intervals were mean 39.33ms, P10 37.65ms, P50 38.98ms, P90 41.22ms, P99 47.19ms, min 33.57ms, max 61.17ms.

## Full fixed-delay causal Mock A/B

| Provider | Frames | Mock downs | Host loop mean / P90 | Matched post-hoc human key/time events | Wrong/extra Mock downs | Safety violations |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 3,159 | 343 | 23.52 / 32.83ms | 105 / 341 | 238 | 0 |
| V8.4 Segmented | 3,159 | 213 | 30.96 / 43.08ms | 60 / 341 | 153 | 0 |
| V8.5 | 3,159 | 199 | 38.66 / 51.76ms | 60 / 341 | 139 | 0 |

The host-loop column is not the fixed 14ms clock. The human-event proximity count uses 80ms and matching key as a post-hoc auxiliary measure only; it is neither game hit rate nor physical-note recall. Every Mock down had one key-up, with zero duplicate UID, key-up failure, unreleased UID, or illegal key.

## Per-Legacy-action loss attribution

The fresh CSV has one row per 343 Legacy actions. Pairing uses source-frame geometry, lane/key, color, and multi-frame motion trajectory; provider UIDs are not treated as cross-version physical identity.

| Last observed V8.5 outcome | Count | Interpretation |
|---|---:|---|
| Same-key V8.5 Mock action | 116 | Paired simulated action; physical-note truth unknown. |
| V8.5 Mock action on a different key | 29 | Wrong-key simulated action; not a segmentation miss. |
| Engine Tap visibility gate | 85 | Candidate reached the terminal Tap visibility gate. |
| Engine type pending | 40 | Type remained unresolved at the Engine gate. |
| Engine eligibility gate | 49 | Engine rejected for eligibility/motion/origin reasons. |
| Timing gate | 8 | Timing rejected the trajectory. |
| Timing insufficient observations | 11 | Too few accepted Timing observations. |
| Pixel role UNKNOWN | 5 | Real pixels were retained as unknown-role evidence. |
| **Total** | **343** | Mutually exclusive attribution outcomes. |

The small role-UNKNOWN count does not prove all other paired tracks are physical notes: attribution is cross-provider trajectory evidence, not an independently reviewed label set. Scheduler rejection is not a material bucket in this replay. Raw report: `output/analysis_v86_autoloop/final/action_loss_attribution.csv`.

## Measured-time A/B, two full repeats with diagnostic profiling disabled

| Provider | Repeat | Processed / dropped | Compute mean / P90 | Mock downs | Stale-capture pause events | Disarms |
|---|---:|---:|---:|---:|---:|---:|
| Legacy | 1 | 3,156 / 3 | 17.01 / 23.15ms | 341 | 229 | 0 |
| Legacy | 2 | 3,156 / 3 | 17.21 / 23.56ms | 344 | 231 | 0 |
| V8.4 Segmented | 1 | 3,129 / 30 | 29.47 / 39.50ms | 108 | 279 | 1 |
| V8.4 Segmented | 2 | 3,135 / 24 | 28.53 / 38.61ms | 111 | 236 | 1 |
| V8.5 sparse-assignment candidate | 1 | 3,101 / 58 | 32.43 / 43.53ms | 44 | 114 | 1 |
| V8.5 sparse-assignment candidate | 2 | 3,102 / 57 | 31.88 / 43.12ms | 42 | 83 | 1 |

Each run decoded all 3,159 source frames; processing/drop counts vary under the measured latest-frame slot. The capture interval P90 is 41.22ms. V8.5 P90 remained above that interval in both repeats and it dropped 58/57 frames versus Legacy's three per run. V8.5 stale-capture pause events were 114/83, with one stale-timeout disarm in each run. All six provider/repeat results had zero illegal keys, duplicate press UIDs, missing key-ups, or key-up failures. The two current repeats are close for V8.5 (P90 43.53/43.12ms), but their P90 remains worse than Legacy and the candidate is not live-feasible.

The earlier `measured_repeat1/2` results in `iteration_0001` enabled extra per-note timers for V8.5 alone. They are retained as historical profiles, not fair latency A/Bs. Per-note timing is now opt-in (`--profile-v85-decision-notes`); official full runs in `iteration_0003` and `iteration_0005` disable it for every provider. The current runs are from a faster host session than `iteration_0003`, so use the within-run provider comparisons and retain both paired repeats. Current reports and variance data are under `output/analysis_v86_autoloop/iteration_0005/`.

The 80ms key/time proximity matches were 17/17 for V8.5 and 105/106 for Legacy. These compare post-hoc human key events, not physical notes or gameplay hits, and cannot establish note recall.

## Per-stage V8.5 inference latency

Values are P50 / P90 / P99 milliseconds for the two unprofiled official measured runs. Stage measurements are nested where noted and must not be summed into total processing time.

| Stage | Repeat 1 | Repeat 2 |
|---|---:|---:|
| Normalize | 1.004 / 1.227 / 1.475 | 0.996 / 1.267 / 1.541 |
| Rectify | 0.974 / 1.210 / 1.430 | 0.969 / 1.236 / 1.442 |
| HSV conversion | 0.549 / 0.660 / 0.854 | 0.564 / 0.724 / 0.967 |
| Gray conversion | 0.110 / 0.204 / 0.255 | 0.116 / 0.216 / 0.281 |
| Connected components | 2.523 / 3.166 / 3.772 | 2.313 / 2.899 / 3.522 |
| Mask and component classification | 11.083 / 17.147 / 22.174 | 10.982 / 17.509 / 22.775 |
| Tap ROI recovery | 1.894 / 3.179 / 4.171 | 1.795 / 3.011 / 4.053 |
| Detection adapter | 1.488 / 2.220 / 3.084 | 1.418 / 2.266 / 3.215 |
| Tracker association | 3.710 / 7.889 / 13.061 | 3.589 / 7.968 / 12.826 |
| Engine decision | 6.273 / 8.677 / 10.949 | 6.093 / 8.642 / 10.963 |
| Observe + decide total | 32.053 / 43.532 / 53.207 | 31.249 / 43.119 / 52.679 |

The new stats-first ROI/Hold-buffer change lowered mask/component P90 from the prior unprofiled pair's 18.70/20.11ms to 17.15/17.51ms. The new whole V8.5 processing P90 is 43.53/43.12ms, so this local reduction does not bring inference under the 41.22ms capture interval or eliminate drops. Data-conversion timing has no V8.5 sample (`data_conversion_ms` is empty); separately exposed detection-adapter timing is reported instead. Video decode and review rendering/encoding remain outside inference timing; encoding was not independently micro-profiled in this iteration.

The additional segmentation breakdown is nested and not additive: class component-loop P90 is 15.05/14.70ms, including class connected-components work; effect-mask, effect connected-components, and effect-component-loop P90 are 2.14/2.18ms, 0.80/0.80ms, and 1.09/1.06ms. A separate 1,200-frame before/after diagnostic showed mask/component P90 18.33→15.97ms and class-loop P90 16.54→14.22ms. It supports the local allocation optimization but is not a standalone performance acceptance run.

### Instrumented tail-latency diagnosis (not an A/B result)

To localize rare 100–300ms maxima, two diagnostic-only V8.5 measured replays processed the same source prefix (2,700 decoded-frame limit) with per-note row-build, action-logic, Scheduler-snapshot, and finalize timers. These profiling runs are not comparable performance A/Bs: the second run itself ran substantially slower across ordinary frames, and latest-frame admission consequently processed 2,651 frames / dropped 49 versus 2,694 / dropped 6 in the first run.

The first run had total processing P50/P90/P99 of 17.23/22.23/29.81ms. Its maxima were split across unrelated code regions: segmentation took 143.98ms at frame 2,644, an individual note iteration took 107.18ms in the Engine loop at frame 2,146 (107.16ms in the then-combined finalization section), and segmentation took 102.66ms at frame 1,801. In the second run, total processing P50/P90/P99 shifted to 32.72/43.87/52.54ms. Its longest decision was 152.93ms at frame 2,169, with 144.96ms inside a single `Scheduler.snapshot()` call; another snapshot took 93.08ms at frame 1,505. A separate 60.19ms row-build sample occurred at frame 957, while segmentation maxima of 139.37 and 111.51ms occurred at frames 1,815 and 1,210. Normal decision P90/P99 were 8.82/10.86ms in that slower run.

The spikes move between segmentation, row construction, and a tiny in-memory snapshot, while the second run's ordinary-frame latency roughly doubled across the pipeline. The replay Scheduler has no background thread and the same frame locations did not reproduce the same slow stage. This points to host/runtime scheduling or load as a likely contributor, but does not prove the cause. No single stable algorithmic hotspot is established by these tail samples, so no code path was removed or weakened based on them. Keep these maxima in measured feasibility results; do not replace them with synthetic fixed latency. Full frame-level traces are under `output/analysis_v86_autoloop/iteration_0001/tracker_sparse/decision_subphase_profile_v85/` and `decision_subphase_profile_v2/`.

## Visual and identity review

`output/analysis_v86_autoloop/final/review_queue.csv` selects source-aligned continuous windows for each available terminal attribution class, the slowest measured frame, the first latest-frame gap, and Assist frames 294, 360, 894. The Assist frame 894 target maps to `source_frame=1086`, and both source and indexed frame values are retained. The source and index are hashed in `review_manifest.json`. Clips include source, rectified view, current-pixel mask, V8.5 overlay, and frame/timestamp timeline.

The V8.4/V8.5 before/after comparison video and masks at frames 294/360/894 are preserved at `output/analysis_v85_early_identity/v84_v85_visual_comparison/`. The 14.9s multi-Hold/Tap mask still contains substantial effect/background contamination; separate Hold ownership is not proven. All current review cases are `PROVISIONAL_VISUAL_AUDIT`, with physical-note labels `UNKNOWN`. No human-reviewed Tap/Hold/effect/occlusion/negative set exists, so note recall, false-positive rate, type confusion, IDF1, false merge, and Hold head/tail owner accuracy are `NOT_EVALUABLE`.

The current Tracker was rescanned over all 20 complete local indexed Runs: 98,669 indexed/decoded frames, 106,978 candidate tracks, and 24,840 automatically confirmed tracks. The four target runs produced 13,128 candidates / 2,966 confirmed. Across all 20, there were 65 yellow-Hold-hinted candidates and seven automatically confirmed; the two primary recording Runs each had one candidate and zero confirmations. Neutral pending hints remain common. These counts are model-generated tracks only and do not establish physical-note count, recall, or precision. Per-run indexed/decoded coverage is in `output/analysis_v86_autoloop/final/candidate_scan_frame_coverage.csv`; SHA-256 hashes for all 20 source video/index pairs are in `candidate_scan_source_hashes.csv`.

## Bounded optimization, tests, cleanup, and decision

The Tracker still solves each connected component of hard-gated feasible association edges independently with the same exact assignment solver and unmatched cost. The new segmentation optimization first applies cheap component-stat gates before allocating tight pixel ROIs, and only creates Hold head/tail scratch buffers for Hold bodies. No classification threshold changed. Full fixed replay `mock_actions.csv`, `physical_note_decisions.csv`, and `candidate_trace.csv` are byte-identical to the pre-optimization run. Six actual source frames (green Hold, cyan Tap, near-hit effect, gray panel, yellow Hold, simultaneous Holds) produced all 48 role masks pixel-identical to the pre-optimization masks. Hashes and frame references are in `output/analysis_v86_autoloop/iteration_0005/mask_equivalence_audit.csv`.

Validation: `python -B -m pytest -q -p no:cacheprovider` → **32 passed**. In-memory UTF-8-SIG syntax compilation → **37 Python files compiled**. Autoloop help, case-window help, and quick/full dry-run plans passed; dry-run selected 20 complete local runs and wrote no files. Full replay output and current case artifacts are referenced by `output/analysis_v86_autoloop/final/evidence_manifest.json` rather than duplicated.

Cleanup re-audit found seven manifest candidates already absent and three Python bytecode caches still present. The exact-path deletion attempts were blocked by PowerShell policy. The BAT preview was rerun and listed only those three cache paths as `WOULD_REMOVE`; no deletion was executed. `tools/cleanup_v85_candidates.bat` previews the ten manifest paths by default and requires `--execute` plus an interactive `Y`. All raw recording/assist, fixtures, calibration, and canonical baseline evidence were retained; the latest retry is recorded in `docs/V85_CLEANUP_MANIFEST.md`.

**Result: `OFFLINE_NOT_PASSED`.** Keep Live on Legacy. The segmentation allocation change lowers mask/component P90 by about 8–13% across the paired full-run measurements without changing fixed replay actions. Whole V8.5 P90 remains 43.53/43.12ms versus a 41.22ms source interval P90, with 58/57 drops and one stale-timeout disarm per repeat. Physical-note quality remains unverified, and wrong-key actions, type pending, Tap visibility gates, multi-Hold mask ambiguity, latency tails, stale disarms, and absent independent labels remain acceptance blockers.

## Continuation through iteration 0010 (2026-11-15)

The sections above document iterations 0000–0005 and are historical. The current code/evidence is iteration 0010. Fixed and measured runs remain separate: fixed replay uses all 3,159 indexed frames and a synthetic 14ms delay; measured mode advances on observed `observe + decide` wall time and replaces pending frames in a latest-frame slot. Both use the same source/index, Arm window 1–124s, geometry, timing calibration, key map, Engine, Tracker, Timing, and Scheduler within their own comparison. Capture/acquired timestamps are indexed; no future frames or human events are decision inputs. Human-key comparisons remain post-hoc only.

### Current fixed-delay replay

| Provider | Mock downs | 80ms human-key proximity | Other/extra by that diagnostic | Host-loop P90* |
|---|---:|---:|---:|---:|
| Legacy | 343 | 105 | 238 | 30.52ms |
| V8.4 Segmented | 221 | 66 | 155 | 38.16ms |
| V8.5 current | 179 | 52 | 127 | 51.22ms |

*The last column is fixed-replay host-loop profiling, not the 14ms simulation delay or a measured-time feasibility result. Safety audit: 0 illegal keys, duplicate press UIDs, key-up failures, presses without release, or duplicate down for one UID. Human-key proximity does not establish physical-note recall or game hits. Full files are under `output/analysis_v86_autoloop/iteration_0010/fixed_full/run_20261106T164049_800126Z/`.

The current source-frame attribution pairs the 343 Legacy action episodes to V8.5 by same-frame geometry and multi-frame physical trajectories. Cross-provider UIDs are not used as physical identity. The terminal-stage counts are:

| V8.5 terminal evidence | Count |
|---|---:|
| Same-key V8.5 Mock action present | 99 |
| V8.5 Mock action on a different key | 17 |
| Engine Tap visibility gate | 75 |
| Engine type pending | 61 |
| Engine eligibility gate | 42 |
| Candidate not active at the exact reference frame | 20 |
| Segmentation role UNKNOWN | 2 |
| Timing gate | 10 |
| Timing insufficient observations | 15 |
| Scheduler rejection | 2 |
| **Total Legacy actions categorized** | **343** |

This is algorithm-stage attribution, not physical-note ground truth. The 20 tracks absent at the exact frame have a recorded last observation/state; they are not forced into an earlier assumed root cause. The CSV, per-case images, hashes, and source alignment manifest are in `output/analysis_v86_autoloop/iteration_0010/action_attribution/`.

### Current measured-time repeats

| Repeat / provider | Mean / P90 compute | Processed / dropped of 3,159 | Mock downs | 80ms human-key proximity | Other/extra by that diagnostic |
|---|---:|---:|---:|---:|---:|
| 1 Legacy | 17.46 / 24.81ms | 3,156 / 3 | 337 | 103 | 234 |
| 1 V8.4 Segmented | 25.79 / 33.18ms | 3,145 / 14 | 189 | 56 | 133 |
| 1 V8.5 | 24.68 / 35.59ms | 3,138 / 21 | 38 | 18 | 20 |
| 2 Legacy | 18.87 / 25.15ms | 3,155 / 4 | 331 | 103 | 228 |
| 2 V8.4 Segmented | 26.04 / 33.55ms | 3,149 / 10 | 188 | 54 | 134 |
| 2 V8.5 | 33.24 / 44.51ms | 3,085 / 74 | 35 | 14 | 21 |

The indexed capture-interval P90 is 41.22ms. V8.5 repeat 1 is below it; repeat 2 is above it and drops 74 frames. The two current repeats do not establish reproducible feasibility. On 3,065 common V8.5 frames, repeat 2 was slower by a median 8.02ms; segmentation, class-component, Tracker, and Engine decision stages all shifted upward. The measurement spread is not explained by a single fixed bottleneck and remains a host/runtime or workload variance question. Each measured repeat had one stale-timeout disarm. Stale pause events were 95 and 89 for V8.5; these are event counts, not unique pause episodes.

Per-stage P50 / P90 / P99 milliseconds for current V8.5 (repeat 1 / repeat 2): normalize 0.71/0.95/1.27 / 0.93/1.13/1.40; rectify 0.67/1.00/1.30 / 0.93/1.16/1.38; HSV 0.24/0.55/0.74 / 0.53/0.65/0.85; gray 0.07/0.14/0.21 / 0.11/0.18/0.25; connected components 1.76/2.27/2.76 / 2.16/2.66/3.22; class-component loop 5.99/10.91/17.06 / 8.54/14.08/19.02; Tap recovery 2.34/3.63/5.07 / 2.95/4.38/5.72; detection adapter 1.10/1.67/2.32 / 1.45/2.22/2.98; Tracker 3.19/6.56/9.57 / 4.85/9.30/15.22; and `observe + decide` 22.32/35.59/45.61 / 32.85/44.51/53.08. These stages are nested and must not be summed. Decode, visualization, and video encoding are outside inference time; encoding itself was not separately micro-profiled. Stage traces are under each repeat's `stage_profile_by_frame.csv`.

### Pixel and adapter regression work

Source frame 186 contains an observed cyan panel at rectified bbox `(32,282,91,27)`. The current lane-centered ROI recovery returns 1,591 observed cyan pixels in that panel and zero Tap pixels in the clipped judgment-glow ROI `(292:360,311:324)`. The panel passes through `EarlyPixelProvider` as `kind=tap`, `semantic_candidate=tap`, `full_face=True`; a 7px cyan panel stays UNKNOWN/pending, and an observed 3px neutral rail no longer claims full-face evidence. No old `Perception.detect()` result was used as segmentation truth. Thirteen focused segmentation/adapter tests passed and the full source-only suite passed **41 tests**. These are pixel/adapter regressions, not human-reviewed physical-note labels.

Iteration 0007's sliding ROI implementation had Tap recovery P90 10.21ms and action/proximity diagnostics worsened. Iteration 0009 replaced sliding windows with one lane-centered bounded ROI per lane and batched morphology/connected-component work. Its 600-frame fixed prefix preserved press counts and 80ms proximity exactly while Tap recovery P90 fell from 6.39ms to 3.36ms. On the full current run, Tap recovery P90 is 5.03ms fixed and 3.63/4.38ms measured. This local optimization does not resolve measured variance or prove note quality.

Current sequentially decoded source-indexed case videos, masks, and timelines are under `output/analysis_v86_autoloop/iteration_0010/case_windows/`. The 4.9s, 6.0s, and 14.9s Assist windows are included. Every case remains `PROVISIONAL_VISUAL_AUDIT`; note identity, physical truth, and Hold ownership are `UNKNOWN` pending human review. No Active path was enabled, and Scheduler safety bounds were unchanged.

The current source/baseline/action outputs and both measured repeats are referenced in `output/analysis_v86_autoloop/iteration_0010/`; its command/config/source/output hashes are in `iteration_0010/iteration_manifest.json`. Iteration history through 0010 is in `iteration_history.csv` and `iteration_history.md`. Earlier full runs remain preserved and are not overwritten.

Cleanup re-audit after the latest retry confirms the three Python cache directories are still present (316,387 / 44,366 / 215,507 bytes). A BAT path-test bug had reported them absent; after correction, preview mode reports all three `WOULD_REMOVE`. Direct PowerShell deletion remains policy-blocked; BAT execute mode was not run. Raw recording, assist, fixture, calibration, and canonical replay data remain untouched.

### Iteration 0012 — attribution provenance correction

The iteration-0010 fixed replay itself was not rerun. Its 343 Legacy actions were re-attributed using an exact same-provider, same-frame `tracker_uid` to component trace link. A spatially overlapping detector component with no assigned tracker identity is now shown separately and cannot be presented as the matched track's segmentation evidence. A stale decision row without a fresh exact-frame observation is classified as `TRACK_ASSOCIATION_UNVERIFIED`, with low confidence, instead of being counted as a proven Engine/Timing loss. Exact score ties remain unmatched.

Corrected root-stage counts across the 343 Legacy actions are: 99 same-key V8.5 actions; 17 wrong-key actions; 158 tracker-association-unverified; 20 track-not-active at the reference frame; 19 Engine type-pending; 15 Engine eligibility; 8 Timing insufficient-observation; 3 Timing gate; 2 Scheduler rejection; and 2 UNKNOWN. Of 343 rows, 104 have exact current-frame tracker-to-component evidence; 234 have a nearby spatial detection but no verified assignment. These are attribution counts for provider outputs, not physical-note recall. `physical_note_id` remains UNKNOWN.

Source evidence at video frame 177 illustrates the correction: the replay emits an accepted Tap component at the Legacy note's spatial location, but its tracker-input row has no `tracker_uid`; the prior matched track's last observation is frame 173. Thus the replay shows an association gap and a downstream `confirmed_tap_observation_lost` reason, but does not prove that the historical Legacy action and the unassigned Tap component are the same physical note. The frame-97 sample likewise remains unresolved. Updated attribution CSV, summary, and 25 source-aligned case windows are under `output/analysis_v86_autoloop/iteration_0011/`; compact current copies are under `output/analysis_v86_autoloop/final/`.

The full suite at attribution revision 0012 passed **45 tests** (`python -B -m pytest -q -p no:cacheprovider`). This was an analysis-only change; fixed action counts, two measured-time repeats, segmentation, Tracker, Timing, Scheduler, calibration, and Live defaults were unchanged. Status remained `OFFLINE_NOT_PASSED`.

## Tracker association trace follow-up (iteration 0013)

The current canonical fixed-delay counts are Legacy / V8.4 Segmented / V8.5 **343 / 221 / 179**. An opt-in trace now records, on selected frames only, each tracker-input component's final disposition and every cap-to-component edge's hard-gate rejection reason, feasible cost, ambiguity, assignment loss, or selected status. No association threshold or decision branch was changed. The diagnostic full replay's action, physical-decision, and candidate-trace files are SHA-identical to the iteration-0010 replay. Its wall-time statistics are not usable as a performance result because tracing adds diagnostic work.

Trace windows cover 1,752 of 3,159 frames, selected from the 691 Legacy-action cases plus three frames on either side. A spatially filtered trace and per-case refinement table report the following within the prior low-confidence association class:

| Candidate provider | Prior unverified rows | Stage evidence observed in the selected spatial region |
|---|---:|---|
| V8.5 | 158 | 103 non-action effect/body regions; 17 exact-component edges lost global assignment; 19 ambiguous; 10 exact-component hard-gate rejects; 6 exact components matched an existing cap; 1 target track outside the 240ms association window; 2 nearby component links still unverified. |
| V8.4 Segmented | 86 | 73 spatial components dropped before Tracker input; 6 exact components matched an existing cap; 4 ambiguous; 1 target track outside the association window; 1 hard-gate reject; 1 unresolved. |

These numbers describe which program stage handled spatially chosen candidates and do not identify physical notes. `TRACK_ASSOCIATION_UNVERIFIED` remains a valid physical-cause caveat where no independent label exists. In particular, a component assigned to another local note UID may be a split identity or a different visual object; the ID alone cannot decide. The full raw trace and evidence are in `output/analysis_v86_autoloop/iteration_0013/`; the compact 691-case table is `final/action_loss_tracker_refinement.csv`.

V8.4 frame 97 is now concretely traced at the component-to-detector boundary: component 83 is cyan, bbox `(0,250,209,73)`, area 4,023, role `unknown`, and adapter result `dropped_semantic_gate`. The component is broad and vertically extended in a busy hit-effect region, so keeping it non-executable is consistent with the safety rule; whether it contains the Legacy physical note remains UNKNOWN. This identifies a segmentation/adapter evidence path but does not justify promoting the component to Tap or Hold.

`python -B -m pytest -q -p no:cacheprovider` now passes **47 tests**. This diagnostic instrumentation does not resolve physical-note recall, Tap/Hold confusion, measured-time variance, or Hold endpoint ownership. Offline status remains `OFFLINE_NOT_PASSED`.

## Persistent identity and alternate action follow-up (iteration 0014)

A second full-source V8.5 fixed replay traced the 29 prior unverified cases whose spatial component was an accepted `tap_face`, plus/minus three frames. The trace now includes each competing cap's confirmation, observation count, last-seen time, birth origin, votes, and edge cost. This is diagnostic-only; no association or ambiguity threshold changed.

At video frame 177, the cyan Tap component 70 `(234,284,101,33)` was feasible for two confirmed local tracks: `note:100` (51 observations, cost 0.10134) and `note:137` (27 observations, cost 0.14825). Their cost gap, 0.04690, is below the existing 0.12 ambiguity margin, so the Tracker marked the component `ambiguous_unassigned`. Both tracks had the same last-seen timestamp. This is a concrete association-stage result, but the image does not establish whether these are two overlapping physical notes or duplicate identities, so choosing either UID would be unsafe without further evidence.

The fixed replay also contains a V8.5 `note:137` Mock K press at 1266.7102138s and a Legacy `note:32` Mock K press at 1266.7222889s, 12.08ms apart. Across all previous unverified attribution rows, 29/158 V8.5 cases had a same-key V8.5 press within 80ms of the Legacy press, and 53/158 had any-key V8.5 presses in that interval. For V8.4, the corresponding counts were 0/86 and 13/86. This is posthoc cross-provider action-time proximity only; it does not identify the physical note or establish a game hit or note recall.

Artifacts are `output/analysis_v86_autoloop/iteration_0014/iteration_manifest.json`, `targeted_tracker_trace/.../tracker_association_trace.csv`, and `cross_provider_action_time_proximity_diagnostic.csv`. This follow-up clarifies that some UID-level action gaps coincide with an alternate same-key action, but cannot justify changing the ambiguity policy or claiming improved note recall. Offline status remains `OFFLINE_NOT_PASSED`.

The stage-split auxiliary table is `cross_provider_action_time_by_stage.csv`: among V8.5 association-unverified cases, same-key proximity appears in 6/16 exact-track ambiguities, 3/3 other component ambiguities, 4/17 assignment losses, 2/8 hard-gate rejects, 2/6 existing-cap assignments, and 12/103 non-action effect/body regions. These overlaps show why “no action on the geometrically paired UID” cannot be equated to “no nearby action”; each row still needs independent physical-note truth.

## Narrow neutral-bevel adapter correction (iteration 0017)

Frame 173 of the source recording has a cyan Tap-face component `(231,259,103,28)` and a separate neutral 3px rail `(240,284,83,3)` at its lower edge. The pixel segmenter labeled the rail UNKNOWN/partial-neutral, but V8.5 converted it into a trackable `plate_fragment`; the Tracker then updated a second Tap identity from it while the full Tap face updated another. The adapter now retains the segmenter pixels for inspection but withholds a partial-neutral rail from Tracker input only when a same-frame complete Tap face covers at least 90% of its width and the rail lies at that face's bottom bevel. This does not use `Perception.detect()` as pixel truth and does not relax timing, association, or scheduler gates.

The same-process full fixed replay used the same 3,159 indexed frames, 14ms simulated delay, arm window, calibration, geometry and shared Engine/Tracker/Timing/Scheduler. It produced **343 / 221 / 186** Legacy / Segmented / V8.5 Mock downs, compared with **343 / 221 / 179** in the previous source snapshot. Per-provider Legacy and Segmented action/decision rows were identical to baseline. V8.5 same-key 80ms proximity changed **52→57**, while extra/wrong-key proximity changed **127→129**; these are not physical-note recall or gameplay outcomes. V8.5 `compute_wall_ms` P50/P90/P99 under the three-provider run was **39.65/53.93/69.11ms**. In the isolated fixed V8.5 run the corresponding values were **31.53/43.15/54.55ms**; stage P90s there were segmentation 22.76ms, Tracker association 9.01ms, rectification 1.10ms and HSV conversion 0.62ms. The different host/load results are not a paired performance experiment and do not prove speedup. All **50 tests passed**. The frame-173 trace, full replay, and hashes are recorded under `output/analysis_v86_autoloop/iteration_0017/`; offline status remains `OFFLINE_NOT_PASSED`.

The current measured-time three-provider run decoded 3,159 frames and processed 3,156 / 3,148 / 3,073 Legacy / Segmented / V8.5 frames, dropping 3 / 11 / 86. Processing P50/P90/P99 was **16.39/24.22/32.00ms**, **26.63/34.66/42.23ms**, and **33.38/44.76/54.88ms**. V8.5 capture-age P90/P99 was **80.92/101.59ms**. Stale-capture pause events were **230 / 272 / 92**; V8.5 had one `stale_timeout` disarm. Mock downs were **338 / 184 / 38**, and 80ms same-key proximity was **104 / 55 / 18**. This single current-source run misses freshness and action-quality requirements; earlier two measured repeats used a different source snapshot and are not a paired comparison. No Active recommendation follows.

## Current-source follow-up (iterations 0021–0024)

The current fixed 14ms same-source Compare still uses all 3,159 indexed frames, the 1–124s arm window and shared Legacy / Segmented / V8.5 Engine, Tracker, Timing and Scheduler. Its **343/221/186** action totals and per-provider action, decision and candidate rows are identical before and after the performance-only Tracker/effect-region changes. The Tracker hot path skips only pairs already beyond the existing `center_gap > .28` rejection. The segmentation code limits class connected-components to its exact nonzero y-domain and computes the existing near-hit effect/Sobel mask only within the hit-line band plus a one-row border. Neither change alters semantic gates. Exact source mask SHA-256s and component lists match on recording frames 97/173 and Assist frames 294/360/894.

Two current-source measured-time runs, with one fixed source and unchanged latest-frame admission policy, yielded:

| Provider | Run | Compute mean/P90 (ms) | Processed / dropped | Capture-age P90 (ms) | Stale pauses / stale timeout | Mock downs | Same-key 80ms proximity* |
|---|---:|---:|---:|---:|---:|---:|---:|
| Legacy | 1 | 16.34 / 22.04 | 3156 / 3 | 41.20 | 232 / 0 | 341 | 106 |
| Legacy | 2 | 16.34 / 21.81 | 3155 / 4 | 40.95 | 231 / 0 | 343 | 105 |
| V8.4 Segmented | 1 | 25.15 / 32.51 | 3150 / 9 | 51.53 | 255 / 0 | 193 | 55 |
| V8.4 Segmented | 2 | 25.53 / 33.02 | 3149 / 10 | 52.10 | 249 / 0 | 189 | 53 |
| V8.5 | 1 | 30.51 / 40.23 | 3124 / 35 | 62.39 | 64 / 1 | 44 | 19 |
| V8.5 | 2 | 31.58 / 41.58 | 3113 / 46 | 66.12 | 66 / 1 | 45 | 19 |

Against the immediately preceding two-repeat Tracker-only version, the V8.5 processing P90 improved from **43.04/42.00ms** to **40.23/41.58ms**; drops changed from **57/44** to **35/46**, stale pauses from **81/80** to **64/66**, and stale disarm remained once per run. The per-run effect-mask P90 fell from 2.16/2.09ms to 0.58/0.63ms, while segmentation P90 fell from 24.55/23.52ms to 21.80/22.87ms. This is a repeatable local cost reduction, not a full freshness pass: capture-age P90 remains above 60ms, one processing P90 is above the source interval P90 of 41.224ms, and P99 processing is 48.45/50.78ms. The measured result is performance-eligible; it excludes video encoding and decode I/O.

The same current source was fixed-replayed on a second complete recording, `run_20261106T171405_612600Z` (3,156 frames): Legacy / Segmented / V8.5 Mock downs were **493/330/264** and one-to-one posthoc same-key 80ms proximity was **128/92/68** against 475 recorded human key-downs. Large run-to-run action-count variation confirms these values are not physical-note counts, recall, or game hits.

The latest 343-action attribution is `output/analysis_v86_autoloop/iteration_0021/action_attribution/action_loss_attribution.csv`. Of 149 V8.5 association-unverified rows, exact selected-region trace evidence refines 99 to non-action observation roles (effect/body/UNKNOWN), 17 to lost candidate-track assignment, nine to candidate-track ambiguity, nine to candidate-track hard-gate rejection, eight to a matched existing track, two to another hard-gate rejection, two to other association ambiguity, two remain spatially unlinked, and one target track is outside the 240ms window. These are candidate-region diagnostics, not proof that the paired Legacy action was a real note. The per-case trace is under `iteration_0021/`; compact current summaries are in `final/`.

Two tempting alternatives were explicitly rejected: vectorized component-stat filtering worsened full-run V8.5 compute P90 (50.49→50.71ms), and color-subset Tracker filtering changed P90 only 7.16→7.13ms. Both were reverted. Current accepted changes are limited to exact-ROI operations and an early application of existing hard gates; no timing/scheduler/safety bounds changed. Full tests: **50 passed**. Offline status remains `OFFLINE_NOT_PASSED`; Live remains Legacy.


## Iteration 0025 - zero-copy class-mask input

The class-component loop previously materialized four `uint8` copies of boolean class ROIs for OpenCV. Passing `class_roi.view(np.uint8)` avoids those copies; a targeted test confirms byte and connected-component equivalence for contiguous and non-contiguous row views. No segmentation rules, component ordering, or downstream interfaces changed.

The full fixed 14ms A/B admitted all **3,159** source frames and retained **343/221/186** Legacy/Segmented/V8.5 Mock downs. Action, physical-note-decision, candidate-trace, and safety-audit files match iteration 0022 byte for byte. Mask SHA and component records match on recording frames **97/173** and Assist frames **294/360/894**. Full suite: **51 passed**.

| Repeat | Provider | Processing P90 old?new (ms) | Class-loop P90 old?new (ms) | Capture-age P90 old?new (ms) | Dropped old?new |
|---:|---|---:|---:|---:|---:|
| 1 | V8.5 | 40.23?39.70 | 13.99?13.56 | 62.37?61.04 | 35?31 |
| 2 | V8.5 | 41.58?40.42 | 14.36?13.74 | 66.09?62.99 | 46?33 |

Both measured repeats moved in the same direction for V8.5, but Legacy P90 also rose in the candidate sessions, so host variation remains material. Capture-age P90 remains over 60ms. `replay_lane_filter_measured.py` does not emit scheduler stale-pause/disarm event totals; the exact iteration-0025 stale-event count is therefore unknown. Safety counters remain zero for duplicate press UIDs, missing releases, key-up failures, and illegal keys. Mock press totals are descriptive only. Status remains **`OFFLINE_NOT_PASSED`**. Detailed paired data: `output/analysis_v86_autoloop/iteration_0025/measured_paired_comparison.csv`.


## Iteration 0026 - measured stale-event totals

The measured replay previously lacked explicit Scheduler stale-pause and stale-timeout totals. It now drains `scheduler.drain_events()` after the `observe + decide` wall-time sample has been captured, records only `input_paused` with reason `stale_capture` and `disarmed` with reason `stale_timeout`, then reports per-provider totals. This is diagnostic-only; no scheduler safety rule, engine behavior, or action callback was changed, and event-drain work is excluded from processing_ms.

| Repeat | Provider | Processed / dropped | Processing P90 (ms) | Capture-age P90 (ms) | Stale pauses | stale_timeout disarms | Mock downs |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Legacy | 3155 / 4 | 22.33 | 41.44 | 230 | 0 | 340 |
| 1 | V8.4 Segmented | 3148 / 11 | 32.52 | 51.27 | 246 | 0 | 189 |
| 1 | V8.5 | 3128 / 31 | 39.53 | 61.41 | 63 | 1 | 46 |
| 2 | Legacy | 3156 / 3 | 22.79 | 41.84 | 231 | 0 | 341 |
| 2 | V8.4 Segmented | 3149 / 10 | 31.93 | 51.12 | 246 | 0 | 188 |
| 2 | V8.5 | 3129 / 30 | 39.46 | 62.53 | 64 | 1 | 45 |

V8.5 stale pauses and stale-timeout repeat counts are now reproducible, but capture-age P90 still exceeds the 60ms stop window in both runs. The result is **OFFLINE_NOT_PASSED**. Counts and full per-frame traces are under `output/analysis_v86_autoloop/iteration_0026/`; full tests: **52 passed**.


## Iteration 0027 - lane-ROI class masks (rejected)

This experiment moved four class masks to local y-ROI storage. The first full fixed run found a concrete boundary regression: frame 655 contains a yellow panel at y=28, and recovery padding began at y=26, producing a negative local slice. After clamping the ROI edge, frame 655 masks and component records matched the baseline; five other representative source frames remained exact. The full fixed action, physical-note-decision, candidate-trace, and safety files then matched iteration 0025 byte for byte.

| Repeat | V8.5 processing P90 (ms) | Capture-age P90 (ms) | Dropped frames | Stale pauses | stale_timeout |
|---:|---:|---:|---:|---:|---:|
| 1 | 40.12 | 62.52 | 36 | 66 | 1 |
| 2 | 40.26 | 63.04 | 33 | 62 | 1 |

These did not improve on iteration 0026: 39.53/39.46ms processing P90, 61.41/62.53ms capture-age P90, and 31/30 dropped frames. The ROI construction change was reverted. The regression test for Tap recovery at the class ROI top remains, as does the outside-domain test. Final suite after rollback: **54 passed**. This attempt is rejected for no performance gain; status remains **`OFFLINE_NOT_PASSED`**.


## Iteration 0028 - HSV channel views (rejected)

The `cv2.split` replacement used three views into the interleaved HSV image. It saved around 0.16ms at the HSV stage but made downstream thresholding more expensive because each channel had a 3-byte pixel stride. Class-mask setup P90 increased from **1.71/1.62ms** to **4.84/3.96ms**; segmentation P90 increased from **20.97/20.88ms** to **23.58/22.77ms**.

| Repeat | V8.5 processing P90 | Capture-age P90 | Drops | Stale pauses | stale_timeout |
|---:|---:|---:|---:|---:|---:|
| 1 | 41.78ms | 67.17ms | 44 | 82 | 1 |
| 2 | 41.19ms | 64.41ms | 34 | 90 | 1 |

All source masks, component lists and fixed Replay output hashes remained identical, but measured performance regressed. The code was reverted; the view/stride equivalence test remains. Full suite after rollback: **55 passed**. Status remains **`OFFLINE_NOT_PASSED`**.


## Current-source attribution correction (iteration 0040)

The current provisional 0037 source was replayed with the same complete 3,159-frame fixed 14ms run. Counts remain 343/221/194 Legacy/Segmented/V8.5 Mock downs. The Legacy-action attribution utility previously paired each candidate track with its nearest event without a time limit. That paired some distant, unrelated events. The report now pairs action events only within an **80ms auxiliary event-proximity window**, and retains the nearest outside-window event and signed/absolute delta as diagnostic fields. This window is not a hit or note-recall metric.

| Candidate | Same-key paired action | Different-key paired action vs Legacy | Track association unverified | Not active at reference frame | Other gates/unresolved |
|---|---:|---:|---:|---:|---:|
| V8.4 Segmented | 155 | 32 | 91 | 24 | 41 |
| V8.5 | 104 | 15 | 146 | 19 | 59 |

Of 343 Legacy references, the nearest candidate event fell outside 80ms for 12 Segmented rows and 7 V8.5 rows. The unbounded logic would have labeled 10/2 of those different-key and 2/5 same-key action-present, respectively; they are now unpaired for classification. “Different-key” is relative to the Legacy event and does not prove an objective wrong lane. Cross-provider candidate associations are still provisional, so these are pipeline diagnostics, not physical-note counts. Full files and sequentially decoded evidence are under `output/analysis_v86_autoloop/iteration_0040/action_attribution_segmented/` and `action_attribution_v85/`.

Three previously ambiguous neutral-fragment rows were checked at source/index frames 1756, 2124, and 2199. Each region intersects two Tap candidate boxes and contains mixed Tap-face/UNKNOWN pixels. Owner remains unknown; no segmentation or adapter rule was changed. The 0037 total of 333 suppressed rows separates into 203 same-frame+bbox matches already suppressed in baseline and 130 new 12×8 rows; the earlier grouped audit's 146 count was incomplete. Full suite after the tool correction: **61 passed**. The 0037 measured-time freshness and stale-pause results remain unchanged and still fail the offline feasibility gate. Physical-note ground truth remains absent; status is **`OFFLINE_NOT_PASSED`**.


## Iteration 0041 ? schedule-time lane-key disagreement audit

The 47 paired different-key cases were joined to the candidate's actual `decision_capture_timestamp`, exact provider capture frame, and same-UID `physical_note_decisions.csv` row. Nineteen schedule frames differ from the Legacy reference frame. All **47/47** Engine rows were `COMMITTED`/`SCHEDULED`, and their stored key matched the candidate Mock press key. The 12 cases where the simplified bbox vote differed from the Mock key are explained by the Engine's pending-action rule: it reuses the committed `existing.key`. They are not Engine-to-actuator key mismatches.

Reconstructed latest-center votes matched Legacy in 11/47 cases; median/mean-center alternatives match Legacy in 16/13. These comparisons use Legacy only and are not physical lane truth; they were not replayed through Timing/Scheduler. The candidate's different key therefore remains unverified against the physical note. Forty cases have multiple eligible lane keys. No production code change is justified by this audit.

Both 343-row action-attribution exports include candidate tracker key/press/release-at-reference fields. Full test suite: **61 passed**. Physical-note truth and measured freshness/stale gates remain unresolved; status is **OFFLINE_NOT_PASSED**. See `output/analysis_v86_autoloop/iteration_0041/iteration_report.md` and its manifest.


## Iteration 0042 ? committed-key reuse regression coverage

Added `test_engine_reuses_pending_key_when_current_lane_evidence_differs`, reproducing the observed pending-action branch with a real Scheduler and deterministic ready Timing estimate. It confirms Engine keeps the already committed key when current detection evidence points elsewhere, without rejection/disarm/error or actuator calls. Runtime code and Replay output did not change. Full suite: **62 passed**. This protects key stability but cannot prove the initially committed key is the physical note's lane. Physical-note truth and measured freshness/stale gates remain unresolved; **OFFLINE_NOT_PASSED**. See `output/analysis_v86_autoloop/iteration_0042/iteration_report.md`.


## Iteration 0043 ? alternate same-key action association ambiguity

One Segmented case (`legacy_action_0253`, frame 2256) had a nonpaired UID with a same-key F press 58.4ms before the Legacy F event and a same-frame cyan bbox fully overlapping the Legacy box. The attribution tool now marks the case `ASSOCIATION_AMBIGUOUS` and records alternate evidence without UID reassignment. Segmented different-key counts become 31 (from 32) plus 1 ambiguous; all action totals remain 343/221/194. The spatially separate negative case remains wrong-key; the V8.5 overlap case has the wrong committed key and does not qualify. Focused 15 tests and full 64 tests pass. No runtime change; physical truth remains UNKNOWN and status remains OFFLINE_NOT_PASSED.


## Iteration 0044 ? freshness-qualified same-key alternate UID audit

The cross-UID ambiguity guard now also checks Legacy cases where the selected candidate UID had no same-key paired press. Qualification requires a different-UID same-key press within 80ms, exact decision-capture and Legacy frame rows, fresh observations for both boxes, same known color, eligible/committed expected key, and at least 0.5 smaller-box overlap. Fourteen cases qualify (2 Segmented, 12 V8.5); eight stale-box candidates are excluded. All 14 are `ASSOCIATION_AMBIGUOUS` at medium confidence, preserving their previous stage/reason in `underlying_*`; UIDs are not reassigned. Current stage counts: Segmented 155 same-key, 31 different-key, 3 ambiguous, 91 association-unverified, 22 inactive, 41 other; V8.5 104,15,12,137,18,57 respectively. Action totals remain 343/221/194. Focused 19 and full 68 tests pass. No runtime change; physical-note truth remains UNKNOWN; OFFLINE_NOT_PASSED.


## Iteration 0045 ? exact trace coverage for unverified associations

Audited all 91 Segmented and 137 V8.5 `TRACK_ASSOCIATION_UNVERIFIED` rows from the latest full action-attribution exports against the fixed-replay trace. Exact joins by provider, video frame, and provider-local tracker UID found **0/91** and **0/137** fresh tracker-input/component links. The selected UID's prior observations and last-observation age are retained row by row in `iteration_0045/unverified_trace_link_audit.csv`. No UID/pixel attribution was changed: geometry and stale observations do not prove ownership. No runtime or Replay changed; existing full-suite result remains 68 passed. Physical-note ground truth and quality gates remain unresolved; status **OFFLINE_NOT_PASSED**. See `iteration_0045/iteration_report.md` and `iteration_manifest.json`.


## Iteration 0046 ? preserve Hold connection lineage

Added a per-frame `connection_group_id` shared by each source hold connected region's body, derived head, and derived tail; propagated it through LaneObservation CSV, both provider conversion traces, and replay tracker-input rows. Masks, semantic gates, timing, Tracker, Engine, Scheduler, and actions were not changed. Full fixed 3,159-frame 14ms Replay is byte-identical to iteration 0037 for mock actions, safety audit, frame summary, physical-note decisions, and posthoc action comparison (343/221/194 downs; all safety counters zero). Group audit: 28,120 groups, 44,754 grouped rows, zero endpoint groups without body; tracker inputs carry groups for Segmented 22,213/22,213 and V8.5 8,317/8,317. Targeted 24 and full 69 tests pass. A 15-instance assistant-visual label seed and source/rectified masks were created for frames 294, 360, 894; they are provisional, not human truth. Status remains OFFLINE_NOT_PASSED. See `output/analysis_v86_autoloop/iteration_0046/iteration_report.md`.


## Iteration 0047 - stale track component lineage diagnostic

The 228 rows previously marked `TRACK_ASSOCIATION_UNVERIFIED` now resolve to unique exact last-observed pixel components in the 0046 trace (91/91 Segmented; 137/137 V8.5). Role counts: Tap face 94, UNKNOWN 85, Hold head 27, Hold body 22. This does not prove cross-provider physical identity. Frame 373 provides a provisional mask failure candidate: outer-lane panels remain within one screen-wide UNKNOWN cyan component and are not separately recovered as Tap faces. No runtime/action behavior changed, no physical-note metric is claimed, and status is `OFFLINE_NOT_PASSED`. See `output/analysis_v86_autoloop/iteration_0047/iteration_report.md`.


## Iterations 0076-0077: profiling and rejected microtrial

Iteration 0076 profiled 24 hot and 8 control frames with cProfile. `terminal_cap` accounted for 0.034s cumulative over 668 calls; NumPy median was 0.018s inclusive over 479 calls; connected-components calls totaled 0.095s. This did not explain the rare ~200ms class-loop stalls: frame 3008 was 216.999ms in the 0075 measured repeat and 15.871ms in the instrumented 0076 diagnostic. Root cause remains UNKNOWN. The profile is diagnostic only.

Iteration 0077 tested removal of one sorted-list copy in `terminal_cap`. Exact masks and ordered component records matched across 32 frames and 12 interleaved pairs per frame, but the -0.1702ms/frame mean difference had a 95% paired interval [-0.5519,+0.2116]ms, including zero. The trial was rejected and source restored to saved baseline SHA256 `F5D03A6F20C1E7F0F424A7DD8EEE88D313AE93851E54B0C705BB9A8A39915DB9`. No full Replay/tests were run. Runtime remains retained 0075; status remains `OFFLINE_NOT_PASSED`, and human physical-note labels remain UNKNOWN. Evidence: `output/analysis_v86_autoloop/iteration_0076_terminal_cap_profile/` and `output/analysis_v86_autoloop/iteration_0077_terminal_cap_trial/`.


## Iteration 0078 - bounded GC stall diagnostic

Attempt 2 processed 3,139/3,159 frames (20 drops); its eight largest Engine intervals over 70ms overlapped same-thread generation-2 collections lasting 39-182ms (zero objects collected), with allocated blocks growing about 163k to 2.81m. One GC-disabled attempt processed 3,153 frames (6 drops), had no updates over 70ms, and reduced max 206.46 to 57.50ms; P90 was 40.31 to 40.21ms. This supports Gen2 collection as a proximate pause cost in this diagnostic harness, but does not explain the tracked heap. Admissions/actions differ from the measured repeats; no production or semantic-equivalence claim. Runtime remains 0075; OFFLINE_NOT_PASSED. See `iteration_0078_stall_causes/attempt_2/` and `attempt_3_gc_disabled/`.

## Iteration 0079 - compact measured recording mode

Added performance-only recording to the measured replay tools. Every Engine decision row is still computed and counted, while copied per-note output dictionaries/history and `physical_note_decisions.csv` are omitted. Detailed recording remains available. Two 100-frame V85 smoke runs matched at 1,421 decisions and identical Mock action signatures. The full two-repeat matrix used six fresh processes and verified all processed timestamps; every hard Mock safety counter was zero. V85 compact P90 was 36.64/36.49ms, P99 43.03/42.90ms, capture-age P90 55.86/55.70ms, drops 0/1, stale pauses 300/300, timeouts 0/0. This is a measurement-harness correction, not a perception gain; per-note attribution is unavailable. Runtime remains retained 0075, physical labels UNKNOWN, OFFLINE_NOT_PASSED. Latest full suite: 97 passed in 1.22s. See `iteration_0079_compact_measured_matrix/`.


## Iteration 0080 - stale-pause boundary alignment

A read-only join of the two 0079 compact V85 runs aligns all 600 `input_paused` events to `stale_capture` near or beyond the unchanged 60ms Scheduler `max_age`. Decision-age min/P50/P90/max was 60.003/60.994/61.980/114.122ms and 60.003/60.995/61.978/106.645ms. In each repeat, 151/300 pauses occurred within 5ms of the next source acquisition (median delta 4.836ms). The following frame had not yet passed Perception, so this does not justify relaxing the safety bound or establish hit truth. Runtime remains 0075; physical labels UNKNOWN; `OFFLINE_NOT_PASSED`. See `output/analysis_v86_autoloop/iteration_0080_stale_pause_alignment/analysis_report.md`, `summary.json`, and `stale_pause_event_alignment.csv`.

## Latest performance-only trial - iteration 0082 (OFFLINE_NOT_PASSED)

The V85 Replay provider skips polygon construction only when created by `make_state`; default and rendering paths retain polygons. Regression coverage confirms equal masks, ordered component data apart from polygon payloads, identical provider detections, and default polygon retention. The full fixed 14 ms replay processed 3,159 frames; seven semantic artifacts match 0075 byte-for-byte, and Mock downs remain 342/294/259 with all hard safety counters zero.

| Repeat | V85 processing P90 | Capture-age P90 | Stale pauses / timeout disarms | Mock downs | Class-component-loop mean / P90 | Segmentation mean / P90 |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 28.743 ms | 47.560 ms | 226 / 0 | 228 | 5.904 / 8.817 ms | 11.894 / 15.772 ms |
| 2 | 28.706 ms | 47.460 ms | 227 / 0 | 229 | 5.862 / 8.735 ms | 11.797 / 15.776 ms |

Two counterbalanced fresh-process repeats covered baseline, Segmented, and V85; all six runs timestamp-verified 3,159/3,159 frames. Video encoding and OS input were excluded. Relative to 0081, raw V85 P90 fell 7.6/7.7%, while baseline controls shifted faster 0.973/0.290 ms. The conservative control-adjusted candidate deltas are 1.40/2.11 ms; host and wall-clock effects prevent attributing the full raw difference to the trial. Stage class-component-loop mean/P90 was 6.672/10.185 and 6.707/10.354 ms in 0081; segmentation was 13.272/18.013 and 13.373/18.159 ms.

Performance-only output omits per-note attribution. Mock downs are not physical-note hits or recall. Physical-note truth remains UNKNOWN, stale pauses persist, runtime candidate remains 0075, Live remains Legacy, and status remains **OFFLINE_NOT_PASSED**. Full suite: **99 passed**. Evidence and hashes: `output/analysis_v86_autoloop/iteration_0082_skip_polygons/`.

## Iteration 0089 — Scheduler safety boundary tests

Added five deterministic Mock-only tests for unfocused arm rejection, key release/disarm on live focus loss, key release/disarm through `stop_hotkey`, rejection beyond the 9-second Hold limit, and stale-capture release plus the existing 200 ms disarm. No Scheduler/Live code changed and no OS input was sent. Focused suite: 5 passed; full suite: 108 passed; compileall passed. This adds safety regression coverage, not perception or Active evidence. Physical-note labels remain UNKNOWN, the 122 cross-provider associations remain unverified, and acceptance remains OFFLINE_NOT_PASSED. Details: `output/analysis_v86_autoloop/iteration_0089_safety_boundary_tests/iteration_report.md`.

## Iteration 0090 — post-cleanup Replay smoke

After retiring obsolete cleanup helpers, the full fixed-delay compare Replay processed all 3,159 indexed frames using the same 14 ms synthetic delay, arm window, timestamp source, geometry/calibration, and Engine/Tracker/Timing/Scheduler. Mock downs stayed 342/294/259 and all hard safety counters were zero. Six semantic outputs were byte-identical to iteration 0088; wall-time columns differed and are not a measured-time claim. The full test suite passed 108 tests; both Replay CLI help commands and core import smoke passed. Raw video/index hashes match saved manifests. V85 remains OFFLINE_NOT_PASSED with human physical-note labels UNKNOWN; measured-time results are still the 0088 repeats. Details: `output/analysis_v86_autoloop/iteration_0090_cleanup_audit/iteration_report.md`.

## Iteration 0091 — current exact-trace attribution for unverified rows

The 0086 tracker trace was revalidated against the current full 0090 trace: the decompressed trace SHA-256 is identical, and all 122 current `TRACK_ASSOCIATION_UNVERIFIED` rows exactly join to the trace refinement by case ID, video frame, Legacy key/bbox, and selected V85 local trajectory UID. Trace-visible evidence is 65 evidence-only nearest components (33 effect/artifact, 32 Hold body), 35 accepted components assigned to another V85-local UID, 20 ambiguous/unassigned components, and 2 frames with no spatial component. For the 55 accepted components, the target-trajectory trace dispositions are 13 global-assignment competition, 17 ambiguous detection, 11 edge rejected, and 14 no edge. These are Tracker observations, not proven cross-provider physical ownership; all 122 original causes remain unverified. No source or root-cause stage changed. See `output/analysis_v86_autoloop/iteration_0091_tracker_rebase/`.

## Iteration 0092 — foreign-UID spatial trajectory audit

A read-only exact-frame join of the 35 cases whose accepted V85 component was assigned to a different provider-local Tracker UID found: 34/35 components included the Legacy key, 30/35 matched Tap/Hold kind, and 30/35 overlapped at least half the Legacy box's smaller area. Across 228 fresh framewise spatial comparisons in the reference frame and eight preceding frames, the exact-assigned UID ranked among the top spatial candidates 73 times versus 36 for the UID selected by the original trajectory matcher; the exact-assigned UID ranked ahead in 16/35 cases. This supports a Tracker identity/assignment ambiguity mechanism, but does not prove physical ownership.

The exact-assigned UID emitted a same-key V85 Mock down within the auxiliary 80 ms window in 8/35 cases; any V85 UID did so in 12/35. These events were not attributed to the physical note and are not hit or recall evidence. Case `legacy_action_0009` illustrates a reference-frame Tap component assigned to `note:185` while the old matcher selects `note:141`; `note:185` is spatially aligned at the reference frame but remains unconfirmed with `insufficient_motion_or_late_origin`. Physical ownership remains UNKNOWN, and all 35 original rows stay `TRACK_ASSOCIATION_UNVERIFIED`. No source, policy, or Live behavior changed. Details and hashes: `output/analysis_v86_autoloop/iteration_0092_tracker_assignment_diagnostic/`.

## Iteration 0093 — exact association-edge decisions

The 55 accepted components among the 122 association-unverified rows were joined by exact provider/frame/component ID to the sparse Tracker edge trace. The original target trajectory UID had a feasible edge that lost global assignment in 13 cases, a feasible edge left ambiguous in 11, a gate-rejected edge with an ambiguous detection outcome in 6, a rejected edge in 11, and no recorded edge in 14. The trace contains feasible edges for 53/55 components and competing feasible edges for 46/55. These counts prove the Tracker processing branch but not physical identity.

For `legacy_action_0009` at frame 191, the target UID `note:141` has no association edge. The visible spatial component has three feasible edges: `note:185` is selected at cost 0.1713, `note:179` loses global assignment at 0.5357, and `note:186` loses at 0.9813. The detection is assigned to `note:185` but remains unconfirmed. A sequential source/mask contact sheet covers frames 187–195 and overlays those provider-local IDs; the visual label remains provisional and physical identity UNKNOWN. This makes the Tracker identity competition explicit while leaving physical ownership UNKNOWN. No attribution stage or runtime behavior changed. Details and hashes: `output/analysis_v86_autoloop/iteration_0093_tracker_edge_audit/`.

## Iteration 0094 — spatially missing cases inspected

The two rows without an exact-frame spatial component were replayed through the current pixel segmenter from sequential source frames. For frame 1787's 25×4 rectified Legacy L/Hold ROI, all 100 pixels are explicitly UNKNOWN and no Tap/Hold role pixel is present. For frame 2715's 70×20 Legacy K/Tap ROI, the segmenter assigns 396 pixels UNKNOWN and 1,050 to the lane mask, with no Tap/Hold/effect role. It emits no action-role component in that ROI. The selected V85 trajectory UID at frame 2715 is a completed D-key fragment at a distant bbox, so that cross-provider pairing does not establish physical identity. Nine-frame contact sheets and hash-bearing manifests are in `output/analysis_v86_autoloop/iteration_0094_spatial_missing_audit/`.

The second source window contains a cyan panel near the judgment area, but the available image does not settle whether it is the corresponding Tap, a Hold part, or overlapping material. The current masks explicitly abstain; no recovery threshold was changed. Both rows remain UNKNOWN, V85 remains offline, and Live remains Legacy.

## Iteration 0095 — focused human-review packet

Prepared a six-case queue containing the three Assist windows (4.9s, 6.0s, 14.9s), the frame-191 identity-competition case, and spatially missing frames 1787 and 2715. The CSV keeps all physical labels UNKNOWN and links each row to source/mask media; `README.md` defines reviewer-entered values and cautions that UIDs and 80ms proximity are diagnostic only. `review_manifest.json` contains hashes for the queue and all 12 media references. No labels were promoted. See `output/analysis_v86_autoloop/iteration_0095_human_review_packet/`.
