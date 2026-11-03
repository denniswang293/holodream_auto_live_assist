# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Experiment: v7147_tap_earlier_amend_ab | variant: experiment
Input prediction target: y=295.5; physical track completion: y=325.5.
Tap timing source: global; Global model: active.
Processed frames: 8142; acquired/source frames: 8417
Capture FPS: 64.178; processing FPS: 60.422
Latency P50/P95: 13.221/27.216 ms
Dropped frames: 275; stale frames: 0
Events: 535; abstentions: 126; key-downs: 245 (Tap 183, Hold 62)
Tap intent states: {'PENDING': 0, 'FIRED': 183, 'CANCELED': 0, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 246, 'hit_time_drift': 10, 'unstable_hit_time': 32, 'duplicate_hold_path': 65, 'past_hit_time': 17, 'tap_key_conflict': 2}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 8142; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
