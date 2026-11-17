"""Profile a bounded, deterministic Geometry Video V1 source window."""
from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.render_geometry_video import candidate_dict, ffmpeg_writer
from src.geometry_video.geometry import VideoGeometry
from src.geometry_video.renderer import render_geometry_frame
from src.geometry_video.segmenter import PixelGeometryConverter

RUN_ID = "run_20261106T164049_800126Z"
FRAME_COUNT = 120


def timed_cv2(samples: dict[str, list[float]]):
    """Wrap only known stage calls; preserve results and native behavior."""
    names = {
        "cvtColor": "conversion",
        "inRange": "mask_ops",
        "bitwise_and": "mask_ops",
        "morphologyEx": "mask_ops",
        "connectedComponentsWithStats": "connected_components",
        "findContours": "segmenter_other",
        "arcLength": "segmenter_other",
        "approxPolyDP": "segmenter_other",
        "Canny": "segmenter_other",
        "HoughLinesP": "segmenter_other",
    }
    originals = {}
    def install(name):
        original = getattr(cv2, name)
        originals[name] = original
        def wrapped(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                stage = names[name]
                elapsed = time.perf_counter() - start
                # cvtColor is split by conversion code to report HSV and gray.
                if name == "cvtColor":
                    code = args[1] if len(args) > 1 else kwargs.get("code")
                    stage = "hsv_conversion" if code == cv2.COLOR_BGR2HSV else (
                        "gray_conversion" if code == cv2.COLOR_BGR2GRAY else "conversion")
                samples[stage].append(elapsed)
        setattr(cv2, name, wrapped)
    for name in names:
        install(name)
    return originals


def restore_cv2(originals):
    for name, original in originals.items():
        setattr(cv2, name, original)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--geometry", type=Path, default=Path("config/geometry_video_v1.json"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/performance"))
    parser.add_argument("--label", default="", help="Optional output suffix to preserve prior profiles")
    args = parser.parse_args()
    source_path = args.recording_root / RUN_ID / "live_source.mp4"
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = f"_{args.label}" if args.label else ""
    video_path = args.out / f"{RUN_ID}_first{FRAME_COUNT}_geometry{suffix}.mp4"
    if video_path.exists():
        raise FileExistsError(f"Refusing to overwrite profile encode: {video_path}")

    samples: dict[str, list[float]] = {key: [] for key in (
        "source_decode", "hsv_conversion", "gray_conversion", "mask_ops",
        "connected_components", "segmenter_other", "pixel_segmentation_total", "temporal_association",
        "data_conversion_serialization", "geometry_rendering", "hconcat",
        "encode_write", "encode", "end_to_end")}
    geometry = VideoGeometry(args.geometry)
    converter = PixelGeometryConverter(geometry)
    source = cv2.VideoCapture(str(source_path))
    if not source.isOpened():
        raise RuntimeError(f"Cannot decode {source_path}")
    fps = source.get(cv2.CAP_PROP_FPS) or 60.0
    writer = ffmpeg_writer(video_path, geometry.width * 2, geometry.height, fps, 28)
    originals = timed_cv2(samples)
    total_start = time.perf_counter()
    frame_count = 0
    try:
        for frame_no in range(FRAME_COUNT):
            start = time.perf_counter()
            ok, frame = source.read()
            samples["source_decode"].append(time.perf_counter() - start)
            if not ok:
                raise RuntimeError(f"Source decode ended at frame {frame_no}")
            # This source is already 1280x720 native pixels; no resize,
            # normalization, perspective warp, or rectification is used.
            start = time.perf_counter()
            objects, uncertain = converter.segment(frame)
            samples["pixel_segmentation_total"].append(time.perf_counter() - start)
            start = time.perf_counter()
            geo = render_geometry_frame(geometry, objects)
            samples["geometry_rendering"].append(time.perf_counter() - start)
            start = time.perf_counter()
            compare = cv2.hconcat((frame, geo))
            samples["hconcat"].append(time.perf_counter() - start)
            start = time.perf_counter()
            # Exercise the pipeline's JSON object conversion and serialization
            # on this frame; no analysis artifact is written per frame.
            record = {"run_id": RUN_ID, "frame_id": frame_no,
                      "instances": [candidate_dict(c, frame_no, RUN_ID, n)
                                    for n, c in enumerate(objects)],
                      "uncertain_candidates": [candidate_dict(c, frame_no, RUN_ID, n + len(objects))
                                               for n, c in enumerate(uncertain)]}
            json.dumps(record, separators=(",", ":"))
            csv.writer(io.StringIO(newline="")).writerow((frame_no, len(objects), len(uncertain)))
            samples["data_conversion_serialization"].append(time.perf_counter() - start)
            if writer.poll() is not None:
                raise RuntimeError("ffmpeg exited before profiling encode completed")
            start = time.perf_counter()
            writer.stdin.write(compare.tobytes())
            samples["encode_write"].append(time.perf_counter() - start)
            frame_count += 1
    finally:
        restore_cv2(originals)
        source.release()
    encode_start = time.perf_counter()
    writer.stdin.close()
    stderr = writer.stderr.read().decode("utf-8", errors="replace")
    code = writer.wait()
    samples["encode"].append(time.perf_counter() - encode_start)
    samples["end_to_end"].append(time.perf_counter() - total_start)
    if code:
        raise RuntimeError(f"ffmpeg failed ({code}): {stderr[-4000:]}")

    # The current pipeline has no tracker, so temporal association is absent.
    samples.pop("temporal_association")
    samples.pop("normalization_rectification") if "normalization_rectification" in samples else None
    statuses = {"temporal_association": "NOT_IMPLEMENTED",
                "normalization_rectification": "NOT_IMPLEMENTED"}
    status_map = {"hsv_conversion": "MEASURED", "gray_conversion": "MEASURED",
                  "mask_ops": "MEASURED", "connected_components": "MEASURED",
                  "segmenter_other": "MEASURED", "source_decode": "MEASURED",
                  "pixel_segmentation_total": "MEASURED",
                  "data_conversion_serialization": "MEASURED", "geometry_rendering": "MEASURED",
                  "hconcat": "MEASURED", "encode_write": "MEASURED", "encode": "MEASURED",
                  "end_to_end": "MEASURED"}
    rows = []
    for stage in ["source_decode", "hsv_conversion", "gray_conversion", "mask_ops",
                  "connected_components", "temporal_association", "segmenter_other", "pixel_segmentation_total",
                  "normalization_rectification",
                  "data_conversion_serialization", "geometry_rendering", "hconcat",
                  "encode_write", "encode", "end_to_end"]:
        values = samples.get(stage, [])
        status = statuses.get(stage, status_map.get(stage, "NOT_IMPLEMENTED" if not values else "MEASURED"))
        rows.append({"stage": stage, "status": status, "samples": len(values),
                     "median_ms": round(statistics.median(values) * 1000, 4) if values else "",
                     "p95_ms": round(float(np.percentile(values, 95)) * 1000, 4) if values else ""})
    report = {
        "pipeline": "Geometry Video V1 offline renderer",
        "run_id": RUN_ID, "window": {"start_frame": 0, "frame_count": frame_count},
        "source": str(source_path), "source_resolution": [geometry.width, geometry.height],
        "source_pixels": "Already native pixels; normalize/rectify is not used.",
        "encode": {"performed": True, "output": str(video_path), "format": "H.264 via ffmpeg, comparison hconcat"},
        "measurement_notes": {
            "opencv_calls": "Instrumented cv2.cvtColor, mask operations, connected components, and named segmenter operations.",
            "mask_component_breakdown": "OpenCV call timing excludes Python loops and candidate postprocessing, shown as segmenter_other only for wrapped calls.",
            "serialization": "In-memory candidate conversion, JSON dump, and CSV row formatting; filesystem output costs excluded.",
            "encode": "encode_write measures pipe write/backpressure; includes actual ffmpeg encoding on this window.",
        },
        "stages": rows,
    }
    json_path = args.out / f"{RUN_ID}_profile{suffix}.json"
    csv_path = args.out / f"{RUN_ID}_profile{suffix}.csv"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer_csv = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer_csv.writeheader()
        writer_csv.writerows(rows)
    print(json.dumps({"frames": frame_count, "json": str(json_path), "csv": str(csv_path),
                      "encoded_video": str(video_path), "stage_count": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
