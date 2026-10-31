# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 1416; acquired/source frames: 1561
Capture FPS: 64.262; processing FPS: 57.210
Latency P50/P95: 22.984/31.486 ms
Dropped frames: 145; stale frames: 0
Events: 284; abstentions: 32; key-downs: 76 (Tap 58, Hold 18)
Tap intent states: {'PENDING': 0, 'FIRED': 58, 'CANCELED': 2, 'EXPIRED': 1}
Abstain reasons: {'selected_tap': 76, 'unstable_hit_time': 11, 'past_hit_time': 8, 'duplicate_hold_path': 11, 'tap_key_conflict': 2, 'late_or_key_already_held': 1, 'game_state_or_focus_or_roi_loss': 2}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 1416; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
