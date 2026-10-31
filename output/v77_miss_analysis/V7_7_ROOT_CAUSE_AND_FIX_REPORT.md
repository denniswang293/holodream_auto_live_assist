# HoloDream V7.7 Root Cause and Fix Report

## Executed

- Baseline run: `C:\Users\USER\Desktop\holodream\output\assist\run_20261031T194457_212618Z`
- Replay source: `live_source.mp4` with `live_video_index.csv` capture timestamps.
- Replay coverage: 1048 indexed video frames; candidate trace rows 49846; association rows 45868.
- Full pytest was run after the patch; see `pytest_v77.txt`.

## Baseline lifecycle (not accuracy)

- acquired=1253, processed=1052, dropped=201, stale=0.
- FIRED/key-down counts are recorded by the run, but game judgment remains UNKNOWN.
- UID first-blocker counts from existing lifecycle logs: `{'KEY_DOWN_SENT_GAME_JUDGMENT_UNKNOWN': 34, 'below_event_min_y': 23, 'NOT_ENOUGH_OBSERVATIONS_OR_TRACK_LOST': 63, 'ALREADY_PAST_TRIGGER': 3, 'hit_time_not_future': 1, 'particle_posterior_too_wide': 1, 'eta_outside_horizon': 1}`.

## Detector evidence

- Final replay candidate appearances: `{'cyan_bar': 5446, 'pink_candidate': 147, 'neutral_candidate': 508, 'green_candidate': 1439, 'yellow_bar': 920}`.
- Candidate rejection trace ranking: `{'edge_geometry': 2569, 'nested_suppression': 327, 'physical_roi': 486, 'edge_shape': 962, 'shape': 78, 'fill': 16}`.
- Gray, overlap and pink CSVs contain source frame, capture timestamp and candidate IDs; they are evidence rows, not physical truth.

## Root-cause status

No active detector/tracker/planner threshold patch is justified yet. The replay now provides candidate-level evidence, but the required physical_note_id and game judgment annotations are not present. In particular, a neutral candidate or a missing candidate cannot be called a true gray note without the contact-sheet review. `pending_calibration` geometry is also retained. No neutral/overlap experimental patch is enabled.

## Top priorities after review

1. Review all high-confidence gray rows in `physical_note_review.csv`; enable a local neutral experiment only if two or more real notes share the same documented detector blocker and negative controls remain clean.
2. Review overlap/nested rows against adjacent frames before changing NMS or association.
3. Pair visible notes with lifecycle traces before changing PF/Planner gates; never use FIRED as hit truth.

## Blockers

The current run was recorded with live identity telemetry disabled, so the offline replay was required. The provided geometry is pending calibration. Manual review is required before any Active repair.
