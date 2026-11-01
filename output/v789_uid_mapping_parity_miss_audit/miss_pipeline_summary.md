# Miss pipeline summary

- 18 CONFIRMED_NOT_FIRED software UIDs analyzed; this is not 18 proven game MISS.
- Primary blocker counts: `{'TRACK_NOT_CURRENT_CONFIRMED': 9, 'PLANNER_GATED': 9}`.
- Neutral/pink trace cases: `{'pink_candidate': 2, 'neutral_candidate': 8}`.
- Pink candidates are classified as ordinary Tap in this audit, not Flick.
- Gray/neutral candidates remain separate and are not assumed to be physical notes.
- `key_down`, `FIRED`, or software UID continuity do not establish game judgment; game accuracy remains `UNKNOWN`.
- The strongest actionable evidence is the recorded `track_not_current_confirmed` blocker and planner gates, but the source lacks complete serialized Tracker/PF state for causal proof.
