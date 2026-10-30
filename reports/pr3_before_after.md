# PR3 before / after

Before: visual crossing, game judgment, and input scheduling were represented by one implicit timestamp.

After: `src/judgment_time.py` separates those three timestamps and records model status in `live_run.json`. Calibration remains shadow-only while geometry is pending or labeled samples are insufficient; the current baseline trigger and 30 px setting remain unchanged.

No game judgment samples were available in the supplied run, so no timing offset or accuracy improvement is claimed.
