# V7.14.7 timing bottleneck baseline

Run: `C:\Users\USER\Desktop\holodream\output\assist\v7147_baseline\run_20261103T054928_927271Z`
Scope: offline diagnostics; no Active config was changed.

## Input/schema audit
- Missing required columns: `{'tap_intents.csv': [], 'tap_decisions.csv': [], 'input_actions.csv': [], 'global_tap_timing_shadow.csv': []}`
- All timestamps are parsed as the run's monotonic capture/processing seconds; blank or non-finite values are not converted to zero.

## H1 evidence
- Explicit `amend_earlier_disabled` transition events: **0**.
- Explicit event UIDs: **0**.
- Inferred earlier ETA candidates (not explicit rejections): **1440 rows / 155 UIDs**.
- Inferred candidates passing future/epoch/key/availability/freeze/step/total checks: **1392 rows / 142 UIDs**.
- Inferred earlier delta P50/P90: **-19.78482847334817 / -4.081568616675211 ms**.
- Inferred safe earlier delta P50/P90: **-15.901933031273074 / -2.7916300779906944 ms**.
These inferred rows show that a newer ETA was earlier than the recorded deadline; they do not prove the live manager rejected it, because this run predates the new diagnostic fields.

## Deadline and input timing
- Amendment actions: **347**; amendment delta P50/P90: **2.3832716688048095 / 23.038651380920783 ms**.
- Tap key-down minus final deadline P50/P90: **1.8236074392916635 / 3.461415859055706 ms** (execution offset, not game grade).
- UID classifications: `{'SCHEDULED_BUT_SLOW_UNKNOWN': 248, 'NO_INPUT': 13, 'UNRESOLVED': 156, 'LATE_ESTIMATE': 5}`.
- `press_time_not_future` and `eta_outside_horizon` are gate/estimate counts; they are not MISS counts.

## Go / No-Go
**NO-GO for Active enablement from this run alone.** Explicit earlier-disabled rows are absent, and no game-grade truth exists. The inferred candidates justify a controlled Shadow/A-B experiment, but not a claim of improvement.

## Example cases
`v7147_earlier_examples.csv` contains 20 timestamped UID examples (up to 20), including old deadline, proposed press time, delta, key and epoch.

## Interpretation
A/B group B can be prepared with allow_earlier_amend=true, but it must remain opt-in. Compare only identical song segments with human one-to-one game grades; otherwise report UNKNOWN/INSUFFICIENT_GROUND_TRUTH.
