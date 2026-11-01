# V7.8.5 Safety Regression

- A is the Legacy replay; B is a separate tracker/PF instance.
- B only consumes real recorded `candidate_final` observations and cannot create a candidate, UID, key-down or Hold state from coasting.
- Shadow replay emits simulated transitions only; Planner, Scheduler and Actuator are not called.
- Focus/ROI/stale/disarm/ESC/F12, Hold ownership and key release are outside the offline replay and remain unchanged.
- All control cases are `UNREVIEWED`; game judgment is `UNKNOWN`.
