"""Render exact source frames for pixel-segmentation review before full replay."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.geometry_video.geometry import VideoGeometry
from src.geometry_video.renderer import render_geometry_frame
from src.geometry_video.segmenter import Candidate, PixelGeometryConverter


def describe(candidate: Candidate, index: int) -> dict:
    return {"class": candidate.class_name, "color": candidate.color_name,
            "confidence": round(candidate.confidence, 3), "bbox": list(candidate.bbox),
            "area": candidate.area, "polygon": candidate.polygon,
            "parts": candidate.parts, "reasons": candidate.uncertainty_reasons,
            "pixel_evidence": candidate.pixel_evidence, "index": index}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="run_20261106T164049_800126Z")
    parser.add_argument("--frame", action="append", type=int, default=[])
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--geometry", type=Path, default=Path("config/geometry_video_v1.json"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/segmentation_samples"))
    args = parser.parse_args()
    frames = args.frame or [316, 1579, 2842]
    args.out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(args.recording_root/args.run/"live_source.mp4"))
    geometry = VideoGeometry(args.geometry)
    converter = PixelGeometryConverter(geometry)
    for frame_id in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, source = cap.read()
        if not ok:
            print(f"{args.run} frame={frame_id}: DECODE_ERROR")
            continue
        objects, uncertain = converter.segment(source)
        rendered = render_geometry_frame(geometry, objects)
        diag = source.copy()
        all_rows = [dict(describe(item, i), review_status="VISIBLE_CANDIDATE")
                    for i, item in enumerate(objects)] + [
            dict(describe(item, i+len(objects)), review_status="UNCERTAIN")
            for i, item in enumerate(uncertain)]
        mask = np.zeros(source.shape[:2], dtype=np.uint8)
        mask_classes = np.zeros((*source.shape[:2], 3), dtype=np.uint8)
        for row in all_rows:
            x, y, w, h = row["bbox"]
            color = (40, 220, 60) if row["review_status"] == "VISIBLE_CANDIDATE" else (40, 80, 240)
            mask_value = 255 if row["review_status"] == "VISIBLE_CANDIDATE" else 128
            mask_color = ({"TAP": (255, 190, 30), "HOLD": (50, 220, 75)}.get(row["class"], (125,125,125))
                          if row["review_status"] == "VISIBLE_CANDIDATE" else (125,125,125))
            for dy, start, length in row["pixel_evidence"].get("mask_spans_rle", []):
                if 0 <= y+dy < mask.shape[0]:
                    x0, x1 = max(0, x+start), min(mask.shape[1], x+start+length)
                    mask[y+dy, x0:x1] = mask_value
                    row_pixels = mask_classes[y+dy, x0:x1]
                    row_pixels[np.all(row_pixels == 0, axis=1)] = mask_color
            cv2.rectangle(diag, (x, y), (x+w, y+h), color, 2)
            cv2.putText(diag, f"{row['class']} {row['color']} {row['confidence']:.2f}",
                        (x, max(18, y-5)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
        stem = f"{args.run}_f{frame_id:06d}"
        cv2.imwrite(str(args.out/f"{stem}_source.png"), source)
        cv2.imwrite(str(args.out/f"{stem}_geometry.png"), rendered)
        cv2.imwrite(str(args.out/f"{stem}_diagnostic.png"), diag)
        cv2.imwrite(str(args.out/f"{stem}_comparison.png"), cv2.hconcat((source, rendered)))
        cv2.imwrite(str(args.out/f"{stem}_mask.png"), mask)
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        cv2.imwrite(str(args.out/f"{stem}_mask_comparison.png"), cv2.hconcat((source, mask_bgr)))
        cv2.imwrite(str(args.out/f"{stem}_mask_classes.png"), mask_classes)
        (args.out/f"{stem}_instances.json").write_text(json.dumps({"run_id": args.run,
            "frame_id": frame_id, "objects": [describe(item, i) for i,item in enumerate(objects)],
            "uncertain": [describe(item, i) for i,item in enumerate(uncertain)]}, indent=2), encoding="utf-8")
        print(f"{args.run} frame={frame_id}: taps={sum(x.class_name=='TAP' for x in objects)} holds={sum(x.class_name=='HOLD' for x in objects)} uncertain={len(uncertain)}")
    cap.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
