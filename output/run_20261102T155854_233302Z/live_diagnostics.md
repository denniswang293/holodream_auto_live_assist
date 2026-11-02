# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Tap timing source: global; Global model: active.
Processed frames: 2699; acquired/source frames: 2768
Capture FPS: 64.279; processing FPS: 61.983
Latency P50/P95: 13.037/26.969 ms
Dropped frames: 69; stale frames: 0
Events: 121; abstentions: 43; key-downs: 38 (Tap 19, Hold 19)
Tap intent states: {'PENDING': 0, 'FIRED': 19, 'CANCELED': 0, 'EXPIRED': 0}
Abstain reasons: {'unstable_hit_time': 16, 'hit_time_drift': 5, 'duplicate_hold_path': 19, 'selected_tap': 36, 'past_hit_time': 3}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 2699; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
