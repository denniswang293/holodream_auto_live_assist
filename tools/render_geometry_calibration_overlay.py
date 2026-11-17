"""Make a source-only visual comparison of independent rail estimates."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.geometry_video.geometry import VideoGeometry


LUNA_VISUAL_POINTS = {
    30: [605, 617, 628, 640, 652, 663, 675],
    190: [407, 485, 562, 640, 718, 795, 873],
    325: [327, 431, 536, 640, 744, 849, 953],
    560: [61, 254, 447, 640, 833, 1026, 1219],
}


def x_at(points, lane: int, y: float) -> float:
    ys = sorted(points)
    xs = [points[row][lane] for row in ys]
    return float(np.interp(y, ys, xs))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="run_20261106T164049_800126Z")
    parser.add_argument("--frame", type=int, default=1579)
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--rail-report", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/rail_measurements.json"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/calibration_candidates_anchored"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(args.recording_root / args.run / "live_source.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, args.frame)
    ok, source = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Cannot decode requested source frame")
    overlay = source.copy()
    config_doc = json.loads(Path("config/geometry_video_v1.json").read_text(encoding="utf-8"))
    geometry = VideoGeometry(config_doc)
    y_eval = (0, 30, 190, 325, 560, round(geometry.judgment_y))
    # Blue: one global straight-line Hough fit. Orange: the piecewise source
    # visual anchors currently used by the provisional geometry.
    for lane, rail in enumerate(config_doc["hough_straight_line_crosscheck"]):
        slope, intercept = rail["slope_dx_per_dy"], rail["x_intercept_at_y0"]
        pts = [(round(intercept+slope*y), y) for y in (0, 580)]
        cv2.line(overlay, pts[0], pts[1], (255, 40, 40), 2, cv2.LINE_AA)
    for rail in geometry.rails:
        pts = [(round(rail.x(y)), y) for y in y_eval]
        cv2.polylines(overlay, [np.asarray(pts, np.int32)], False, (30, 170, 255), 2, cv2.LINE_AA)
        for point in rail.pixel_anchors:
            cv2.circle(overlay, (round(point[1]), round(point[0])), 4, (30, 170, 255), -1, cv2.LINE_AA)
    for y, color in ((560, (0, 170, 255)), (round(geometry.judgment_y), (255, 0, 255))):
        left, right = geometry.boundaries(y)[0], geometry.boundaries(y)[-1]
        cv2.line(overlay, (round(left), y), (round(right), y), color, 2, cv2.LINE_AA)
    cv2.rectangle(overlay, (0, 0), (1279, 62), (0, 0, 0), -1)
    cv2.putText(overlay, "Blue: global Hough fit (too narrow at bottom); orange: provisional pixel anchors",
                (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(overlay, "Judgment reference y=580; brightest band rows y=560 and y=600; hit row unverified",
                (8, 42), cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(overlay, f"{args.run} frame={args.frame}", (8, 59), cv2.FONT_HERSHEY_SIMPLEX, .44, (255, 255, 255), 1, cv2.LINE_AA)
    blended = cv2.addWeighted(source, .58, overlay, .62, 0)
    out = args.out / f"{args.run}_frame_{args.frame}_calibration_candidates.png"
    cv2.imwrite(str(out), blended)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
