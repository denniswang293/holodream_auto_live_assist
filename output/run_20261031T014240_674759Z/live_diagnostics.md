# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 1251; acquired/source frames: 1274
Capture FPS: 60.679; processing FPS: 54.737
Latency P50/P95: 9.173/27.371 ms
Dropped frames: 23; stale frames: 0
Events: 87; abstentions: 11; key-downs: 21 (Tap 16, Hold 5)
Tap intent states: {'PENDING': 0, 'FIRED': 16, 'CANCELED': 2, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 24, 'unstable_hit_time': 6, 'duplicate_hold_path': 1, 'tap_key_conflict': 1, 'past_hit_time': 3, 'stale_frame_or_focus_loss': 2}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 1251; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
