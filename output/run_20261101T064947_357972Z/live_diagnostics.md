# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 1133; acquired/source frames: 1510
Capture FPS: 62.916; processing FPS: 47.170
Latency P50/P95: 22.296/33.729 ms
Dropped frames: 377; stale frames: 0
Events: 212; abstentions: 17; key-downs: 65 (Tap 53, Hold 12)
Tap intent states: {'PENDING': 0, 'FIRED': 53, 'CANCELED': 2, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 67, 'unstable_hit_time': 10, 'duplicate_hold_path': 4, 'past_hit_time': 3, 'game_state_or_focus_or_roi_loss': 2}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 1133; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
