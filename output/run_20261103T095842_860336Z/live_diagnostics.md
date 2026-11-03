# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Experiment: v7148_tap_earlier_amend_ab | variant: tap-earlier
Input prediction target: y=295.5; physical track completion: y=325.5.
Tap timing source: global; Global model: active.
Processed frames: 7388; acquired/source frames: 7672
Capture FPS: 63.650; processing FPS: 61.399
Latency P50/P95: 14.557/27.561 ms
Dropped frames: 284; stale frames: 0
Events: 555; abstentions: 139; key-downs: 222 (Tap 166, Hold 56)
Tap intent states: {'PENDING': 0, 'FIRED': 166, 'CANCELED': 0, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 223, 'hit_time_drift': 7, 'duplicate_hold_path': 95, 'unstable_hit_time': 26, 'past_hit_time': 8, 'tap_key_conflict': 3}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 7386; dropped recording frames: 2.
Latency stops at the decision stage and excludes overlay/encoding.
