# PR2 before / after

Before: a pending Simple Tap reused its first `hit_at` forever; later predictions were ignored.

After: when `live.tap_deadline_amend.enabled` is true, the same pending note can receive a monotonic revision. The key remains frozen, updates are atomic in the scheduler, the update is rejected inside the 30 ms freeze window or when step/total limits are exceeded, and a stale revision cannot fire.

The feature does not amend an intent after it is FIRED/CANCELED, does not create a second intent, and keeps the existing 15 ms lateness and safety checks.
