# PR0 before / after

Before: run data had per-frame lifecycle rows but no compact note-level outcome report; `NOT_SCHEDULED` could be mistaken for missed notes.

After: `tools/analyze_run.py` groups by `note_uid`, records one final track-level verdict, keeps physical-note identity and game judgment as `UNRESOLVED` / `UNVERIFIED`, and emits the V7.1 baseline reports.

Baseline reproduction: 304 detected, 142 confirmed, 125 scheduled, 124 fired, 1 canceled, and 17 listed confirmed-without-schedule tracks. These remain track counts, not physical-note accuracy.
