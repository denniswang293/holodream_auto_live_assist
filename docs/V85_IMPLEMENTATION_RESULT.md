# V8.5 Implementation Result

Date: 2026-11-15. **Acceptance: not passed; keep V8.5 offline and keep Active on Legacy.** No OS key injection occurred. Scheduler limits, Live default, geometry and timing calibration were not modified.

## Implemented

- Added `EarlyPixelProvider` as an offline-only provider, preserving source-pixel semantic evidence through Tracker input.
- Added immutable birth provenance, pending semantic type, visible/occluded/ambiguous visibility states, and global one-to-one Hungarian assignment with unmatched options. Missing frames do not advance `last_seen` or fabricate observations.
- Added conservative Tap short-occlusion eligibility, pending-type rejection, unique Hold tail ownership diagnostics, and stale tail evidence rejection for release updates. Existing Scheduler bounds remain authority.
- Segmentation now represents neutral pixel candidates as UNKNOWN, isolates color classes, preserves observed Hold body/head/tail pixels, recovers current-frame panel cores without rectangular fill, and skips impossible large neutral component geometry while retaining those pixels in UNKNOWN.
- Added local real-frame fixtures with source provenance, synthetic pixel tests, attribution and reporting tools, complete fixed-delay/measured-time replay outputs, and continuous candidate review clips.
- Fixed review rendering to decode sequentially from frame zero; MP4 random seek did not reliably align source frame number with the timestamp index.

## Results

The same-source 3,159-frame fixed 14ms replay produces 343 Legacy, 213 V8.4 Segmented, and 199 V8.5 Mock key-downs. The 14ms value is only the shared synthetic processing delay. Component pruning did not change any action totals. V8.5's fixed-mode measured host compute after pruning is 39.81ms mean / 53.88ms P90; measured compute does not alter the fixed logical clock.

The separate measured-time V8.5 repeat processes 3,048/3,159 frames and drops 111 with the latest-frame admission rule. Its mean/P90 compute is 35.28/46.89ms, compared with 17.01/24.15ms Legacy and 30.54/41.95ms V8.4 Segmented in that repeat. It emits 39 V8.5, 339 Legacy, and 141 Segmented Mock key-downs. Logged stale-capture pause events in this repeat are Legacy 231, Segmented 620, V8.5 202; the previous measured pass recorded 235, 405, 139. The prior V8.5 pass emitted 34 presses and dropped 150 frames; host variation exists. Both repeats show V8.5 slower and dropping more frames than Legacy and Segmented. There is no evidence to claim live feasibility.

The per-Legacy-action fixed replay attribution totals 343: 116 same-key V8.5 Mock action; 29 wrong-key V8.5 action; 49 Engine eligibility gates; 8 Timing gates; 13 track-confirmation gates; 5 pixel UNKNOWN roles; and 123 unresolved after tracking/observation. The unresolved class is not force-assigned. These are cross-provider geometric trajectory associations, not reviewed physical-note recall.

The full four-run automatic scan has 13,128 candidate tracks and 2,966 automatically confirmed tracks. The provisional geometric birth-zone boundary is y=176.75; it is not validated by human-reviewed true-note labels. Yellow Hold candidates were rare and none were confirmed in the two recording runs; most neutral face candidates remain type-pending. These are concrete acceptance failures for the requested early yellow Hold/gray-note behavior. The V8.4 vs V8.5 masks at 4.9s, 6.0s, and 14.9s are visually near-identical; the delivered comparison is genuine and time-aligned but does not show a visual-quality gain.

## Validation

- `python -m compileall -q src tools tests`: passed.
- `pytest -q`: 20 passed, including observed-pixel, yellow Hold endpoint, neutral UNKNOWN, two independent Hold + Tap, global assignment, immutable birth identity, short occlusion, and pending-type safety checks.
- Fixed and measured replay Mock audits found zero illegal keys, duplicate press UIDs, key-up failures, or press UIDs lacking a release.
- All six review windows retain identical source-frame SHA-256 between the verified before/after candidate renderers. The review renderer now decodes sequentially because random seeking was shown to mismatch indexed source timestamps. Review queue labels remain `NOT_HUMAN_REVIEWED` and physical note/head/tail owners remain UNKNOWN.
- Final fixed and measured summaries, P50/P90/P99 stage latency, action attribution, identity ambiguity flags, and tail-owner rows are stored under `output/analysis_v85_early_identity/`.

## Remaining risk and release decision

The action count remains far below Legacy and the Segmented provider. V8.5 has material wrong-key actions, excessive pending/observation-loss cases, poor measured-time admission, no reviewed physical-note labels, no confirmed yellow Hold population, and no verified head/tail owner truth. The candidate scan count cannot establish recall or precision. Keep V8.5 disabled in Live. The next valid acceptance step requires human review of the supplied small continuous windows, followed by targeted corrections and repeated A/B; do not loosen Scheduler safety bounds to mask these failures.

Cleanup candidates are documented in `V85_CLEANUP_MANIFEST.md`, but the execution policy rejected deletion commands (including a disposable pytest-cache file). No candidate was deleted, and I did not switch to another mechanism to bypass the block. The manifest records the exact paths and sizes. See `V85_EARLY_IDENTITY_DESIGN.md`, `V85_EVALUATION.md`, and `V85_CLEANUP_MANIFEST.md` for design, protocol/results, and cleanup status.

## Continuation status (2026-11-16, iteration 0088)

A real Assist frame exposed an adapter leak: frame 894/source 1086's green Hold group 25 head had `below=80` because a separate overlapping yellow group 47 was present in the global Hold-mask union. Endpoint extent now comes from the exact same-group local Boolean ROI, and ambiguity provenance is preserved. The real frame changed to `below=0`; segmentation mask previews/videos remained byte-identical, as expected for an adapter-only fix. A per-frame before/after table is in `output/analysis_v86_autoloop/iteration_0088_hold_group_extent_repair/assist_endpoint_extent_before_after.csv`.

Two final measured-time repeats processed all 3,159 frames with no drops and 226 stale pauses. V85 compute P90 was 25.67/27.02ms; fixed 14ms Mock downs remained 342/294/259 (Legacy/Segmented/V85), with no hard-safety failures. One V85 Hold release moved 4ms earlier; no additional Mock press was created. The full suite passed 103 tests. Updated action attribution still has 122 `TRACK_ASSOCIATION_UNVERIFIED` cases, and physical note truth remains UNKNOWN. Do not activate V85; the three priority Assist labels still require human review. Full evidence is in the 0088 report and manifest.


## Continuation status (2026-11-16, iteration 0069)

The current runtime candidate remains iteration 0061 and V8.5 remains **OFFLINE_NOT_PASSED**. The iteration 0067 Tap-recovery profile and iterations 0068-0069 segmentation trials did not establish an overall improvement; both code candidates were reverted. Iteration 0069?s occupied-bounds CCL crop preserved role masks but changed ordered component records on 21/32 sampled frames and increased mean/P90 segmentation time from 16.759/21.878 ms to 16.998/21.940 ms. The full suite passes (95 tests) on the restored source; the 0069 candidate also passed its focused 23-test pixel suite. No full replay was run for that rejected trial. Physical-note labels remain not human reviewed, so recall and gameplay correctness remain unverified. See `output/analysis_v86_autoloop/iteration_0069_ccl_trial/report.md`.


## Cross-session review queue (2026-11-16)

The review set now covers 11 continuous candidate clips across two separate recording sessions, with Tap, green Hold, pending yellow/neutral candidates, effects/near-hit fragments, and simultaneous Hold candidates. Session B uses the same provisional birth-zone boundary (176.75 px); exact run/index joins and source-frame pixels were checked. A yellow-Hold row is explicitly `NOT_FOUND_IN_SCANNED_RUNS` in Session B; it is not a negative physical-note label. All cases remain `NOT_HUMAN_REVIEWED`, and IDs/owners remain `UNKNOWN`. The review index, blank response template, and per-session render manifest are linked in `output/analysis_v85_early_identity/cross_session_review_index.md`. Physical-note recall and Hold-owner accuracy therefore remain unscored.


## Segmentation timing trial (2026-11-16, iteration 0070)

A read-only HSV channel-view candidate preserved every sampled mask/component/counter but made total segmentation slower on all 32 sampled frame means (9.013 to 10.289 ms), despite reducing the HSV conversion substage. The candidate was reverted. The current runtime candidate remains iteration 0061; the segmentation and measured-time gates remain unmet. See `output/analysis_v86_autoloop/iteration_0070_hsv_views/report.md`.

## Continuation status (2026-11-16, iteration 0089)

Added deterministic `MockActuator` regression coverage for five existing Scheduler safety boundaries: unfocused frame arm rejection, focus-loss and `stop_hotkey` release/disarm, rejection of a Hold beyond the 9-second hard timeout, and release at stale capture followed by disarm at the existing timeout. No runtime or safety behavior changed. Focused tests pass (5), full suite passes (108), and compileall passes. No OS input was sent. Human physical-note truth remains UNKNOWN, 122 cross-provider attribution rows remain unverified, latest Replay/performance evidence remains iteration 0088, and V85 stays offline with Live on Legacy. See `output/analysis_v86_autoloop/iteration_0089_safety_boundary_tests/iteration_report.md`.

## Continuation status (2026-11-16, iteration 0090)

Removed four stale or unsafe cleanup helper groups after checking their targets and references; in particular, the broad oversized-file helper that could delete protected Assist-run inputs is gone. Then ran a full post-cleanup fixed 14 ms Replay over 3,159 frames. Mock downs remain 342/294/259 with all hard safety counters zero, and six semantic outputs hash-match the 0088 canonical run. Full tests pass (108), both Replay `--help` commands and import smoke pass. This fixed-latency run does not replace measured-time results or prove game accuracy. Two duplicate 0088/0090 CSV pairs remain pending the hash-guarded handoff because direct deletion was rejected; raw sources remain untouched. Physical labels and 122 cross-provider associations remain unverified; V85 stays OFFLINE_NOT_PASSED and Live stays Legacy. See `output/analysis_v86_autoloop/iteration_0090_cleanup_audit/iteration_report.md`.

## Continuation status (2026-11-16, iteration 0091)

Rebased the 0086 exact-frame Tracker refinement onto the current 0088 attribution. The old trace, decompressed, is byte-identical to the complete 0090 candidate trace; all 122 case IDs and frame/key/Legacy-box/V85-local-UID fields match exactly. This provides current algorithm-stage detail: 65 nearest components are evidence-only (33 effects/artifacts, 32 Hold bodies), 35 accepted components went to another provider-local UID, 20 were left ambiguous, and 2 had no spatial component. The original 122 rows stay `TRACK_ASSOCIATION_UNVERIFIED`; no physical owner, miss, or ID switch is inferred. See `output/analysis_v86_autoloop/iteration_0091_tracker_rebase/iteration_report.md` and its joined CSV.

## Current continuation status (2026-11-16, iterations 0092–0095 and staged timing audit)

The later Tracker investigations narrow, but do not resolve, the 122 current cross-provider action associations that remain `TRACK_ASSOCIATION_UNVERIFIED`. Exact edge traces show Tracker competition/rejection states; spatially missing frames 1787 and 2715 have no Tap/Hold role component inside the relevant Legacy boxes. The available source/mask windows do not prove the physical owner, so no segmentation threshold or send-key gate was changed on those cases. Detailed counts and images are in `docs/V86_EVALUATION.md` and the 0092–0094 iteration folders.

The 0095 six-case review packet covers Assist 4.9s, 6.0s, 14.9s and three loss/identity cases. Its physical presence, type, key, visibility, and owner labels remain UNKNOWN pending human review. The CSV is review-ready and hashes its media; automated masks and provider UIDs are not labels.

`output/analysis_v85_early_identity/baseline_vs_candidate.csv` now consolidates six fixed-delay/measured-time comparison rows with separate clocks and source CSV provenance. `early_confirmation_stage_metrics.csv` summarizes 13,128 automatically proposed candidates, 2,966 automatic confirmations, 4,802 exact replay-UID joins, and 202 rows with replay-log first-commit timestamps. These are detector/tracker statistics, not true-note recall. Candidate-to-confirmation y/time deltas are available; candidate-to-schedule displacement is `NOT_AVAILABLE_IN_METRICS`, and every group remains `NOT_EVALUABLE_AUTOMATIC_TRACKS_ONLY`.

The duplicate large CSV cleanup targets were already absent at the latest recheck. This continuation removed only the regenerable `src/__pycache__/` through the allowlisted cleanup BAT and recorded the result in `V85_CLEANUP_MANIFEST.md`. README links the consolidated comparison and focused review packet. No runtime source or safety behavior changed in this continuation. The full suite now passes 111 tests, including 3 focused synthetic tests for the summary utility. No Replay was rerun in this documentation/analysis continuation; the last recorded full fixed Replay and hash-equivalence remain in iteration 0090. V8.5 remains **OFFLINE_NOT_PASSED**, Live remains on Legacy, and no OS input was sent.
