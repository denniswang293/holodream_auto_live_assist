# V7.14.7 A/B comparison

Status: **INSUFFICIENT_GROUND_TRUTH**

This comparison separates internal timing metrics from manually labelled game grades. key_down/FIRED/Combo are not game accuracy.
The experiment differs from baseline only by `allow_earlier_amend`; lead remains 60 ms and all safety limits remain unchanged.

## Runs
- baseline: `output\assist\v7147_baseline\run_20261103T054928_927271Z`; variant `baseline`; lead `60.0 ms`; earlier `False`; Tap key-down 186; amendments 347 (earlier 0, later 347, P50 delta 2.4716697516851127 ms); grades 0/186; SLOW rate `UNKNOWN`.
- experiment: `output\assist\v7147_experiment\run_20261103T055219_493952Z`; variant `experiment`; lead `60.0 ms`; earlier `True`; Tap key-down 183; amendments 1722 (earlier 779, later 943, P50 delta 0.3189982962794602 ms); grades 0/183; SLOW rate `UNKNOWN`.

## Acceptance rule
Only if the same song segment has at least 30 one-to-one trusted labels per group may SLOW/MISS/FAST rates be compared. Otherwise the result stays INSUFFICIENT_GROUND_TRUTH and only internal timing metrics are reported.
A failed or unsafe experiment must keep the baseline config; do not write the experiment setting into config/live_assist.json.
