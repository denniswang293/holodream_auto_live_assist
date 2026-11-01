# V7.8.9 safety regression

- Legacy remains the only real input path.
- PF-assisted reassociation remains Shadow/offline-only; no actuator, Planner or Scheduler call is made by this audit.
- No detector/tracker/PF gate, Hold ownership, Focus/ROI/stale/manual arming or ESC/F12 rule was changed.
- Shadow input actions: 0. Game judgment: UNKNOWN.
