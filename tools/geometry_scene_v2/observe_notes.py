#!/usr/bin/env python3
"""Write source-indexed note observations using the isolated per-run geometry.

Legacy Perception output is retained only as candidate evidence; it is not
ground truth and must not be used as an accepted note list by itself.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.perception import Perception


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RunGeometry:
    """Rectify x into six lane columns using one run's provisional rails."""

    def __init__(self, document: dict[str, Any]):
        self.width, self.height = document["source"]["resolution"]
        self.plane_width = 600
        self.lane_pixels = 100.0
        self.top_y = 20.0
        self.hit_y = float(document["judgment_line_y"])
        self.rails = document["rail_boundaries"]
        y = np.arange(self.height, dtype=np.float32)
        boundaries = np.stack([self.boundaries(row) for row in y], axis=0)
        q = np.arange(self.plane_width, dtype=np.float32) / self.lane_pixels
        lane = np.minimum(q.astype(int), 5)
        frac = q - lane
        self.map_x = (boundaries[:, lane] * (1 - frac) + boundaries[:, lane + 1] * frac).astype(np.float32)
        self.map_y = np.repeat(y[:, None], self.plane_width, axis=1)

    def boundaries(self, y: float) -> np.ndarray:
        return np.asarray(
            [rail["top_intercept_x"] + rail["slope_dx_per_dy"] * y for rail in self.rails],
            dtype=np.float32,
        )

    def rectify(self, image: np.ndarray) -> np.ndarray:
        return cv2.remap(
            image, self.map_x, self.map_y, cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )

    def source_x(self, rect_x: float, y: float) -> float:
        q = float(np.clip(rect_x / self.lane_pixels, 0, 6))
        lane = min(5, int(q))
        frac = q - lane
        boundary = self.boundaries(y)
        return float(boundary[lane] * (1 - frac) + boundary[lane + 1] * frac)


def observe(video: Path, index: Path | None, geometry_path: Path, output: Path, max_frames: int | None = None) -> dict[str, Any]:
    geometry_doc = json.loads(geometry_path.read_text(encoding="utf-8"))
    geometry = RunGeometry(geometry_doc)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"cannot decode {video}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if index is not None:
        with index.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != frame_count:
            cap.release()
            raise ValueError(f"index/video row mismatch: {len(rows)} != {frame_count}")
        for frame_no, row in enumerate(rows):
            if "video_frame" in row and int(row["video_frame"]) != frame_no:
                cap.release()
                raise ValueError(f"index video_frame order mismatch at {frame_no}")
    else:
        rows = [{"capture_timestamp": f / fps} for f in range(frame_count)]
    limit = frame_count if max_frames is None else min(frame_count, max_frames)
    observer = Perception(geometry)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        header = {
            "record_type": "provenance",
            "schema": "geometry_scene_v2.input_observations.v1",
            "status": "LEGACY_DETECTION_OBSERVATIONS_ONLY / NOT_GROUND_TRUTH",
            "source_video": video.as_posix(),
            "source_video_sha256": sha256(video),
            "source_index": index.as_posix() if index is not None else None,
            "source_index_sha256": sha256(index) if index is not None else None,
            "timestamp_source": "read_only_index_capture_timestamp" if index is not None else "encoded_video_frame_index_divided_by_this_clip_fps",
            "geometry_json": geometry_path.as_posix(),
            "geometry_sha256": sha256(geometry_path),
            "frame_count_total": frame_count,
            "frames_processed": limit,
            "processing_stride": 1,
            "candidate_source": "src.perception.Perception.detect on per-run provisional rectification",
            "excluded_inputs": ["player_key_events.csv", "output masks as truth", "manual keypresses", "total object counts"],
        }
        stream.write(json.dumps(header, separators=(",", ":")) + "\n")
        frame_no = 0
        while frame_no < limit:
            ok, image = cap.read()
            if not ok:
                break
            timestamp = float(rows[frame_no]["capture_timestamp"])
            detections = observer.detect(image)
            for detection in detections:
                x, y, w, h = map(float, detection.bbox)
                center_y = y + h / 2
                left = geometry.source_x(x, center_y)
                right = geometry.source_x(x + w, center_y)
                item = {
                    "record_type": "observation",
                    "video_frame": frame_no,
                    "capture_timestamp": timestamp,
                    "rectified_bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                    "source_bbox": [round(left, 2), round(y, 2), round(right - left, 2), round(h, 2)],
                    "source_coordinate_system": "encoded_source_frame_px_origin_top_left",
                    "candidate_color": detection.color,
                    "candidate_kind": detection.kind,
                    "candidate_score_uncalibrated": float(detection.score),
                    "candidate_component_id": int(detection.component),
                    "candidate_lane_keys_unverified": list(detection.keys),
                    "ribbon_above_px": float(detection.above),
                    "ribbon_below_px": float(detection.below),
                    "tap_marker_candidate": bool(detection.tap_marker),
                    "legacy_connected_ribbon_candidate": bool(detection.connected_ribbon),
                    "observation_status": "LEGACY_DETECTION_OBSERVATION_ONLY / NOT_GROUND_TRUTH",
                }
                stream.write(json.dumps(item, separators=(",", ":")) + "\n")
                count += 1
            frame_no += 1
        cap.release()
        if frame_no != limit:
            raise ValueError(f"decoded {frame_no}/{limit} requested frames")
    return {"run_id": video.parent.name, "frames_processed": limit, "candidate_observations": count, "output": output.as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_video_or_run_dir", type=Path)
    parser.add_argument("geometry_json", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    parser.add_argument("--max-frames", type=int, default=None, help="bounded diagnostic window only")
    parser.add_argument("--index", type=Path, default=None, help="optional per-frame CSV with video_frame/capture_timestamp")
    args = parser.parse_args()
    video = args.source_video_or_run_dir if args.source_video_or_run_dir.is_file() else args.source_video_or_run_dir / "live_source.mp4"
    default_index = video.parent / "live_video_index.csv"
    index = args.index if args.index is not None else (default_index if default_index.is_file() else None)
    result = observe(video, index, args.geometry_json, args.output_jsonl, args.max_frames)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
