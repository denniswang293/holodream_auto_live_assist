# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Experiment: v7148_tap_earlier_amend_ab | variant: stable
Input prediction target: y=295.5; physical track completion: y=325.5.
Tap timing source: global; Global model: active.
Processed frames: 7344; acquired/source frames: 7726
Capture FPS: 64.096; processing FPS: 60.556
Latency P50/P95: 15.435/29.080 ms
Dropped frames: 382; stale frames: 0
Events: 527; abstentions: 121; key-downs: 243 (Tap 183, Hold 60)
Tap intent states: {'PENDING': 0, 'FIRED': 183, 'CANCELED': 0, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 241, 'duplicate_hold_path': 67, 'unstable_hit_time': 37, 'hit_time_drift': 9, 'tap_key_conflict': 3, 'past_hit_time': 5}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 7344; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
