# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 1355; acquired/source frames: 1517
Capture FPS: 56.815; processing FPS: 49.112
Latency P50/P95: 21.386/34.097 ms
Dropped frames: 162; stale frames: 0
Events: 282; abstentions: 39; key-downs: 99 (Tap 73, Hold 26)
Tap intent states: {'PENDING': 0, 'FIRED': 73, 'CANCELED': 1, 'EXPIRED': 1}
Abstain reasons: {'selected_tap': 93, 'unstable_hit_time': 16, 'duplicate_hold_path': 15, 'hit_time_drift': 3, 'late_or_key_already_held': 1, 'past_hit_time': 5, 'game_state_or_focus_or_roi_loss': 1}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 1355; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
