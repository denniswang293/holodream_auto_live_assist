# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 7745; acquired/source frames: 7962
Capture FPS: 64.231; processing FPS: 62.060
Latency P50/P95: 12.901/26.964 ms
Dropped frames: 217; stale frames: 0
Events: 579; abstentions: 134; key-downs: 197 (Tap 133, Hold 64)
Tap intent states: {'PENDING': 0, 'FIRED': 133, 'CANCELED': 0, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 194, 'duplicate_hold_path': 79, 'hit_time_drift': 14, 'unstable_hit_time': 35, 'past_hit_time': 6}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 7745; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
