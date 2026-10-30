# V7 cleanup and deletion matrix

| Item | Action in this iteration | Reason / status |
|---|---|---|
| New duplicate Tap retention layers | None added | Simple intent ownership does not depend on tracker loss to retain an accepted action |
| V6 provisional/dropout/edge/identity retention methods | Retained | V6 stays available for comparison and rollback; deleting before independent note review would remove the baseline |
| V6 Tap scheduler ownership | Still present in `v6` mode | Needed for A/B replay and rollback; not called by Simple intents because they use a separate event-ID namespace and manager |
| Particle identity logic in `tracker.py` | Retained for V6 | Simple Tap mode does not use it; Hold still uses the existing tracker route |
| PF source code | Retained | C comparison requires the predictor under the same Simple control core |
| PF/high-frequency diagnostic writers | Retained in V6 | Runtime trace reduction is deferred until the final core is selected |
| Old configuration keys | Retained | Migration/removal waits for final predictor/core selection; existing config continues to load |
| Geometry, 720×404 scaling, 15 px advance, 310.5/325.5 targets | Unchanged | Explicit V7 constraints |
| Runtime `output/` artifacts | `.gitignore` now excludes runtime children except `output/README.md`; exact real run was backed up and `git rm --cached` was staged for its 15 files | Source evidence remains locally in `output/run_20261030T132141_738544Z` and in Downloads backup; no commit/push/history rewrite |
| Legacy tests | Retained | They protect current V6 and Hold behavior while the new path is evaluated |

Nothing was deleted from the real run directory. The index change is local and staged; it has not been committed or pushed.
