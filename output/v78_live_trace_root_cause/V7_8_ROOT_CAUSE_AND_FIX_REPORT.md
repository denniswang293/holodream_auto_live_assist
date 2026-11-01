# HoloDream V7.8 Live Trace Root Cause and Fix Report

- Source run: `C:\Users\USER\Desktop\holodream\output\run_20261031T201055_348946Z`
- Source SHA manifest: `v78_manifest.json`
- Trace coverage: 1094 frames with submitted telemetry rows out of 1202 processed frames; 108 frames had no submitted diagnostic row. This is not automatically data loss.
- Trace rows: candidate=58965, association=57775, track=7358; health submitted/written=124098/124098; dropped=0.

## UID funnel

{'FIRED': 50, 'DETECTED_ONLY': 121, 'CONFIRMED_NOT_FIRED': 24}. These are software UID groups, not physical-note count or accuracy.

## Root-cause classification

{'KEY_DOWN_LOGGED_GAME_TRUTH_UNKNOWN': 50, 'TRACK_COAST_TIMEOUT': 115, 'NOT_ENOUGH_OBSERVATIONS': 17, 'eta_outside_horizon': 3, 'below_event_min_y': 7, 'particle_posterior_too_wide': 3}. Each row includes evidence, counterevidence, frame, timestamp, candidate/track references and confidence in `uid_root_cause_195.csv`. `track_not_current_confirmed` is not used as a complete root cause.

## Physical review

The review corpus contains 40 local cases: {'pink_candidate': 10, 'neutral_candidate': 13, 'cyan_bar': 16, 'yellow_bar': 1}. They are all `UNREVIEWED` and game judgment is `UNKNOWN`; the local IDs are not official game IDs. Pink is treated as ordinary Tap. Contact crops are in `case_crops/`.

## Patch decision

`PATCH_NOT_JUSTIFIED`: no two HIGH-confidence, manually verified physical notes with the same irreversible blocker are available. No Detector/Tracker/PF/Planner/Scheduler/Hold threshold was changed, no Active Shadow path was enabled, and no FPS/drop policy was changed.

## Next single user action

Review `physical_notes_review.csv` and the corresponding `case_crops/` adjacent frames, filling only physical_note_id, reviewer_status, confidence and game_judgment. Do not change config or record another run yet.
