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
