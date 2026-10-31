# HoloDream Assist diagnostics

Stop: global_escape_or_f12
Source: actual window capture | geometry: pending_calibration (e2b28c79ccea59f743ae39a7fe886e17f9d13b9e095c1544426dcb230ab94cd4)

Input prediction target: y=295.5; physical track completion: y=325.5.
Processed frames: 1202; acquired/source frames: 1547
Capture FPS: 64.305; processing FPS: 49.079
Latency P50/P95: 21.131/32.715 ms
Dropped frames: 345; stale frames: 0
Events: 232; abstentions: 25; key-downs: 63 (Tap 50, Hold 13)
Tap intent states: {'PENDING': 0, 'FIRED': 50, 'CANCELED': 1, 'EXPIRED': 0}
Abstain reasons: {'selected_tap': 63, 'duplicate_hold_path': 8, 'unstable_hit_time': 16, 'past_hit_time': 1, 'game_state_or_focus_or_roi_loss': 1}

Tap accuracy and real-game hit rate are UNVERIFIED; event counts are not accuracy metrics.
The input latch starts OFF. Ctrl+Shift+Alt+Q plus modifier release is required to Arm.
Esc/F12, stale frames, focus loss, invalid ROI or gameplay state disarm and release keys. Re-arming is manual.
Hold uses the user-confirmed visible-tail rule; its accuracy is also UNVERIFIED.

Recording index: live_video_index.csv; encoded frames: 1202; dropped recording frames: 0.
Latency stops at the decision stage and excludes overlay/encoding.
