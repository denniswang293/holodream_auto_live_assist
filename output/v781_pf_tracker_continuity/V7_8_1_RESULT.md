# HoloDream V7.8.1 Result

- Baseline source: `C:\Users\USER\Desktop\holodream\output\run_20261031T201055_348946Z`
- Data status: `DATA_UNAVAILABLE`
- PF-assisted reassociation: implemented as a bounded Shadow proposal layer; config default is `enabled=false`, `mode=shadow`.
- Active Legacy Planner/PF path: unchanged.
- Pure PF prediction cannot create a candidate, observation, UID, keydown or Hold action.
- `FIRED`, `key_down` and software UID counts are not game accuracy.
- Active promotion: **NO**; minimum two manually confirmed lost→reacquired physical notes are unavailable.

## Code and rollback

The rollback is `pf_assisted_reassociation.enabled=false` in `config.json`; no active path reads Shadow proposals.

## Required evidence to continue

Restore or provide one clean source run with `live_video_index.csv`, the three trace CSVs, lifecycle CSVs and source video. Then run the same tool and manually label at least two physical lost→reacquired cases plus ten negative controls.
