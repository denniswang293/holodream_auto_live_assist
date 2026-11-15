"""Fingerprint current-frame segmentation on indexed source frames.

Frames are decoded sequentially and paired to the corresponding video-index
row. This is an offline diagnostic; it reads no labels or future frames into
segmentation decisions and does not render or encode video.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model import Geometry  # noqa: E402
from src.lane_segmentation import LanePixelSegmenter  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, nargs="+", required=True,
                        help="video_frame indexes; source frames are resolved from the index")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--geometry", type=Path, default=ROOT / "config/geometry_live_assist.json")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    video = run_dir / "live_source.mp4"
    index_path = run_dir / "live_video_index.csv"
    with index_path.open(encoding="utf-8-sig", newline="") as stream:
        index = {int(row["video_frame"]): row for row in csv.DictReader(stream)}
    targets = sorted(set(args.frames))
    missing = [frame for frame in targets if frame not in index]
    if missing:
        raise SystemExit(f"video_frame indexes absent from source index: {missing}")

    geometry = Geometry(args.geometry.resolve())
    segmenter = LanePixelSegmenter()
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"cannot open source video: {video}")
    found = {}
    frame_no = -1
    target_set = set(targets)
    try:
        while targets and (ok := capture.read())[0]:
            frame_no += 1
            if frame_no not in target_set:
                continue
            image = ok[1]
            normalized = geometry.normalize(image)
            rectified = geometry.rectify(normalized)
            started = time.perf_counter()
            result = segmenter.segment(rectified, geometry, frame_index=frame_no)
            elapsed_ms = (time.perf_counter() - started) * 1000
            row = index[frame_no]
            found[frame_no] = {
                "video_frame": frame_no,
                "source_frame": int(row.get("source_frame", frame_no)),
                "capture_timestamp": float(row["capture_timestamp"]),
                "acquired_timestamp": float(row["acquired_timestamp"]),
                "rectified_shape": list(rectified.shape),
                "segment_wall_ms": elapsed_ms,
                "stage_profile_ms": result_profile(segmenter),
                "mask_sha256": {
                    name: hashlib.sha256(np.ascontiguousarray(mask).tobytes()).hexdigest()
                    for name, mask in sorted(result.masks.items())
                },
                "components": [
                    {"id": c.component_id, "role": c.role, "bbox": c.bbox,
                     "color": c.color, "area": c.area, "evidence": c.evidence,
                     "positive": c.positive, "negative": c.negative,
                     "ambiguity": c.ambiguity}
                    for c in result.components
                ],
            }
            targets.remove(frame_no)
            target_set.remove(frame_no)
    finally:
        capture.release()
    if targets:
        raise SystemExit(f"source video ended before requested frame indexes: {targets}")

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_dir.name,
        "video_sha256": sha256_file(video),
        "index_sha256": sha256_file(index_path),
        "geometry_sha256": geometry.sha256,
        "decoder_policy": "sequential VideoCapture.read; video_frame maps to same index row",
        "source_pixels_only": True,
        "future_frames_or_reference_events_used_for_decisions": False,
        "frames": [found[frame] for frame in sorted(found)],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(out)


def result_profile(segmenter: LanePixelSegmenter) -> dict[str, float]:
    return {key: float(value) for key, value in segmenter.last_profile.items()}


if __name__ == "__main__":
    main()
