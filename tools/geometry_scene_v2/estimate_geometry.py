#!/usr/bin/env python3
"""Estimate per-run six-lane perspective guides from read-only video evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weighted_median(values: list[tuple[float, float]]) -> float:
    ordered = sorted(values)
    threshold = sum(weight for _, weight in ordered) / 2
    total = 0.0
    for value, weight in ordered:
        total += weight
        if total >= threshold:
            return value
    return ordered[-1][0]


def detect(video: Path, index: Path | None, sample_count: int = 60) -> dict[str, Any]:
    if not isinstance(sample_count, int) or sample_count <= 0:
        raise ValueError("sample_count must be a positive integer")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"cannot decode {video}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frame_count <= 0 or not math.isfinite(fps) or fps <= 0 or width < 64 or height < 64:
        cap.release()
        raise ValueError("video must have at least one frame, finite positive FPS, and dimensions of at least 64x64")
    if index is not None:
        with index.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != frame_count:
            cap.release()
            raise ValueError(f"index/video row mismatch: {len(rows)} != {frame_count}")
        if not rows or "capture_timestamp" not in rows[0]:
            cap.release()
            raise ValueError("index must contain one capture_timestamp value per encoded frame")
        for frame_no, row in enumerate(rows):
            try:
                timestamp = float(row["capture_timestamp"])
                video_frame = int(row["video_frame"]) if "video_frame" in row else frame_no
            except (TypeError, ValueError):
                cap.release()
                raise ValueError(f"index has an invalid frame ID or capture_timestamp at row {frame_no}") from None
            if not math.isfinite(timestamp):
                cap.release()
                raise ValueError(f"index capture_timestamp is not finite at row {frame_no}")
            if "video_frame" in row and video_frame != frame_no:
                cap.release()
                raise ValueError(f"index video_frame order mismatch at {frame_no}")
    else:
        rows = [{"capture_timestamp": f / fps} for f in range(frame_count)]
    sample_frames = np.unique(np.linspace(0, frame_count - 1, sample_count).astype(int))
    samples = []
    for frame_no in sample_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_no))
        ok, image = cap.read()
        if ok:
            samples.append(image)
    cap.release()
    # Short clips naturally produce fewer unique sample indices than the
    # requested target. Measure decode coverage against the indices that
    # actually exist, so clips shorter than sample_count remain supported.
    if len(samples) < len(sample_frames) * 0.9:
        raise ValueError(f"decoded only {len(samples)}/{len(sample_frames)} geometry samples")

    median = np.median(np.stack(samples), axis=0).astype(np.uint8)
    gray = cv2.cvtColor(median, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 45, 130)
    segments = cv2.HoughLinesP(
        edges, 1, np.pi / 720, threshold=max(40, round(height * 0.104)),
        minLineLength=max(45, round(height * 0.076)), maxLineGap=max(10, round(height * 0.025))
    )
    candidates: list[tuple[float, float, float, float, float]] = []
    if segments is not None:
        for segment in segments[:, 0, :]:
            x1, y1, x2, y2 = map(float, segment)
            dy = y2 - y1
            if abs(dy) < height * 0.05:
                continue
            slope = (x2 - x1) / dy
            intercept = x1 - slope * y1
            low_y, high_y = sorted((y1, y2))
            length = math.hypot(x2 - x1, dy)
            if (
                abs(slope) <= 1.2 * (width / 1280) / (height / 720)
                and low_y < height * 0.34
                and high_y > height * 0.42
                and width * 0.39 <= intercept <= width * 0.61
                and length >= height * 0.14
            ):
                candidates.append((slope, intercept, low_y, high_y, length))

    rails: list[dict[str, float]] = []
    slope_scale = (width / 1280) / (height / 720)
    for target in (-0.84, -0.56, -0.28, 0.28, 0.56, 0.84):
        target *= slope_scale
        group = [line for line in candidates if abs(line[0] - target) <= 0.12 * slope_scale]
        if not group:
            raise ValueError(f"no perspective rail evidence near slope {target:+.2f}")
        rails.append(
            {
                "slope_dx_per_dy": weighted_median([(line[0], line[4]) for line in group]),
                "top_intercept_x": weighted_median([(line[1], line[4]) for line in group]),
                "candidate_segments": len(group),
                "max_segment_length_px": max(line[4] for line in group),
            }
        )

    # The converging center boundary is sometimes lost by edge segmentation;
    # interpolate it from the two independently observed inner rails.
    # Very short/compressed clips can quantize converging lane lines to nearby
    # but inconsistent intercepts. Snap only a tightly clustered set to its
    # evidence-weighted common apex; retain each raw fit for traceability.
    intercept_spread = max(line["top_intercept_x"] for line in rails) - min(
        line["top_intercept_x"] for line in rails
    )
    apex_snap_applied = intercept_spread <= width * 0.02
    common_apex_x = None
    if apex_snap_applied:
        common_apex_x = weighted_median([
            (line["top_intercept_x"], line["max_segment_length_px"]) for line in rails
        ])
        for line in rails:
            line["raw_top_intercept_x"] = line["top_intercept_x"]
            line["top_intercept_x"] = common_apex_x
            line["apex_adjustment_px"] = common_apex_x - line["raw_top_intercept_x"]

    # The top of a perspective playfield may converge to a single point, so
    # sorting by y=0 intercept can be unstable. Order boundaries at a measured
    # in-frame reference depth where adjacent lanes are separated.
    reference_y = height * 0.75
    rails.sort(key=lambda line: line["top_intercept_x"] + line["slope_dx_per_dy"] * reference_y)
    left_inner, right_inner = rails[2], rails[3]
    center = {
        "slope_dx_per_dy": (left_inner["slope_dx_per_dy"] + right_inner["slope_dx_per_dy"]) / 2,
        "top_intercept_x": (left_inner["top_intercept_x"] + right_inner["top_intercept_x"]) / 2,
        "derived_from": "midpoint of observed inner rails; center edge not independently fit",
    }
    boundaries = [*rails[:3], center, *rails[3:]]
    band_start, band_end = round(height * 0.75), round(height * 0.86)
    judgment_band = edges[band_start:band_end, round(width * 0.027):round(width * 0.973)]
    row_score = (judgment_band > 0).sum(axis=1)
    peaks = sorted(range(len(row_score)), key=lambda i: int(row_score[i]), reverse=True)
    pair = next(
        ((a, b) for ai, a in enumerate(peaks) for b in peaks[ai + 1 :] if abs(a - b) >= height * 0.028),
        None,
    )
    if pair is None:
        raise ValueError("could not find the two horizontal edges of the judgment band")
    y_edges = sorted((band_start + pair[0], band_start + pair[1]))
    judgment_y = sum(y_edges) / 2

    for y in (height * 0.028, height * 0.472, judgment_y):
        boundary_x = [line["top_intercept_x"] + line["slope_dx_per_dy"] * y for line in boundaries]
        if any(right <= left for left, right in zip(boundary_x, boundary_x[1:])):
            raise ValueError(f"estimated lane boundaries cross or collapse at y={y:.2f}; geometry is ambiguous")

    guide_paths = []
    for lane in range(6):
        left, right = boundaries[lane], boundaries[lane + 1]
        points = []
        for y in (height * 0.028, height * 0.472, judgment_y):
            lx = left["top_intercept_x"] + left["slope_dx_per_dy"] * y
            rx = right["top_intercept_x"] + right["slope_dx_per_dy"] * y
            points.append([round((lx + rx) / 2, 2), round(y, 2)])
        guide_paths.append(points)

    sample_trace = [
        {
            "video_frame": int(frame_no),
            "capture_timestamp": float(rows[int(frame_no)]["capture_timestamp"]),
        }
        for frame_no in sample_frames
    ]
    return {
        "schema": "geometry_scene_v2.run_geometry.v1",
        "run_id": video.parent.name,
        "truth_status": "AUTO_GEOMETRY_ESTIMATE / PROVISIONAL",
        "source": {
            "video_path": video.as_posix(),
            "video_sha256": sha256(video),
            "index_path": index.as_posix() if index is not None else None,
            "index_sha256": sha256(index) if index is not None else None,
            "timestamp_source": "read_only_index_capture_timestamp" if index is not None else "encoded_video_frame_index_divided_by_this_clip_fps",
            "frame_count": frame_count,
            "fps": fps,
            "resolution": [width, height],
            "sampled_frame_trace": sample_trace,
        },
        "coordinate_system": "encoded_source_frame_px_origin_top_left",
        "method": "temporal_median_edges_hough_rails; six rail slope clusters plus interpolated center boundary",
        "track_count": 6,
        "track_guides": guide_paths,
        "judgment_line_y": round(judgment_y, 2),
        "judgment_band_edge_rows": y_edges,
        "judgment_row_edge_support": [int(row_score[y - band_start]) for y in y_edges],
        "rail_boundaries": boundaries,
        "rail_order_reference_y": round(reference_y, 2),
        "converged_apex_snap": {
            "applied": apex_snap_applied,
            "raw_intercept_spread_px": round(intercept_spread, 2),
            "threshold_px": round(width * 0.02, 2),
            "common_apex_x": round(common_apex_x, 2) if common_apex_x is not None else None,
        },
        "caveats": [
            "Geometry is a machine estimate and is not manual ground truth.",
            "Center boundary is interpolated when Hough edge evidence is fragmented.",
            "This geometry pass detects no notes and makes no note identity or speed claims.",
            "Comparison synchronization should pair encoded frame indices and retain capture timestamps as separate provenance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="a video, a recording run directory, or a directory of runs")
    parser.add_argument("output", type=Path, help="geometry JSON path for one video, or output directory for batch runs")
    parser.add_argument("--index", type=Path, default=None, help="optional per-frame CSV index with video_frame and capture_timestamp")
    args = parser.parse_args()
    if args.input.is_file():
        result = detect(args.input, args.index)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"status": "AUTO_GEOMETRY_ESTIMATE / PROVISIONAL", "output": args.output.as_posix(), "judgment_y": result["judgment_line_y"], "frames": result["source"]["frame_count"]}, indent=2))
        return
    if args.input.is_dir() and (args.input / "live_source.mp4").is_file():
        runs = [args.input]
    else:
        runs = sorted(path for path in args.input.iterdir() if path.is_dir())
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for run in runs:
        video = run / "live_source.mp4"
        index = args.index if args.index is not None else (run / "live_video_index.csv" if (run / "live_video_index.csv").exists() else None)
        result = detect(video, index)
        destination = args.output / f"{run.name}.json"
        destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
        results.append({"run_id": run.name, "output": destination.as_posix(), "judgment_y": result["judgment_line_y"], "frames": result["source"]["frame_count"]})
    print(json.dumps({"status": "AUTO_GEOMETRY_ESTIMATE / PROVISIONAL", "runs": results}, indent=2))


if __name__ == "__main__":
    main()
