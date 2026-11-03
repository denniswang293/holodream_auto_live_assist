# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Experiment: v7147_tap_earlier_amend_ab | variant: baseline
Input prediction target: y=295.5; physical track completion: y=325.5.
Tap timing source: global; Global model: active.
Processed frames: 8681; acquired/source frames: 8946
Capture FPS: 64.325; processing FPS: 58.871
Latency P50/P95: 12.722/26.957 ms
Dropped frames: 265; stale frames: 0
Events: 536; abstentions: 122; key-downs: 248 (Tap 186, Hold 62)
Tap intent states: {'PENDING': 0, 'FIRED': 186, 'CANCELED': 0, 'EXPIRED': 1}
Abstain reasons: {'selected_tap': 253, 'outside_horizon_or_uncertain': 1, 'duplicate_hold_path': 72, 'unstable_hit_time': 26, 'hit_time_drift': 6, 'past_hit_time': 13, 'late_or_key_already_held': 1, 'tap_key_conflict': 4}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 8679; dropped recording frames: 2.
Latency stops at the decision stage and excludes overlay/encoding.
