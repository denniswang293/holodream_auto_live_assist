#!/usr/bin/env python3
"""Build one provisional Hold candidate from a source-specific green component trace.

This diagnostic does not promote component counts or masks to ground truth. It
records measured per-frame endpoints for review, and labels short component
merges as retrospective occlusion in the candidate Scene.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import median
import sys
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from observe_notes import RunGeometry
from reconstruct_scene import _component_extents, _native_x
from src.perception import Perception


def add_candidate(
    source_run: Path,
    geometry_path: Path,
    base_scene_path: Path,
    output_scene_path: Path,
    start_frame: int,
    end_frame: int,
    min_rectified_x: float = 300.0,
    max_bottom_x: float | None = None,
    candidate_id: str = "note:round51_right_component_hold",
    max_tail_step_px: float = 125.0,
) -> dict[str, Any]:
    geometry_doc = json.loads(geometry_path.read_text(encoding="utf-8"))
    scene = json.loads(base_scene_path.read_text(encoding="utf-8"))
    video = source_run / "live_source.mp4"
    index = source_run / "live_video_index.csv"
    with index.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != int(scene["frame_count"]):
        raise ValueError("source index/frame-count mismatch")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"cannot decode {video}")
    geometry = RunGeometry(geometry_doc)
    perception = Perception(geometry)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    observed: list[dict[str, Any]] = []
    merged_frames: list[int] = []
    for frame in range(start_frame, end_frame + 1):
        ok, image = cap.read()
        if not ok:
            cap.release()
            raise ValueError(f"decode failed at frame {frame}")
        perception.detect(image)
        extents = _component_extents(perception.last_path)
        candidates = []
        merged = False
        for component_id, extent in extents.items():
            x, y, width, height = extent["bbox"]
            bottom_x, bottom_y = extent["bottom"]
            bottom_left, bottom_right = extent["bottom_band_x_span"]
            if height < 64 or bottom_y < geometry.hit_y - 5:
                continue
            if max_bottom_x is not None and bottom_right > max_bottom_x:
                continue
            if x < min_rectified_x and x + width > min_rectified_x + 150:
                merged = True
                continue
            if x < min_rectified_x:
                continue
            top_x, top_y = extent["top"]
            if not (top_y < bottom_y and abs(bottom_y - geometry.hit_y) <= 6):
                continue
            candidates.append({
                "frame": frame,
                "capture_timestamp": float(rows[frame]["capture_timestamp"]),
                "component_id_observation": int(component_id),
                "rectified_bbox": [int(v) for v in extent["bbox"]],
                "top_rectified_xy": [round(top_x, 2), round(top_y, 2)],
                "bottom_rectified_xy": [round(bottom_x, 2), round(bottom_y, 2)],
                "bottom_band_x_span": [round(extent["bottom_band_x_span"][0], 2), round(extent["bottom_band_x_span"][1], 2)],
                "area_px": int(extent["area"]),
            })
        if candidates:
            # Preserve same-frame ambiguity instead of choosing by count.
            if len(candidates) != 1:
                merged_frames.append(frame)
            else:
                observed.append(candidates[0])
        elif merged:
            merged_frames.append(frame)
    cap.release()
    if len(observed) < 8:
        raise ValueError(f"insufficient unique component observations: {len(observed)}")

    # Connected-component IDs are frame-local and cannot establish identity.
    # Keep only the continuous prefix whose source-space tail endpoint does not
    # jump farther than the configured bound between adjacent observations.
    continuity_observed: list[dict[str, Any]] = []
    rejected_continuity: list[dict[str, Any]] = []
    for point in observed:
        if continuity_observed:
            previous = continuity_observed[-1]
            previous_x = _native_x(geometry, previous["top_rectified_xy"][0], previous["top_rectified_xy"][1])
            current_x = _native_x(geometry, point["top_rectified_xy"][0], point["top_rectified_xy"][1])
            step = abs(current_x - previous_x)
            if step > max_tail_step_px:
                rejected_continuity.append({
                    "frame": point["frame"],
                    "previous_frame": previous["frame"],
                    "previous_tail_x": round(previous_x, 2),
                    "candidate_tail_x": round(current_x, 2),
                    "horizontal_step_px": round(step, 2),
                    "limit_px": max_tail_step_px,
                    "reason": "component endpoint discontinuity; identity not linked",
                })
                break
        continuity_observed.append(point)
    observed = continuity_observed
    if len(observed) < 8:
        raise ValueError(f"insufficient continuous component observations: {len(observed)}")

    frames = [point["frame"] for point in observed]
    intervals: list[dict[str, Any]] = []
    run_start = previous = frames[0]
    for frame in frames[1:]:
        if frame == previous + 1:
            previous = frame
            continue
        gap = frame - previous - 1
        intervals.append({"state": "visible", "start_frame": run_start, "end_frame": previous + 1})
        if gap <= 5 and all(previous < merged_frame < frame for merged_frame in merged_frames):
            intervals.append({
                "state": "occluded", "start_frame": previous + 1, "end_frame": frame,
                "labels": ["INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"],
                "reason": "separate lower-board components merged; per-frame identity is not directly separable",
            })
        else:
            raise ValueError(f"unexplained observation gap {previous + 1}-{frame - 1}")
        run_start = previous = frame
    intervals.append({"state": "visible", "start_frame": run_start, "end_frame": previous + 1})

    stable_head_widths: list[float] = []
    for point in observed:
        rect_left, rect_right = point["bottom_band_x_span"]
        rect_width = rect_right - rect_left
        bbox_width = point["rectified_bbox"][2]
        if rect_width >= 150 and bbox_width >= 200:
            stable_head_widths.append(abs(
                _native_x(geometry, rect_right, point["bottom_rectified_xy"][1])
                - _native_x(geometry, rect_left, point["bottom_rectified_xy"][1])
            ))
    if not stable_head_widths:
        raise ValueError("no stable lower-band width observations")
    head_width = round(float(median(stable_head_widths)), 2)
    same_run_head_heights = [
        float(key["head_height"])
        for note in scene["notes"] if note.get("type") == "Hold"
        for key in note.get("keyframes", [])
        if key.get("source_observation_kind") == "hold_head"
        and key.get("head_y", 0) >= geometry.hit_y - 40
        and 4 <= float(key.get("head_height", 0)) <= 14
    ]
    head_height = round(float(median(same_run_head_heights)), 2) if same_run_head_heights else 6.0

    keyframes = []
    for point in observed:
        head_rx, head_ry = point["bottom_rectified_xy"]
        tail_rx, tail_ry = point["top_rectified_xy"]
        span_left, span_right = point["bottom_band_x_span"]
        source_head_x = _native_x(geometry, head_rx, head_ry)
        source_tail_x = _native_x(geometry, tail_rx, tail_ry)
        source_left = _native_x(geometry, span_left, head_ry)
        source_right = _native_x(geometry, span_right, head_ry)
        bx, by, bw, bh = point["rectified_bbox"]
        source_bbox_left = _native_x(geometry, bx, head_ry)
        source_bbox_right = _native_x(geometry, bx + bw, head_ry)
        keyframes.append({
            "frame": point["frame"],
            "capture_timestamp": point["capture_timestamp"],
            "head_x": round(source_head_x, 2), "head_y": round(head_ry, 2),
            "tail_x": round(source_tail_x, 2), "tail_y": round(tail_ry, 2),
            "head_width": head_width, "head_height": head_height,
            "source_bbox": [round(min(source_bbox_left, source_bbox_right), 2), by, round(abs(source_bbox_right - source_bbox_left), 2), bh],
            "source_observation_kind": "green_component_endpoint_candidate",
            "head_source": "OBSERVED_GREEN_COMPONENT_BOTTOM_ENDPOINT / PROVISIONAL / NOT_GROUND_TRUTH",
            "tail_source": "OBSERVED_GREEN_COMPONENT_TOP_ENDPOINT / PROVISIONAL / NOT_GROUND_TRUTH",
            "candidate_component_id_observation": point["component_id_observation"],
            "candidate_component_bbox_rectified": point["rectified_bbox"],
            "candidate_component_area_px": point["area_px"],
        })

    existing_ids = {note["id"] for note in scene["notes"]}
    note_id = candidate_id
    if note_id in existing_ids:
        raise ValueError(f"candidate id already exists: {note_id}")
    lane = min(5, max(0, int(observed[len(observed) // 2]["bottom_rectified_xy"][0] // geometry.lane_pixels)))
    scene["notes"].append({
        "id": note_id, "type": "Hold", "lane": lane,
        "confidence": 0.25,
        "confidence_status": "AUTO_HEURISTIC / NOT_CALIBRATED / PROVISIONAL",
        "color": "#62E57A",
        "source": {
            "coordinate_system": "encoded_source_frame_px_origin_top_left",
            "provenance": "source-specific rectified green-component endpoints; not ground truth",
            "video_sha256": scene["source"]["video_sha256"],
            "index_sha256": scene["source"]["index_sha256"],
            "geometry_sha256": scene["source"]["geometry_sha256"],
        },
        "intervals": intervals, "keyframes": keyframes,
        "association_status": "AUTO_VISUAL_REVIEWED / PROVISIONAL / NOT_GROUND_TRUTH",
        "head_body_tail_evidence": {
            "observed_green_components": len(keyframes),
            "merged_component_frames_unresolved": merged_frames,
            "tail_horizontal_step_limit_px": max_tail_step_px,
            "rejected_discontinuous_observations": rejected_continuity,
            "review_label": "NOT_GROUND_TRUTH",
        },
    })
    scene["candidate_summary_not_ground_truth"]["scene_note_candidates"] += 1
    scene.setdefault("review_queue", []).append({
        "candidate_id": note_id,
        "candidate_kind": "hold",
        "first_frame": frames[0],
        "last_frame": frames[-1],
        "observations": len(keyframes),
        "status": "PROVISIONAL_SCENE_SPECIFIC_COMPONENT_CANDIDATE",
        "reason": "separate lower-board green component trace; head identity and merged-frame ownership remain unconfirmed",
    })
    scene["automatic_visual_review"] = {
        "status": "AUTO_VISUAL_REVIEWED / PROVISIONAL",
        "scope": f"Sparse visual review plus source-specific component-Hold observations in frames {frames[0]}-{frames[-1]}; this is not frame-complete review or ground truth.",
    }
    scene["reconstruction_method"] += "; source-specific component Hold candidate from direct per-frame green-component endpoint observations; provisional and not ground truth"
    scene["notes"].sort(key=lambda note: note["id"])
    output_scene_path.parent.mkdir(parents=True, exist_ok=True)
    output_scene_path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "candidate_id": note_id, "lane": lane, "observed_frames": frames,
        "merged_frames_unresolved": merged_frames, "intervals": intervals,
        "keyframes": keyframes, "output_scene": output_scene_path.as_posix(),
        "rejected_continuity_observations": rejected_continuity,
        "selection": {"min_rectified_x": min_rectified_x, "max_bottom_x": max_bottom_x},
        "max_tail_step_px": max_tail_step_px,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_run", type=Path)
    parser.add_argument("geometry_json", type=Path)
    parser.add_argument("base_scene", type=Path)
    parser.add_argument("output_scene", type=Path)
    parser.add_argument("--start-frame", type=int, required=True)
    parser.add_argument("--end-frame", type=int, required=True)
    parser.add_argument("--min-rectified-x", type=float, default=300.0)
    parser.add_argument("--max-bottom-x", type=float, default=None,
                        help="keep components whose observed bottom-band right edge does not exceed this rectified x")
    parser.add_argument("--candidate-id", default="note:round51_right_component_hold")
    parser.add_argument("--max-tail-step-px", type=float, default=125.0,
                        help="stop the observed candidate prefix at a larger source-space tail-x jump")
    args = parser.parse_args()
    result = add_candidate(
        args.source_run, args.geometry_json, args.base_scene, args.output_scene,
        args.start_frame, args.end_frame, args.min_rectified_x, args.max_bottom_x,
        args.candidate_id, args.max_tail_step_px,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
