# V7.5.4 PR-0 Baseline

Commit: `947b7dc600fb4577591eebfea8c81a4537964503`
Run: `output\assist\run_20261031T181722_597143Z`

- 1,526 acquired / 1,443 processed / 83 dropped / 0 stale
- 248 unique DETECTED UID
- 95 ever CONFIRMED, 71 scheduled Tap, 70 FIRED, 1 EXPIRED
- Capture 58.25 FPS, processing 52.06 FPS, latency P95 30.58 ms
- Pink: 11 UID, 1 FIRED, 10 single-frame DETECTED

Timestamp alignment uses `source_video_frame -> capture_timestamp` from `live_video_index.csv`. No fixed 60 FPS substitution.

The baseline is diagnostic only. No game judgment labels are available, so all physical-note and hit fields remain UNKNOWN. Candidate-level detector rejection and pair-cost association data were not recorded in this run; those limits are preserved in `association_audit.csv`.
