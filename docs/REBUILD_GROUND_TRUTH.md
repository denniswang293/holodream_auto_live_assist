# Reference data and timing ground truth

The reference set contains eight usable manual recordings. It preserves complete host-clock key intervals and indexed capture/acquired timestamps, but it is not complete per-note game judgment truth. `game_judgment_accuracy` remains `UNKNOWN` in the recording metadata. The user's successful manual performance is accepted as a valid operation reference. It does not identify each note's unique judgment category or the absolute center of the game's timing window.

## Reference counts

- 8 usable recordings, 26,259 indexed frames and 2,836 complete down/up key intervals.
- 17,090 visual note hypotheses. These include effects, fragmented identities and other false or duplicate hypotheses; they are not the true chart note count.
- 1,770 supported human-action associations, including 36 supported Hold intervals. The other 1,066 human actions remain **UNKNOWN** for note association. Unmatched visual hypotheses also remain unknown.
- Of the supported associations, only 1,265 have an observed head-crossing bracket. Another 505 use disclosed short extrapolation and are not direct crossing observations.

The 1,770 associations are evidence-supported matches, not verified game hits. Association uses compatible key coverage, descending motion, head proximity, timing tolerance and a unique cost margin. Hold matching also requires tail/up evidence; duration alone does not identify a Hold. Overlapping events, ambiguous competing tracks, menus, occlusion, classification errors and fragmented tracks are not forced into labels.

## Clock and provenance

The video index, key events and markers use host performance-counter seconds with matching elapsed-time origins. The playable video ordinal and source acquisition sequence are distinct. Nominal 60 FPS is not used as a timing clock; frame timing comes from indexed capture/acquired timestamps. Median frame capture cadence is about 39 ms (roughly 25.5 Hz). The capture-to-acquired interval itself is typically about 18–20 ms; display exposure within that interval is not observable. A different live capture backend can change the interval, and timing transfer across backends is unverified.

Each association can be traced from `run_id` and encoded `video_frame` through capture timestamp and visual hypothesis to stable `action_id` and down/up interval. The offline matcher may use later frames to construct labels. Causal replay and the active runtime do not read reference labels or human key events.

## Successful-operation timing reference

`config/reference_timing.json` fits a log-position model. It uses 20 visually reviewed development heads with observed crossings from the first four recordings. The median `visual crossing - successful human key-down` offset is −16.536 ms (P10 −34.845 ms, P90 +4.435 ms). The model therefore targets a key-down about 16.5 ms after its predicted visual leading-edge crossing. This is a manual-operation offset, not an ideal game judgment center and not a hardware latency calibration.

Development visual prediction error bands are P90 absolute errors of 90.99 ms at y=190, 50.77 ms at y=230, 32.92 ms at y=270, 23.89 ms at y=290, 22.24 ms at y=300 and 19.52 ms at y=310. These describe prediction error, not hit rate. The runtime's 40 ms uncertainty gate remains in force; unavailable calibration at earlier heights is not treated as zero error.

No reviewed Hold has an independently observed, reliable tail bracket suitable for learning a release offset. `release_guard_samples=0` and `release_guard_s=0` mean no guard has been calibrated; they do not establish an ideal release time. A predicted release includes runtime tail uncertainty, while a safety-censored release (for example the hard timeout) is not a measured tail crossing and must not be counted as successful release timing.

The four development recordings supplied all 20 timing-review samples. The final four recordings were not used to fit the timing reference. However, all eight recordings were inspected during debugging, so the final four are not a blind holdout. These recordings also do not establish chart-disjoint validation.

## Current reference material

The extraction/calibration commands used during the rebuild have been retired. Generated `output/analysis_reference/` datasets and frozen extractor copies are no longer included. The original eight recordings remain in `output/recording/`; the runtime uses `config/reference_timing.json` and does not require generated analysis outputs.

Regression examples and their frame/timestamp provenance are stored in `tests/fixtures/`. For recording integrity details, see [data audit](REBUILD_DATA_AUDIT.md); for the running system, see [architecture](REBUILD_ARCHITECTURE.md).
