# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=310.5; physical track completion: y=325.5.
Processed frames: 3165; acquired/source frames: 3239
Frame/source FPS: 60.278; wall processing FPS: 58.257
Acquisition-to-decision latency P50/P95: 14.498/27.610 ms
Dropped frames: 74; stale frames: 0
Events: 208; abstentions: 80; actual key-downs: 128 (Tap 120, Hold 8)
Abstain reasons: {'selected_tap': 128, 'duplicate_hold_path': 12, 'past_hit_time': 15, 'unstable_hit_time': 37, 'hit_time_drift': 5, 'tap_key_conflict': 5, 'reidentified_same_physical_tap': 6}

Accuracy / Tap precision / recall / key accuracy / signed timing error: UNVERIFIED.
Live uses host perf_counter at capture start/end, not a verified GPU presentation timestamp.
No confidence value is a correctness probability. The user-confirmed Assist Hold rule presses one start key for configured green/yellow paths and releases after that color's visible tail leaves the judgment row; this visual heuristic is unverified against game judgments. Other unknown candidates receive one Tap attempt.
Key selection uses pinned manual singleton evidence or an explicit user-confirmed any-covered-key control profile; neither verifies recognition accuracy.
Explicit range-rule Assist can commit an already-confirmed Tap across the measured judgment-bar occlusion for at most 100ms; fresh PLAYING/focus/ROI context remains mandatory.
The input latch always starts OFF and requires an explicit user hotkey.
Live assist requires Ctrl+Shift+Alt+Q, modifier release, fresh frames, game focus, PLAYING, and one eligible selected key.
Esc/F12, stale capture, focus/ROI/game-state loss disarm and release keys; resuming does not re-arm.

If only the previous decision expires while a fresh frame is being checked, key-down pauses until its validated result; the existing latch is retained, never re-armed automatically. See decision_wait/decision_resumed in live_key_actions.csv.

Recording index: live_video_index.csv; async encoder: True; encoded: 3165; unread recording frames replaced: 0.
Live recordings pair clean live_source.mp4 and live_overlay.mp4 through live_video_index.csv. Nominal video FPS is not capture time.
Latency statistics stop at the decision, excluding overlay/encoding. Live encoding has one bounded unread slot and does not wait in the CV loop.

## Accuracy status

No independent ground truth is available; runtime counts do not establish recognition accuracy.
See the operator guide and live_key_actions.csv for Assist operation and diagnostics.
