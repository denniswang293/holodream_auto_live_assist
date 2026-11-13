# V8.4 implementation result

## Baseline and local data

- Found 8 `USABLE` manual recording runs and 12 `PARTIAL` Assist runs under
  `output/`; all videos decode and align with index rows. Assist source
  sequences contain 18,178 gaps; per-run reasons and provenance are in
  `output/analysis_lane_filter_v84/dataset_audit.csv`.
- Baseline environment, hashes, and pre-existing pytest result are in
  `output/analysis_lane_filter_v84/baseline_environment.json`.
- Before this work, pytest collected no tests (exit 5). Added lane-filter
  isolation and dataset-audit coverage; current `python -m pytest -q` passes 4 tests.
- `config/geometry_live_assist.json` is still `pending_calibration`; the timing
  and geometry files were not modified.

## Deliverables

- `src/lane_filter.py`: causal observation type and adapter over current
  perception, with current-frame source provenance, evidence/reasons, bounded
  past-only motion context, and semantic channels.
- `tools/render_lane_filter.py`: offline `--run-dir`, `--out`,
  `--mode filtered|baseline|compare`, and `--limit-frames` CLI. Only filtered
  rendering is implemented; unsupported replay modes fail with an explicit
  message. It never creates or calls an actuator.
- `output/analysis_lane_filter_v84/run_20261109T143554_007912Z/`: complete
  1,149-frame filtered and side-by-side videos, observations, frame summary,
  compressed lossless masks, review frames, audit, and quality report.
- `output/analysis_lane_filter_v84/annotations/physical_notes.csv` is an empty
  human-review template, not a labeled evaluation set.
- Design and evaluation boundaries are in `V84_LANE_FILTER_DESIGN.md` and
  `V84_LANE_FILTER_EVALUATION.md`.

## Findings and limits

The selected run has 1,149 decoded frames and 1,149 matching index rows, no
timestamp reversals, and 7,504 detections adapted into role observations.
Repeated full renders measured 22.97–40.27 ms/frame mean and 28.56–49.35 ms/frame
P90. Both ends exceed a 60 FPS budget. These are wall-time pipeline measurements,
not isolated processor time; no Live integration is recommended.

This is not an independent new perception implementation: semantic roles are
adapted from the existing detector, role masks are bounding boxes, and
`effect_or_artifact` is reserved but currently empty. The checkout has no
`src/replay.py` or `src/recordings.py`, no reviewed physical-note annotations,
and no shared baseline/candidate replay adapter. Therefore physical-note
recall, false-positive rate, owner accuracy, action recall, timing comparisons,
and the 273/282, 498/513, 1151/1162 case improvements remain unevaluated. No
improvement is claimed.

## Active status

**NO: Active was not changed.** Production Perception/Tracking/Timing/Scheduler,
geometry, timing calibration, and source recordings were not modified. The new
adapter is offline only. The current result does not meet the plan's evidence,
fair-comparison, or performance gates for Active integration.
