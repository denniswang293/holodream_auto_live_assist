# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 6037; acquired/source frames: 6053
Capture FPS: 61.095; processing FPS: 58.099
Latency P50/P95: 11.437/21.396 ms
Dropped frames: 16; stale frames: 0
Events: 494; abstentions: 39; key-downs: 186 (Tap 166, Hold 20)
Tap intent states: {'PENDING': 0, 'FIRED': 166, 'CANCELED': 1, 'EXPIRED': 1}
Abstain reasons: {'unstable_hit_time': 31, 'selected_tap': 181, 'hit_time_drift': 1, 'past_hit_time': 5, 'late_or_key_already_held': 1, 'duplicate_hold_path': 2, 'game_state_or_focus_or_roi_loss': 1}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 6037; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
