# V8.6 Autonomous Recovery Result

Date: 2026-11-15. **Status: `OFFLINE_NOT_PASSED`.** V8.5 remains offline; Live continues to use Legacy Perception. No OS keyboard input, Scheduler safety-bound change, or calibration change was made. Raw `output/recording/run_*` and `output/assist/run_*` remained read-only.

## Current update - iteration 0051 (runtime candidate remains 0049)

The current edge-recovery build passes 78 tests and completed same-source full fixed and two-repeat measured A/B. Iteration 0048 recovered two observed cyan edge Tap masks at frame 373 while keeping the inter-panel bridge UNKNOWN; its continuous before/after video is still missing and the archived comparison renderer hash is unavailable. Iteration 0049 removed an arbitrary key-order choice when two best lane keys have equal votes and equal center distance. The exact ambiguous track no longer presses S; this is an abstention, not proof that another key is physically correct.

Latest full fixed 14ms Mock downs are **342/293/259** Legacy/Segmented/V8.5, all safety counters zero. Two measured repeats gave Legacy P90 12.80/13.10ms with 1 drop each, Segmented 15.56/15.61ms with 1 drop each, and V8.5 18.72/18.87ms with 9 drops each. Stale pauses remain 230-231 per run. Automated cross-provider wrong-key categories changed Segmented 45→41 and V8.5 27→25, while their same-key action categories changed 173→174 and 123→123. These are action-trajectory comparisons against Legacy, not physical-note labels, precision, recall, or game hit rate. Geometry remains pending calibration; no geometry remap is justified by the available frames.

Decision remains **OFFLINE_NOT_PASSED**. Physical-note truth, reviewed Tap/Hold/occlusion/negative cases, exact archived parent-source provenance, and the measured freshness/stale-pause gate are not satisfied. During evidence-manifest maintenance, a bare `git` command was accidentally invoked; it printed usage help only, with no repository subcommand or state-changing operation. This nevertheless violated the user's explicit no-Git-command instruction. Current evidence is in `output/analysis_v86_autoloop/iteration_0048/`, `iteration_0049/`, and `iteration_0051/`; details are in their reports and `docs/V86_EVALUATION.md`.

## Iteration 0050 validation

No runtime candidate logic changed after iteration 0049. The source-aligned 25-frame clip for frames 361–385 preserves the normalized source aspect and includes rectified pixels plus semantic masks; the index join is verified for all 25 frames. On sequential frame 1004, the pending geometry projection's lane centers differ from approximate bottom-row UI keycap centers by −20.1 to +20.8 reference pixels, increasing from left to right. This is a provisional geometry-alignment warning: UI keycaps are not proven chart-lane centers. Calibration was not modified.

Renderer tests passed 6/6; the full suite now passes 84 tests and compileall passes. Runtime A/B numbers remain those from iteration 0049 because iteration 0050 adds visual diagnostics only. The continuous clip is not a before/after comparison; the immediate-parent edge-recovery render hash remains unavailable. Status remains **OFFLINE_NOT_PASSED**. See `output/analysis_v86_autoloop/iteration_0050/iteration_report.md`.

## Iterations 0051–0052 validation

Iteration 0051 produced a continuous source-aligned frame-361–385 mask comparison using an explicitly reconstructed iteration-0047 outer-ROI behavior. At frame 373, the current segmenter yields two cyan edge components and zero Tap pixels in their intervening bridge band; the old source code was not preserved, so this is a reconstruction rather than an exact historical A/B. Iteration 0052 then joined both exact components into the iteration-0049 full fixed Replay: each reached adapter acceptance, a confirmed provider-local track, Scheduler pending, and a completed Mock down/up (D and K). This establishes a successful pipeline path for those replay rows, not physical-note recall or correct lane/key truth. The lifecycle CSV is `output/analysis_v86_autoloop/iteration_0052/edge_recovery_lifecycle.csv`.

No runtime change was made in iterations 0050–0052. The latest full suite remains 84 tests from iteration 0050, and the latest fixed/measured Replay remains iteration 0049. The exact parent source, independent physical-note annotations, pending geometry calibration, stale-pause improvement, and broader Tap/Hold/effect/occlusion/negative review remain unresolved. Status remains **OFFLINE_NOT_PASSED**.

## Iteration 0051 validation

Added a sequential four-panel comparison for frames 361–385. The pre-change mask is a documented reconstruction of iteration 0047's omitted outer centered ROIs; the exact historical segmenter and renderer are unavailable, so this is not an exact parent build. At source frame 373, the reconstructed version has zero cyan edge Tap components; the current version has two observed cyan faces (3,176 and 3,103 pixels) and zero Tap pixels in the relevant bridge band. All 25 source/index joins are verified. The archived mask panel remains non-identical to the reconstructed output (17,990/145,440 pixels differ), so the result is provisional pixel evidence, not a historical binary comparison or physical-note truth.

On this 25-frame diagnostic, reconstructed/current segmentation means are 7.16/7.62ms; do not interpret this as a stable runtime comparison. No inference/action logic changed, so the 84-test full-suite result and full fixed/measured replay remain from iterations 0050 and 0049. The edge mask result is retained for offline evaluation; overall status remains **OFFLINE_NOT_PASSED**. See `output/analysis_v86_autoloop/iteration_0051/iteration_report.md` and `edge_recovery_ab_361_385_final/`.

## Historical candidate snapshot (iteration 0037)

The latest full fixed 14ms replay covers 3,159 indexed frames and produces **343 / 221 / 194** Legacy / Segmented / V85 Mock presses. All hard Mock safety counters are zero. Relative to a fresh-process full fixed replay using the 0034 `early_perception.py` snapshot, the narrow 12×8 neutral-fragment adapter rule changes V85 presses 186→194, posthoc 80ms same-key proximity matches 57→59, and extra/wrong proximity actions 129→135. These proximity figures are auxiliary diagnostics, not note recall or game hits. An exact-index visual audit found visible note-like faces in changed windows, but overlap and effects prevent confident action ownership in several cases.

Iteration 0036's broad rule was rejected after suppressing 3,530 neutral fragments and creating unresolved action/identity changes. Iteration 0037 narrows suppression to the source-verified 12×8 fragment: it preserves the confirmed Tap identity at frame 186 and suppresses 333 fragments over the full run. Full fixed baseline/candidate host compute deltas were small and provider-wide runtimes varied sharply between runs, so no performance gain is claimed. See `output/analysis_v86_autoloop/iteration_0036/iteration_report.md` and `iteration_0037/iteration_report.md`.

The 0037 candidate and archived 0034 perception baseline were each run through two fresh-process measured matrices on the same host. Candidate V85 compute P90/P99 was **17.91/22.29ms** and **18.04/22.38ms**; capture-age P90/P99 **36.82/42.53ms** and **36.98/42.57ms**; drops **5/5**, stale pauses **231/229**, timeout disarms **0/0**. Same-host baseline compute P90/P99 was **18.22/23.21ms** and **18.10/21.79ms**; capture-age P90/P99 **37.09/43.78ms** and **37.03/42.60ms**; drops **5/5**, stale pauses **230/230**, timeout disarms **0/0**. The small compute/age deltas are mixed and do not establish a repeatable speedup; both snapshots still have many stale pauses. Source frame interval P90 is **41.22ms**. Physical-note truth and human-reviewed Tap/Hold/occlusion/negative labels remain absent. Keep V85 offline; the recovery gate has not passed.

The stale-pause boundary audit shows those pauses are caused by the recorded 60ms Scheduler freshness rule crossing before the next frame's acquired timestamp; pause-age median is about **60.9ms**, and **149–150 of 229–231** events per run are followed by the next frame within 5ms. Baseline and candidate show the same pattern. The rule was not changed. See `output/analysis_v86_autoloop/iteration_0038/iteration_report.md` and its event-level CSV.

Physical-note truth and human-reviewed Tap/Hold/occlusion/negative labels remain absent. Keep V85 offline; do not describe Mock action counts or 80ms key proximity as recall or game hit rate. The recovery gate has not passed. See [V86 evaluation](V86_EVALUATION.md).

## What the 54-press gap means

The reported Legacy 72 / Segmented 18 and stale-pause 46 / 232 figures came from a Scheduler event-history view capped at 512 entries. `updated` events consumed that ring, evicting early Legacy presses and pauses. The full callback stream shows **348 Legacy vs 18 Segmented** presses in the original fixed-delay snapshot and **232 stale-pause events for each provider**. Therefore there is no real 54-press algorithm loss to assign: the 54 is a logging artifact. The complete original-stream difference is 330. See [V84 regression root cause](V84_REGRESSION_ROOT_CAUSE.md).

After the V8.4 perception/adapter rework, a separate complete fixed replay reported 348 / 228. The historical iteration-0010 same-source replay reported Legacy / V8.4 Segmented / V8.5 at **343 / 221 / 179**; the latest iteration-0022 fixed replay is **343 / 221 / 186**. These are different code snapshots; they must not be mixed with the original 72 / 18 report.

## Historical fixed-delay attribution (iteration 0010)

All 3,159 indexed frames were admitted with a shared synthetic 14ms processing delay, 1–124s Arm window, 2ms polling, identical timestamps, Engine, Tracker, Timing, Scheduler, geometry, timing calibration, and key map. The 14ms is a replay clock setting, not an estimate of execution cost. This historical output records 343 / 221 / 179 Legacy / Segmented / V8.5 Mock downs, with zero duplicate UID, illegal key, key-up failure, or unreleased press UID.

The 343 Legacy actions paired against V8.5 trajectories divide into:

| Last observed V8.5 outcome | Count |
|---|---:|
| Same-key V8.5 Mock action | 116 |
| V8.5 Mock action on a different key | 29 |
| Engine Tap visibility gate | 85 |
| Engine type pending | 40 |
| Engine eligibility gate | 49 |
| Timing gate | 8 |
| Timing insufficient observations | 11 |
| Pixel role retained as UNKNOWN | 5 |
| **Total** | **343** |

This is a source-frame and multi-frame trajectory attribution, not independently reviewed physical-note truth. The 116 same-key actions do not mean 116 true notes were recognized, and the 29 wrong-key actions are a material unresolved error class.

## Historical bounded performance change (iterations 0005–0010)

The Tracker's sparse assignment remains an exact decomposition of the hard-gated feasible graph; gates and unmatched costs did not change. This iteration adds a data-structure optimization to segmentation: reject components from cheap stats before allocating tight pixel ROIs, and allocate Hold head/tail scratch masks only for Hold-body candidates. No semantic threshold changed.

The full fixed-delay run is behavior-preserving: `mock_actions.csv`, `physical_note_decisions.csv`, and `candidate_trace.csv` have identical SHA-256 hashes to the prior full fixed replay. The current 14ms action counts are 343 / 221 / 179. Six real source frames covering green Hold, cyan Tap, near-hit effect, gray panel, yellow Hold, and simultaneous Holds also produced 48/48 role masks pixel-identical to the retained pre-optimization masks. The short segmentation diagnosis saw mask/component P90 fall from 18.33 to 15.97ms; the new full measured profiles show 18.70/20.11ms before and 17.15/17.51ms after, a local reduction of about 8-13%. The class-component loop accounts for most segmented work. Pixel-mask comparison hashes are in `output/analysis_v86_autoloop/iteration_0005/mask_equivalence_audit.csv`.

Two full unprofiled measured repeats in `iteration_0005` show V8.5 at mean/P90 32.43/43.53ms and 31.88/43.12ms, with 58/57 drops and 44/42 Mock downs. Legacy was 17.01/23.15ms and 17.21/23.56ms, with three drops each and 341/344 Mock downs. V8.4 Segmented was 29.47/39.50ms and 28.53/38.61ms. The source interval P90 is 41.22ms, so V8.5 still runs past the frame budget; each repeat also had one stale-timeout disarm. All runs had zero illegal keys, duplicate press UIDs, missing key-ups, or key-up failures.

The host was faster than the previous `iteration_0003` session, so comparisons use within-run providers and retain both repeats. Post-hoc 80ms human-key proximity counts were V8.5 17/17 and Legacy 105/106; these do not measure physical-note recall or gameplay hit rate. The segmentation improvement is a local cost reduction only; it does not qualify V8.5 for Active.

## Visual evidence and remaining blockers

Source-aligned continuous clips and masks cover attribution stages, the slowest frame, the first measured latest-frame gap, and Assist frames 294, 360, and 894. The 14.9s/frame 894 source window maps to indexed `source_frame=1086`; the tool reports both values instead of treating preview time or provider UID as identity. All rows are `PROVISIONAL_VISUAL_AUDIT`; physical notes and Hold ownership are `UNKNOWN`, not `HUMAN_REVIEWED`. The actual before/after V8.4/V8.5 comparison remains available under `output/analysis_v85_early_identity/v84_v85_visual_comparison/`. The multi-Hold/Tap frame still has heavy effect contamination in the mask; it does not establish separate Hold ownership. Yellow Hold and gray-note recall remain not evaluable without reviewed source labels.

The current Tracker scan covered all 20 complete local indexed Runs: 98,669 indexed/decoded frames, 106,978 automatic candidate tracks, and 24,840 automatically confirmed tracks. The four target runs account for 13,128 candidates / 2,966 confirmed tracks. Across all 20, 65 candidates had a yellow-Hold hint and seven were automatically confirmed; the two key recording runs each had one yellow-Hold-hinted candidate and zero confirmed yellow Holds. Neutral pending hints remain common. These are automatic model outputs, not physical-note counts or recall.

The complete evaluation, stage percentiles, stale/drop counts, replay paths, and test results are in [V86 evaluation](V86_EVALUATION.md). Full raw replay files are referenced rather than copied into `final/` to avoid duplicating hundreds of megabytes; paths and review artifacts are recorded in `output/analysis_v86_autoloop/final/evidence_manifest.json`. The source-only test suite passed 32 tests and 37 Python files passed in-memory syntax compilation. No manual review or physical-note recall score is claimed.

Two diagnostic-only 2,700-frame measured prefixes added per-note subphase timing for rare latency spikes. Their ordinary latency shifted substantially between runs, and maxima moved among segmentation, row construction, and one Scheduler snapshot (up to 145ms). Since the mock replay Scheduler has no background thread and no same-stage/same-frame repeat was established, the spike cause remains `UNRESOLVED_HOST_OR_RUNTIME_VARIANCE`; these runs are not evidence of an algorithmic speedup or slowdown. The full traces and measured interpretation are in [V86 evaluation](V86_EVALUATION.md).

## Cleanup

`tools/cleanup_v85_candidates.bat --execute` completed successfully after its exact-path checks and explicit Y confirmation after iterations 0033, 0034 and 0035 validation. It removed only `src/__pycache__`, `tests/__pycache__`, and `tools/__pycache__`; a follow-up filesystem check found none remaining. No raw recording, assist, calibration, fixture, source, or replay evidence was targeted. The current audit is recorded in `iteration_0033/iteration_manifest.json` and `final/evidence_manifest.json`.

`.gitignore` excludes `/output`, so replay videos, CSVs, and case evidence are not included in a normal source upload. During later evidence maintenance, a bare `git` command was accidentally invoked and printed usage help; no repository subcommand or state-changing operation was run. This violated the user's explicit prohibition, and is recorded in the current result and evidence manifests.

## Release decision

Do not promote V8.5 or enable a new Active path. The optimization is accepted as a low-risk Tracker cost reduction, but image semantics, wrong-key attribution, high-tail latency, stale capture, missing human-reviewed Tap/Hold/effect/occlusion/negative cases, and uncertain Hold head/tail ownership leave the offline acceptance gates open.

## Continuation update: iteration 0010

The historical results above end at iteration 0005. The current code and complete re-evaluation are iteration 0010; status remains **`OFFLINE_NOT_PASSED`**.

- Fixed-delay replay again used all 3,159 indexed frames with the same synthetic 14ms clock. Current Mock downs are Legacy/Segmented/V8.5 **343/221/179**. The post-hoc 80ms human-key proximity is 105/66/52; it is not note recall or game-hit evidence. Source-frame attribution for 343 Legacy actions is: V8.5 same-key action 99, wrong-key action 17, Tap visibility gate 75, type pending 61, eligibility gate 42, not active at exact reference frame 20, segmentation UNKNOWN 2, Timing 25, Scheduler rejection 2. Detailed cases are in `iteration_0010/action_attribution/`.
- Two measured-time full repeats disagree materially. V8.5 mean/P90, drops, Mock downs, and 80ms proximity are **24.68/35.59ms, 21, 38, 18** and **33.24/44.51ms, 74, 35, 14**. The indexed capture-interval P90 is 41.22ms; one run is below it, the other above with 74 drops. On 3,065 common processed frames, repeat 2 is 8.02ms slower at the median and multiple stages move together. This is not a reproducible real-time improvement.
- A source-backed cyan Tap panel at frame 186 is retained as 1,591 observed pixels and survives the EarlyPixelProvider adapter as a full Tap candidate; the clipped hit-glow ROI produces zero Tap pixels. Colored faces under 12px and thin neutral rails remain UNKNOWN/pending. The ROI is lane-centered and batched; a 600-frame fixed prefix preserved action counts while its Tap-recovery P90 fell from 6.39ms to 3.36ms. The full current measured Tap-recovery P90 is 3.63/4.38ms.
- The current fixed replay safety audit reports zero illegal keys, duplicate press UIDs, presses without release, key-up failures, or repeated down for one UID. No Scheduler bound, Live default, calibration, or input safety code changed. No OS input was sent.
- `python -B -m pytest -q -p no:cacheprovider` passes **41 tests**. Source-indexed masks, timelines, and continuous review clips for the current run are in `output/analysis_v86_autoloop/iteration_0010/case_windows/`; they remain provisional and not human reviewed. Physical-note recall, false-positive rate, type confusion, identity accuracy, and Hold ownership are still `NOT_EVALUABLE`.

Historical cache-audit note, superseded by the successful iteration-0033 execution recorded in the Cleanup section above. The exact three bytecode cache directories were removed; raw recording/assist data, fixtures, calibration, and canonical replays were untouched.

Keep the Legacy perception path as the Live default. Current evidence does not satisfy physical-note quality, repeated measured-time feasibility, or human-reviewed visual gates; do not enable Active.

## Attribution integrity update: analysis revision 0012

A source-aligned audit found that the prior attribution joined a Legacy action to a candidate track by geometry/motion, then independently chose the nearest segmentation component. That could misstate which pixel component belonged to the matched track. The attribution tool now requires a same-provider, same-frame `tracker_uid` link before calling a component the track's actual input; unassigned nearby candidates are reported separately, and stale track observations are not assigned a definitive Engine/Timing root cause.

On the unchanged 3,159-frame iteration-0010 fixed replay, revised counts for 343 Legacy actions are: 99 same-key candidate actions, 17 wrong-key actions, 158 tracker-association-unverified, 20 not active at the reference frame, 34 Engine gates, 11 Timing gates, 2 Scheduler rejections, and 2 UNKNOWN. Only 104 rows have exact track-component links; 234 rows show spatially overlapping but unverified detections. `physical_note_id` remains UNKNOWN, so this is not a true-note recall score. Frame 177 demonstrates a spatial Tap candidate with no Tracker identity and an older matched track observation; the earlier ENGINE_TAP_VISIBILITY label is not independently proven as the physical cause.

The corrected CSV, regenerated source-aligned windows, command, hashes, and 45-test result are recorded in `output/analysis_v86_autoloop/iteration_0012/iteration_manifest.json`. Replay performance and Mock counts remain those from production candidate iteration 0010. The offline gate remains **`OFFLINE_NOT_PASSED`**; keep Live on Legacy.

## Tracker-stage follow-up: iteration 0013

Added opt-in Tracker association diagnostics and reran the complete 3,159-frame fixed 14ms Replay for all providers. The diagnostic flag records current-frame component IDs and pixels' boxes, per-cap hard-gate reasons/costs, ambiguity/global-assignment disposition, and final cap/note assignment. It changed no matching gate or scheduler behavior. `mock_actions.csv`, `physical_note_decisions.csv`, and `candidate_trace.csv` are byte-identical to iteration 0010; counts remain **343 / 221 / 179**. The diagnostic run's wall-time values are explicitly ineligible for performance comparison because selected frames logged extra data.

The 158 V8.5 and 86 V8.4 rows previously labeled tracker-association-unverified now have additional *candidate-region stage evidence*: V8.5 has 103 regions classified as effect/body and not offered as action observations, 17 exact target-component edges lost global assignment, 19 ambiguous assignments, 10 exact-component hard-gate rejections, six exact components assigned to an existing track, one prior track outside the 240ms association window, and two spatial candidate links still unverified. V8.4 has 73 spatial components dropped before Tracker input, six exact components assigned to an existing track, four ambiguous, one outside the 240ms window, one exact hard-gate rejection, and one unresolved. The full category split is in `iteration_0013/iteration_manifest.json`.

These are not 158 or 86 proven physical-note misses. Several selected spatial components are explicitly `effect_or_artifact`, `hold_body`, or `UNKNOWN`, and the accepted components sometimes acquire a different provider-local note UID. Frame 97 V8.4 provides a concrete adapter path: component 83 is a large cyan observed-pixel region `(0,250,209,73)` with role `unknown`, then `dropped_semantic_gate`; its relationship to the historical Legacy Tap is still unverified. This is a real data path and possible merge/semantic issue, not proof of the note's physical identity. Human-reviewed note truth remains UNKNOWN and status remains **`OFFLINE_NOT_PASSED`**.

The exact-frame diagnostic trace, spatially filtered 691-case table, reproducible tools, hashes, and 47-test output are under `output/analysis_v86_autoloop/iteration_0013/`; compact refinement and summary copies are under `output/analysis_v86_autoloop/final/`.

### Iteration 0014 — inspect ambiguous Tap identity and alternate actions

For the 29 V8.5 association-unverified cases with an accepted Tap-face component, a full-source fixed replay traced three frames around each target and added cap confirmation/age/votes to edge evidence. At frame 177, one cyan Tap component had two confirmed feasible tracks (`note:100`, 51 observations, cost 0.10134; `note:137`, 27 observations, cost 0.14825); the 0.04690 cost gap is inside the existing 0.12 ambiguity margin. Tracker correctly withheld an identity. The source does not prove whether this is one duplicate identity or two overlapping physical notes, so no matching rule was loosened.

The same fixed replay shows V8.5 `note:137` pressing K 12.08ms before Legacy `note:32` presses K. Across the 158 V8.5 low-confidence cases, 29 have a same-key candidate press within 80ms of the Legacy event; 53 have any-key candidate press in that window. V8.4 has 0 and 13 respectively among 86 cases. These are auxiliary cross-provider action-time diagnostics only; action proximity cannot prove physical identity, recall, or gameplay hits. This evidence explains why some UID-level “loss” rows may coincide with a different local candidate action, but does not upgrade them to successes.

The targeted trace and 691-row cross-provider action-time table are under `output/analysis_v86_autoloop/iteration_0014/`, with commands and hashes in its manifest. Status remains **`OFFLINE_NOT_PASSED`**.

### Iteration 0017 — suppress one verified adapter duplicate pattern

The exact frame-173 trace showed two inputs from one overlapping image region: a cyan complete Tap face at `(231,259,103,28)` and a neutral 3px rail at `(240,284,83,3)`. Both entered V8.5 as Tracker observations; the rail was `UNKNOWN` in the pixel segmenter but became a `plate_fragment` in the adapter and updated a second established Tap identity while the full face updated another. The new adapter rule retains the neutral pixels and UNKNOWN segmentation evidence but suppresses that narrow partial-neutral candidate only when a same-frame complete Tap face covers at least 90% of its width and its pixels sit within the face's bottom bevel. Without a covering face, or for fragments taller than 4px, it remains eligible for temporal association.

The same-process full 3,159-frame fixed 14ms comparison produced **343 / 221 / 186** Legacy / Segmented / V8.5 Mock downs, versus **343 / 221 / 179** in the prior fixed baseline. Legacy and Segmented action and decision rows are byte-equivalent after filtering by provider; V8.5 changed. The same-key/80ms auxiliary counts were 105 / 66 / 57 (prior V8.5 52), and V8.5 extra/wrong-key proximity rose 127→129. These are not physical-note truth; the narrow adapter fix has unresolved precision and is not a reliable game-quality improvement. In the three-provider run V8.5 `compute_wall_ms` P50/P90/P99 was 39.65/53.93/69.11ms; an isolated V8.5 fixed run measured 31.53/43.15/54.55ms, so host/load makes these unsuitable as a paired speed claim. The fixed 14ms is a replay clock setting, not the measured compute cost.

The current measured-time comparison admitted 3,159 frames and processed 3,156 / 3,148 / 3,073 for Legacy / Segmented / V8.5, dropping 3 / 11 / 86. Processing P50/P90/P99 was 16.39/24.22/32.00ms, 26.63/34.66/42.23ms, and 33.38/44.76/54.88ms respectively. V8.5 capture-age P90/P99 reached 80.92/101.59ms. Stale-capture pause events were 230 / 272 / 92 and V8.5 also disarmed once for `stale_timeout`. Mock downs were 338 / 184 / 38; 80ms same-key action proximity was 104 / 55 / 18. The measured-time run therefore does not pass freshness or action-quality gates. It used the current source once, on this host; older measured repeats used an earlier code snapshot and are context only. All 50 tests passed. Detailed paths and hashes are in `output/analysis_v86_autoloop/iteration_0017/iteration_manifest.json`. Status remains **`OFFLINE_NOT_PASSED`**.

The supplementary stage table shows that the 29 same-key time-near rows include six of 16 candidate-track ambiguities, three of three other component ambiguities, four of 17 global-assignment losses, and two of eight candidate-track hard-gate rejections. This is an action-event association clue, not physical-note validation.


## Iteration 0025 - zero-copy class-mask input

`LanePixelSegmenter.segment()` now presents each boolean class ROI to `connectedComponentsWithStats` as a `uint8` view instead of allocating a converted copy. Pixels remain 0/1 and OpenCV treats nonzero as foreground. A focused test compares labels, stats, and centroids for contiguous and non-contiguous row slices.

The 3,159-frame fixed 14ms replay retained **343/221/186** actions. `mock_actions.csv`, `physical_note_decisions.csv`, `candidate_trace.csv`, and safety audit are byte-identical to iteration 0022. On recording frames 97/173 and Assist frames 294/360/894, every role-mask SHA and ordered component record is identical. Full suite: **51 passed**.

Two measured current-source repeats show V8.5 processing P90 **39.70/40.42ms** versus iteration-0022 **40.23/41.58ms**; segmentation P90 **21.39/21.85ms** versus **21.79/22.87ms**; class-component loop P90 **13.56/13.74ms** versus **13.99/14.36ms**; V8.5 drops **31/33** versus **35/46**. Capture-age P90 is **61.04/62.99ms**, still above the 60ms freshness window. Exact stale-pause counts are not included in the measured replay artifacts. This is a narrow, repeatable local performance gain with unchanged outputs, not an Active pass or perception-quality claim. See `output/analysis_v86_autoloop/iteration_0025/iteration_manifest.json` and `measured_paired_comparison.csv`.


## Iteration 0026 - measured stale-event totals

Measured Replay now drains and counts Scheduler `input_paused/stale_capture` and `disarmed/stale_timeout` records after each observe/decide interval is timed, and once at the end. `processing_ms` remains the previously captured `observe_ms + decision_ms`; no Scheduler policy or Engine behavior changed. The full suite passes **52 tests**.

Across two full 3,159-frame measured A/B runs on the same recording, V8.5 had **63/64** stale pause events and **1/1** stale-timeout disarms. Processing P90 was **39.53/39.46ms**; capture-age P90 was **61.41/62.53ms**, still beyond the 60ms safety window. Legacy had 230/231 stale pauses and no timeout; V8.4 Segmented had 246/246 and no timeout. All runs report zero duplicate press UIDs, unreleased presses, key-up failures, and illegal keys. The remaining freshness failure prohibits an Active recommendation. See `output/analysis_v86_autoloop/iteration_0026/iteration_manifest.json`.


## Iteration 0027 - lane-ROI class masks (rejected)

The class-mask ROI experiment reduced intermediate dimensions but initially lost the frame-655 yellow Tap at the top boundary: the 2px recovery padding fell above the ROI and became a negative local slice. Clamping the recovery source and adding a regression restored exact masks and component records on frame 655. The repaired full fixed 3,159-frame action, decision, candidate, and safety files are byte-identical to iteration 0025; frames 97/173 and 294/360/894 also match by every mask hash and component record.

The two measured ROI runs were slower and less fresh than iteration 0026: V8.5 processing P90 **40.12/40.26ms** vs **39.53/39.46ms**, drops **36/33** vs **31/30**, and capture-age P90 **62.52/63.04ms** vs **61.41/62.53ms**. The ROI mask rewrite was reverted to the exact iteration-0025 source. Its top-edge Tap recovery regression and outside-domain test remain; full suite after rollback is **54 passed**. Raw failed and repaired runs plus the measured rejection are in `output/analysis_v86_autoloop/iteration_0027/`.


## Iteration 0028 - HSV channel views (rejected)

Using strided HSV channel views kept all five real-frame mask hashes and component records exact, and the full fixed action/decision/candidate/safety hashes matched iteration 0025. It saved about 0.16ms from HSV conversion but increased class-mask setup P90 from 1.71/1.62ms to 4.84/3.96ms. V8.5 segmentation P90 rose from 20.97/20.88ms to 23.58/22.77ms; measured processing P90 became 41.78/41.19ms with capture-age P90 67.17/64.41ms, drops 44/34 and stale pauses 82/90. The change was reverted. The stride-equivalence test remains; full suite after rollback: 55 passed. See `output/analysis_v86_autoloop/iteration_0028/`.


## Iteration 0029 - HSV inRange masks (rejected)

The inRange experiment changed class-mask setup without changing any binary mask or ordered component record on 320 same rectified frames. It did not create a reproducible speed improvement: paired segmentation mean was 9.0085ms baseline vs 9.0312ms candidate; P90 was 12.7489 vs 12.4635ms. Class-mask/effect work regressed. Full measured runs were mixed: V85 compute P90 39.636/33.579ms, capture-age P90 60.798/52.982ms, drops 34/19, stale pauses 66/133, and one stale-timeout disarm in each. Both runs used the same capture/acquired timestamps, 1-124s arm window, geometry/timing hashes, measured compute clock, latest-frame admission, and mock actuator; decode and video encoding were excluded. The second run is not a pass because stale pauses doubled. Fixed full-replay output hashes matched the baseline. Candidate code was reverted to the exact baseline SHA. See output/analysis_v86_autoloop/iteration_0029/iteration_manifest.json and paired benchmark. Status remains **OFFLINE_NOT_PASSED**.


## Iteration 0030 - pre-loop component gates

The per-class loop now vectorizes only the cheap size and neutral-shape gates before processing retained labels in the same ascending order. All five audited real frames (97, 173, 294, 360, 894) retain exact masks and ordered component records. Two 320-frame same-rectified-frame benchmarks, with the second run reversing call order, both show lower class-loop mean and P90: 4.866/8.660→4.595/8.449ms and 5.255/9.188→5.025/9.064ms. Total segmentation mean improved in both, while total P90 improved in one and slightly regressed in the other; therefore only a narrow stage gain is retained and no robust whole-segmentation P90 claim is made. The full fixed 14ms replay's actions, decisions, candidates, and safety audit are byte-identical to iteration 0028 (343/221/186 Mock actions).

Two full measured repeats returned V85 compute P90 34.46/35.40ms, capture-age P90 53.83/54.74ms, drops 19/20, stale pauses 61/59, and one stale-timeout disarm in each. The iteration-0026 historical baseline was 39.53/39.46ms compute P90 and 61.42/62.53ms age P90, but Legacy and Segmented also measured faster in the new runs and admitted different frames. Those large deltas are host/sample affected and are not attributed wholly to this edit. Mock pressed counts 47/43 are descriptive only, not note recall. All 55 tests passed. Physical-note truth is still UNKNOWN and OFFLINE_NOT_PASSED remains the status. See output/analysis_v86_autoloop/iteration_0030/iteration_manifest.json.


## Iteration 0031 - Tap recovery copy elimination

Tap panel recovery now passes bool class masks to OpenCV through 0/1 byte views and reuses bool views for observed pixels, removing conversions that copied arrays. On all 320 paired recording frames, masks and ordered component records matched iteration 0030 exactly. In two 312-frame timing pairs with reversed starting order, Tap recovery mean/P90 decreased from 2.201/3.498 to 2.097/3.385ms and from 2.684/3.678 to 2.484/3.476ms. The whole segmentation total was mixed, so this is retained only as a repeated local-stage gain. Five audited frames also match exactly.

The full fixed 14ms Replay remains byte-identical at 343/221/186 Legacy/Segmented/V8.5 Mock downs, with zero illegal keys, duplicate press IDs, unreleased presses, or key-up failures. Two full measured runs yielded V8.5 processing P90 38.209/38.315ms, capture-age P90 57.932/58.508ms, P99 age 86.302/84.329ms, 28/25 dropped frames, 62/61 stale pauses, and one stale-timeout disarm in each. Source capture interval P90 is 41.224ms, so processing P90 is below that budget but P99 still exceeds it; stale disarms and large-tail freshness persist. All 55 tests pass. The Mock press counts are not note recall. Physical-note ground truth is still UNKNOWN; status remains **OFFLINE_NOT_PASSED**. See output/analysis_v86_autoloop/iteration_0031/iteration_manifest.json.


## Iteration 0031 long-tail diagnosis

Two rare spikes dominate the P99 tail: source frame 898 shows a 247ms V85 per-note loop in both full measured runs, and frame 1737 shows a 295-301ms V85 effect-component loop. Neither spike reproduced in source-pixel and diagnostic-only replay checks. At frame 898, the same V85 diagnostic pass processed 64 notes in a 6.94ms loop; the slowest note was 0.50ms and the maximum single-note snapshot section was 0.0063ms. The tagged ~79.7ms generation-2 GC at that frame belonged to V8.4 Segmented, not V85. At frame 1737, the same pixels produced a 1.14ms effect loop in a three-provider diagnostic; no GC callback was tagged to that frame. The data does not prove whether the full-run spikes came from OS scheduling, external host load, or another runtime pause. They remain UNRESOLVED_WITH_EVIDENCE, and their measured capture-age/stale effects remain in the results. See output/analysis_v86_autoloop/iteration_0031/outlier_diagnostic.md.


## Provisional case review and max-cost window

The current-source review renderer regenerated 15 sequential source-indexed clips and previews, one per available attribution/performance bucket plus Assist frames 294, 360, and 894. Their statuses are PROVISIONAL_VISUAL_AUDIT and physical UNKNOWN; no clip is labeled human-reviewed. The 4.9s/6.0s Assist frames show a green clipped ribbon whose visible body and broad caps are separated as current-frame components, but top-end ownership and persistent ID are not proven. Frame 894 maps to source frame 1086 and shows overlapping colored ribbons, panels, and flash; many fragments remain UNKNOWN rather than being forced into Tap/Hold. See output/analysis_v86_autoloop/iteration_0031/provisional_visual_audit.md and current_case_windows/review_queue.csv.

The same review selected a more severe slowest case at frame 2774: 397.78ms total with 362.78ms in the 62-note decision loop; repeat 2 has an adjacent frame 2781 spike of 411.94ms / 380.02ms. In a note-profile diagnostic, those frames replayed at 35.98ms / 19.01ms, with slowest-note iteration 0.31ms / 0.15ms and no GC callback. This further supports an unresolved process/host stall rather than a stable heavy note computation; it remains included in full measured P99 and stale behavior. See output/analysis_v86_autoloop/iteration_0031/outlier_diagnostic.md.


## Measured replay mode confound (iteration 0031 follow-up)

A full three-provider rerun with each provider in a fresh Python process produced Baseline/Segmented/V85 Mock downs 342/191/155, with no stale-timeout disarms. V85's standalone runs (three repeats) press 155/156/155; prior `--mode compare` V85 runs press only 46/45 because both hit the same stale-timeout at scheduler time 1295.29093 s. All compare downs occurred before that disarm; separate runs produce another 107?109 downs afterward. On identical frame 898, compare V85 took 269.58?273.20ms, versus 23.28?33.52ms across isolated runs. The compare CLI runs V85 last after accumulating Legacy and Segmented rows, so its measured timing is confounded by process/order; retained data is a plausible but unproven cause of the extreme runtime pause. See `output/analysis_v86_autoloop/iteration_0031/replay_mode_discrepancy.md` and `isolated_replay_check/matrix_summary.csv`. Use the isolated runs for measured feasibility and the unchanged full 14ms replay for algorithmic A/B. Physical-note truth remains UNKNOWN; action counts are not recall. Status remains OFFLINE_NOT_PASSED.


## Iteration 0032 - Hold terminal-cap scan optimization

The Hold terminal-cap classifier now avoids per-row NumPy index arrays and repeated median/extrema scans by using equivalent row endpoints, incremental extrema, and a sorted width list. On two reverse-order pairs over 312 timed frames from the real recording (1400-1719), every mask and ordered component record was identical; class-loop P90 fell 11.70/11.99 to 9.80/9.99ms and whole segmentation P90 fell 18.28/18.76 to 16.68/16.63ms. The full 14ms replay's semantic artifacts remain byte-identical to the previous candidate (343/221/186 Mock downs, all safety counts zero).

Two process-isolated measured matrices show V85 P90 36.88/36.59ms, P99 45.34/44.87ms, capture-age P90 56.88/56.57ms, P99 80.76/78.50ms, 14/14 drops and 359/336 stale pauses. This improves on the immediately preceding isolated two-run matrix (P90 38.56/38.49ms, 19/17 drops, stale pauses 417/417) under the same source, arm, geometry, timing and birth-zone settings. Stale pauses and capture-age tails still fail the practical gate. V85 Mock actions 160/163 are descriptive only; no physical-note GT exists. Runtime stage spikes up to 167-170ms still appear and remain unexplained. 55 tests passed and compileall passed. See `output/analysis_v86_autoloop/iteration_0032/iteration_report.md`. Status remains **OFFLINE_NOT_PASSED**.


## Iteration 0039 — repair the neutral-fragment identity audit

The previous iteration-0037 grouped audit counted only 146 rows from a source trace containing 333 `suppressed_occluded_fragment` events, and its UID column held a literal placeholder. It was not sufficient evidence for a trajectory conclusion. A new trace utility now writes one record per suppression and matches v85 rows only within the same video frame and Tap-face geometry. It mirrors both geometric clauses in the adapter rule; it does not infer cross-provider identity or physical-note truth.

The corrected artifact accounts for all **333** candidate rows across **306** frames. Same-frame+bbox matching against the 0034-source baseline trace shows **203** bottom-bevel rows were already suppressed there; the exact 12×8 change adds **130** candidate-only rows, with zero baseline-only rows. Of the 130 new rows, 127 have one eligible Tap face and three have multiple eligible parents left ambiguous. Among 330 uniquely mapped same-frame tracker inputs, 284 have a provider-local UID and 46 are unassigned. Those rows include 254 confirmed tracker inputs and 87 scheduled presses; these are internal state counts only.

No perception or scheduler behavior changed. The corrected audit does not prove that the pixels physically belong to the Tap face or that suppression improves note quality. Status remains **OFFLINE_NOT_PASSED**. Details and hashes are in `output/analysis_v86_autoloop/iteration_0039/iteration_manifest.json`; per-fragment records are in `neutral_fragment_identity_audit.csv`.


## Iteration 0040 — corrected Legacy-action event pairing

The attribution tool previously selected the nearest action on a matched candidate track without a time limit. On the same 3,159-frame fixed 14ms replay, 19 nearest events were more than 80ms away from the Legacy event. Ten Segmented and two V8.5 rows had been labeled different-key vs Legacy; two more Segmented and five V8.5 rows had been labeled same-key action-present. The updated tool only pairs within an **80ms auxiliary diagnostic window** and retains farther nearest events as separate evidence. This does not estimate hit rate or physical-note recall.

Re-attribution of 343 Legacy presses produced Segmented counts of 155 same-key paired actions, 32 different-key paired actions vs Legacy, 91 track-association-unverified, 24 not active at reference frame, and 41 other stages. V8.5 counts were 104, 15, 146, 19, and 59 respectively. A different-key pair is not a verified physical error; cross-version candidate matching remains provisional, so action pairing totals are diagnostic, not physical-note error counts. The full suite passes **61 tests**.

Three source frames (1756, 2124, 2199) were sequentially decoded and aligned to the index. Each suppressed 12×8 region lies inside two Tap-face boxes and contains mixed Tap-face/UNKNOWN mask pixels; owner remains unresolved. No perception or Scheduler behavior changed. Measured stale and freshness problems remain; status remains **OFFLINE_NOT_PASSED**. See `output/analysis_v86_autoloop/iteration_0040/iteration_report.md` and its manifest.


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


## Iteration 0053 ? Assist Hold lifecycle replay

A full fixed 14ms replay of the same 1,149-frame Assist source produced 30/38/37 Legacy/Segmented/V8.5 Mock downs. At source frame 360, Segmented and V8.5 saw the same Hold-head bbox, but only Segmented owned a terminal cap; V8.5 later used `hold_hard_timeout`. Counts are diagnostic Mock actions, not physical-note recall. The runtime change was not yet present.

## Iteration 0054 ? exact-frame Hold endpoint ownership repair

The V8.5 frame-360 head and tail were same-color green components in one exact-frame `connection_group_id`, but the Note's persistent birth color was `neutral`. Tracker compared the tail against that stale field and rejected the unique connection. Tracker now compares with the current-frame Hold-head Detection color while keeping the group frame-local, uniqueness-gated, and bounded by repeated full observations. No Scheduler safety gate changed.

In a full fixed 14ms Assist A/B, V8.5 Mock downs changed 38?39; the same `note:16` J press released at 759290.4938439 with `tail_release`, replacing the prior 759296.3638438 hard timeout. Legacy/Segmented/V8.5 after-fix downs were 30/40/39. This verifies one endpoint lifecycle, not physical-note recall. V8.5 P90 was 32.22ms versus Segmented 23.27ms; this run does not update measured stale/drop performance for the changed runtime. Five focused and 89 full tests pass. The overall decision remains **OFFLINE_NOT_PASSED**, and Live Active is not recommended. See `output/analysis_v86_autoloop/iteration_0054/iteration_report.md`.


## Iteration 0055 ? full fixed and measured A/B for runtime 0054

The full 3,159-frame recording was replayed with 14ms fixed synthetic latency and in a separate two-repeat, fresh-process measured latest-frame matrix. All six measured runs matched capture/acquired timestamps against the source index within 1e-9s. Fixed-delay Mock downs were Legacy/Segmented/V8.5 342/294/259; they are not physical-note recall.

Measured V8.5 P90 was 37.64/37.57ms, P99 45.40/45.94ms, with 22/21 drops, 379/375 stale pauses and one stale-timeout disarm each. Segmented P90 was 27.37/28.89ms, one drop per run, and no stale-timeout disarms. Compared with runtime 0049, V8.5 P90 rose from 18.72/18.87ms, drops rose from 9 to 22/21, stale pauses rose from 231/230 to 379/375, and each new run had a stale-timeout disarm. The regression is confirmed but not attributed to a specific runtime stage. Full test result remains 89 passed; no code changed in this validation iteration. Status is **OFFLINE_NOT_PASSED**; do not enable Live Active. See `output/analysis_v86_autoloop/iteration_0055/iteration_report.md`.
