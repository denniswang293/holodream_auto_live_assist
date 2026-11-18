# Geometry Scene v1 renderer

Render a human-authored JSON geometry description onto a generated black canvas. The renderer reads only the JSON and never opens, samples, or composites source video. Coordinates are canvas pixels, origin at the top-left; frame ranges are zero-based and half-open.

## Run

From the repository root:

```powershell
python tools/geometry_scene_v2/render_scene.py tools/geometry_scene_v2/synthetic_scene.json tools/geometry_scene_v2/synthetic_scene.mp4
```

The fixture is 640x360, 30 fps, and 120 frames (4 seconds). It includes two taps, one hold, and a six-frame explicitly inferred occlusion interval. The renderer uses OpenCV's `mp4v` encoder and outputs a full-length silent MP4.

## Schema

- `schema_version`: integer `1`.
- `title`: descriptive string; `fps`: number in (0, 240]; `frame_count`: positive integer.
- `canvas`: integer `width` and `height` (at least 64), with optional `background` set to `#000000`.
- `track_guides`: exactly six lane-center guides. Each guide is either a vertical x coordinate or a polyline of at least two `[x, y]` points in pixels. Polyline points must increase in y and the guides must remain left-to-right at shared y coordinates.
- `judgment_line`: either a y coordinate (full-width horizontal line) or an in-canvas `{ "from": [x,y], "to": [x,y] }` segment.
- `notes`: array. Each note has unique `id`, `type` (`Tap` or `Hold`), lane index `0..5`, `confidence` in `[0,1]`, `source` with `coordinate_system` and `provenance` strings, `intervals`, and `keyframes`.
- The reconstruction pipeline writes `intervals` from source-supported note visibility. A detector gap without a linked observation is recorded separately in `unobserved_intervals` with `NO_DIRECT_NOTE_OBSERVATION` and `NOT_OCCLUSION_EVIDENCE`; gap length by itself never creates an inferred note or an occlusion. For Tap tracks, one confirmed same-color fragment-only tracker may bridge a 5–18 frame gap between direct Tap anchors when at least 65% of gap frames (minimum three) align horizontally to the per-note source path and their vertical top-edge residual fits one smooth line. The fragment tracker must uniquely match that gap; ambiguous links are rejected. Associated points retain the fragment tracker ID, raw source box and uncalibrated score. Because a fragment may be horizontally clipped, the reconstructed center and width come from that note's own bracketing full-head observations; the partial source box only supplies association and top-edge evidence. These retrospective measurements remain provisional and are not ground truth. The existing within-tracker retrospective rule remains provisional; Hold body fragments are rejected if their connected component has another head-track owner. A source-reviewed offline reconstruction may add a bracketed `occluded` interval with both `INFERRED_OCCLUSION` and `OFFLINE_RETROSPECTIVE` labels, and the renderer will show only dashed geometry for that interval.
- Each interval has `state` (`visible` or `occluded`) and integer `start_frame`, `end_frame` with `0 <= start < end <= frame_count`. Intervals must be ordered and non-overlapping. Occluded frames are omitted from rendering. Optional `labels` is an array of strings; inferred occlusion requires an `occluded` interval carrying both `INFERRED_OCCLUSION` and `OFFLINE_RETROSPECTIVE`. An observed occlusion can be represented with `state: "occluded"` and no inference labels.
- Keyframes have strictly increasing integer `frame` values and finite `head_x`, `head_y`. Optional `head_width` and `head_height` keep a source-observed Tap/hold head as simple geometry. Holds also require `tail_x`, `tail_y`. Positions and dimensions interpolate linearly between keys and clamp to endpoint values outside the key span.
- Optional note `color` is `#RRGGBB`; default tap and hold colors differ. Taps show a head, short body, and tail cap. Holds show a head, straight head-to-tail body, and tail cap.

Confidence and provenance are preserved as scene metadata and do not alter visual geometry. The renderer draws flat geometric Tap heads and separate Hold heads, bodies, and tails. No source video timestamps or pixel content are read; the frame count and frame rate in the Scene define output duration.

Recovery-only Tap observations that form a nearly stationary cluster straddling a run's judgment line remain in the diagnostic trace but are not retrospectively attached to a tracker. The per-run line and original boxes are preserved; this gate avoids treating static judgment-band/effect pixels as a confirmed note identity. Nearby moving clusters still require the same unique tracker endpoint and overlap checks.


## Source geometry reconnaissance

`estimate_geometry.py output/recording output/geometry_scene_v2/geometries` reads each MP4 and matching video index without writing to either. It creates a per-run perspective geometry candidate from sampled encoded frames. These configs are labeled `AUTO_GEOMETRY_ESTIMATE / PROVISIONAL`; they are not manually confirmed ground truth and do not contain note detections. Their frame-index and capture-timestamp samples and source hashes are preserved in each JSON.

The same pipeline accepts a separate clip from this game. For an MP4 with an index, pass `--index <csv>`; without one, each frame time is based on that clip's own encoded FPS. Example:

```powershell
python tools/geometry_scene_v2/estimate_geometry.py D:\clips\segment.mp4 output/geometry_scene_v2/geometries/segment.json --index D:\clips\segment_index.csv
python tools/geometry_scene_v2/reconstruct_scene.py D:\clips\segment.mp4 output/geometry_scene_v2/geometries/segment.json output/geometry_scene_v2/scenes/segment/scene.json --index D:\clips\segment_index.csv
python tools/geometry_scene_v2/render_scene.py output/geometry_scene_v2/scenes/segment/scene.json output/geometry_scene_v2/scenes/segment/geometry.mp4
python tools/geometry_scene_v2/render_comparison.py D:\clips\segment.mp4 output/geometry_scene_v2/scenes/segment/geometry.mp4 output/geometry_scene_v2/scenes/segment/comparison.mp4
```

Geometry thresholds scale with frame dimensions and are intended for this game's six-lane perspective view at a 16:9 aspect ratio. A different song or segment gets its own measured note paths and speed from its own frames and timestamps. No footage beyond the eight supplied runs has been available here, so this reusable path is implemented but external-clip generalization has not yet been empirically validated.

The geometry estimator targets up to 60 unique, evenly spaced frames. For clips shorter than 60 frames it samples every available frame and checks decode coverage against that actual sample set. A clip still needs enough unobstructed rail and judgment-line evidence for the geometry estimate to succeed; failed or ambiguous fits must remain provisional. An optional index must provide exactly one row per encoded frame and a finite `capture_timestamp` for each row.

Rail candidates are ordered at 75% of that clip's frame height, where lane separation is visible; a tightly clustered set of top intercepts (at most 2% of frame width) may be snapped to a length-weighted common apex, with raw intercepts and adjustment values retained. The estimator rejects boundaries that cross or collapse at its sampled in-frame depths. These are provisional geometry-fit rules, not manual calibration.

## One clip: geometry, Scene, and comparison

Process another same-game MP4 with clip-specific geometry and note trajectories. The optional frame index is read only; without it, timestamps derive from this clip's encoded FPS. Outputs must go into a new, empty child directory under `output/geometry_scene_v2/`.

```powershell
python tools/geometry_scene_v2/process_clip.py path\to\clip.mp4 output\geometry_scene_v2\clip-name
python tools/geometry_scene_v2/process_clip.py path\to\clip.mp4 output\geometry_scene_v2\clip-name --index path\to\index.csv --id review-clip
```

The directory contains `geometry.json`, `scene.json`, blank-canvas `geometry.mp4`, frame-paired `comparison.mp4`, and `run_manifest.json` with input, pipeline, and output hashes. The generated geometry and Scene are provisional candidates, not ground truth. No shared note speed is assumed.
