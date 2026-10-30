# PR4 before / after

Before: Hold candidates entered the legacy visual tracker only when a single frame already showed the full configured path length.

After: `src/hold_tracker.py` accumulates two-frame head/body continuity, tracks lane span and path evidence, and retains accepted identity through a bounded dropout grace. The existing scheduler still owns key-down, key-up, max-hold timeout, focus loss, and emergency stop.

The tracker does not accept an isolated colored fragment. The supplied run has no reliable one-to-one game judgment mapping for the 59–60.5 s segment, so Hold success is still unverified.
