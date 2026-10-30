# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 4075; acquired/source frames: 4088
Capture FPS: 61.532; processing FPS: 59.510
Latency P50/P95: 11.763/21.609 ms
Dropped frames: 13; stale frames: 0
Events: 335; abstentions: 25; key-downs: 134 (Tap 124, Hold 10)
Tap intent states: {'PENDING': 0, 'FIRED': 124, 'CANCELED': 1, 'EXPIRED': 0}
Abstain reasons: {'unstable_hit_time': 17, 'past_hit_time': 5, 'selected_tap': 131, 'hit_time_drift': 1, 'duplicate_hold_path': 2, 'game_state_or_focus_or_roi_loss': 1}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 4075; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
