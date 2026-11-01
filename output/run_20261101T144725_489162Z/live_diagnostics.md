# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 4055; acquired/source frames: 6384
Capture FPS: 64.142; processing FPS: 40.340
Latency P50/P95: 25.634/36.039 ms
Dropped frames: 2329; stale frames: 0
Events: 1406; abstentions: 114; key-downs: 337 (Tap 270, Hold 67)
Tap intent states: {'PENDING': 0, 'FIRED': 270, 'CANCELED': 0, 'EXPIRED': 4}
Abstain reasons: {'selected_tap': 337, 'unstable_hit_time': 51, 'duplicate_hold_path': 36, 'hit_time_drift': 13, 'late_or_key_already_held': 4, 'past_hit_time': 14}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 4055; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
