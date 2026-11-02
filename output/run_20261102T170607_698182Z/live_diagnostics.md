# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Tap timing source: global; Global model: active.
Processed frames: 4145; acquired/source frames: 4318
Capture FPS: 64.205; processing FPS: 61.100
Latency P50/P95: 14.944/27.609 ms
Dropped frames: 173; stale frames: 0
Events: 308; abstentions: 69; key-downs: 137 (Tap 105, Hold 32)
Tap intent states: {'PENDING': 0, 'FIRED': 105, 'CANCELED': 2, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 133, 'duplicate_hold_path': 39, 'hit_time_drift': 6, 'unstable_hit_time': 19, 'past_hit_time': 3, 'tap_key_conflict': 2, 'game_state_or_focus_or_roi_loss': 2}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 4145; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
