# V8.4 lane-filter experiment design

## Scope and status

`src/lane_filter.py` provides an offline semantic adapter around the existing
V8.3 `Perception`. It records one observation for each current-frame detection,
keeps source timestamps, emits role masks, and attaches evidence and reasons.
It does **not** implement an independently validated detector and it is not
connected to `src/live.py`, `Engine`, `Tracker`, or an actuator. That boundary
keeps the active behavior unchanged while the experiment is incomplete.

## Coordinates and input

The renderer reads `live_source.mp4` together with `live_video_index.csv` and
uses `video_frame` to join rows. `source_frame`, `capture_timestamp`, and
`acquired_timestamp` are copied into every observation. Preview FPS is used
only for video encoding. Missing index rows stay visible in `frame_summary.csv`;
they do not receive fabricated timestamps. The current geometry is the existing
`config/geometry_live_assist.json` transformed six-lane plane. Its status is
`pending_calibration`; no geometry or timing values are changed.

The adapter calls the current perception implementation on each acquired
frame. Its detector color class, panel dimensions, role, ribbon depth, score,
and component label are recorded as evidence. Role names are
`TAP_FACE`, `HOLD_HEAD`, `HOLD_BODY`, `HOLD_TAIL`, `FRAGMENT`, and `UNKNOWN`.
Detector score is explicitly not a probability. Candidate IDs are observation
IDs scoped to the output stream; component IDs remain frame-local.

## Mask channels and review rendering

`masks.npz` stores lossless uint8 channels in this order:

1. `lane`: the rectified six-lane image plane.
2. `tap_face`, `hold_head`, `hold_body`, `hold_tail`: current detection boxes
   assigned the corresponding legacy detector role.
3. `judgment_line`: configured judgment-line coordinates.
4. `effect_or_artifact`: reserved, currently empty because the current
   detector does not expose an independently classified effect channel.
5. `unknown`: ambiguous and incomplete legacy detections.

The review video draws only the six configured lane edges, configured
judgment line, and detected role boxes on a black canvas. The side-by-side video
shows the rectified source next to this canvas. Neither file is used as machine
input. A mask box is not pixel-accurate segmentation; the distinction is
recorded here so a clean preview is not mistaken for stronger recognition.

## Causality and uncertainty

The processing API receives one frame and its two timestamps. It has no key
event, manual annotation, future frame, or scheduler input. Motion evidence may
refer only to a prior detection within 250 ms; that evidence does not promote
an otherwise ambiguous role. A current detection is marked fresh. No memory
observation is emitted as a new pixel observation. Hold connection evidence is
limited to the same-frame local ribbon depths exposed by the existing
perception function; it does not establish cross-Hold ownership. Ambiguous
panels remain `UNKNOWN` and `FRAGMENT` rather than being upgraded by prediction.

## Extension boundary

The renderer currently implements `--mode filtered`. `baseline` and `compare`
are CLI-reserved and fail explicitly because this checkout has no replay or
recording modules that can drive the same tracker, timing, and mock scheduler
from both perception sources. A future comparison must add that adapter and
human-reviewed physical-note annotations before reporting A/B quality scores.
