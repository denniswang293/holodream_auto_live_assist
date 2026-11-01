# V7.8.4 Safety Regression

- PF rescue remains Shadow/offline-only; `config.json` defaults `enabled=false`, `mode=shadow`, `offline_only=true`.
- Targeted rows require a real `candidate_final`; no PF-only candidate, UID, key-down or Hold state is created.
- Legacy assignment is completed first; assigned candidates are negative controls and cannot be stolen.
- No frame acquisition, drop policy, Planner, Scheduler, Actuator, Focus/ROI/stale/disarm or Hold code path was opened by the offline analyzer.
- `input_sent` is false for all Shadow rows.
- All manual controls are `UNREVIEWED`; game judgment remains `UNKNOWN`.
