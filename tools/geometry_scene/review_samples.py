"""Create reproducible source-frame color-mask triage for V2 review windows."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

from .segmentation import HSVBand, SegmentationConfig, segment_frame


def segment(frame: np.ndarray):
    config = SegmentationConfig(
        cyan=(HSVBand((85, 80, 180), (112, 255, 255)),),
        green=(HSVBand((38, 80, 75), (84, 255, 255)),),
        calibration_polygon=((590, 20), (693, 20), (1220, 560), (60, 560)),
        min_area=180, min_panel_width=30, min_panel_height=6,
    )
    return segment_frame(frame, config)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--frames", type=int, nargs="+", default=[294, 360, 894])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"cannot open source: {args.video}")
    rows = []
    try:
        for frame_idx in args.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ok, frame = cap.read()
            if not ok:
                rows.append({"frame": frame_idx, "status": "DECODE_FAILED", "detections": 0})
                continue
            result = segment(frame)
            canvas = frame.copy()
            detections = result.candidates
            for c in detections:
                x, y, w, h = c.bbox
                label = f"{c.kind}/{c.status}/{'+'.join(c.colors)}"
                color = (255, 0, 255) if "cyan" in c.colors else (0, 255, 255)
                cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)
                cv2.putText(canvas, label, (x, max(12, y - 3)), cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1)
                points = c.panel_outline if c.panel_outline else c.outline
                if len(points) >= 3:
                    cv2.polylines(canvas, [np.asarray(points, np.int32)], True, color, 1, cv2.LINE_AA)
            cv2.imwrite(str(args.out / f"source_frame_{frame_idx:06d}.png"), frame)
            cv2.imwrite(str(args.out / f"candidate_mask_{frame_idx:06d}.png"), result.raw_mask)
            cv2.imwrite(str(args.out / f"candidate_overlay_{frame_idx:06d}.png"), canvas)
            rows.append({"frame": frame_idx, "status": "AUTO_VISUAL_REVIEWED_PROVISIONAL",
                         "detections": len(detections),
                         "candidate_boxes": ";".join(f"{c.bbox[0]},{c.bbox[1]},{c.bbox[2]},{c.bbox[3]},{c.kind},{c.status},{'+'.join(c.colors)}" for c in detections),
                         "truth_status": "UNKNOWN_NOT_HUMAN_REVIEWED"})
    finally:
        cap.release()
    with (args.out / "review_queue.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "status", "detections", "candidate_boxes", "truth_status"])
        writer.writeheader(); writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
