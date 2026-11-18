#!/usr/bin/env python3
"""Offline, provisional Scene Timeline builder for one complete recording run.

This tool reuses Legacy Perception and Tracker as observation/association
proposals only. Its output is explicitly provisional and never ground truth.
It reads the source MP4/index and per-run geometry; it does not read key events
or write to Live/Tracking code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from observe_notes import RunGeometry, sha256
from src.tracking import Tracker
from offline_perception import OfflinePerception
from scene_refinement import refine_scene_track_discontinuities


def _native_x(geometry: RunGeometry, rect_x: float, y: float) -> float:
    return geometry.source_x(rect_x, y)


def _unique_lane_near_component(
    candidates: list[dict[str, Any]], rect_x: float, max_distance: float,
    ambiguity_margin: float = 12.0,
) -> dict[str, Any] | None:
    """Choose a directly observed unowned component only when lane-near and unique."""
    nearby = sorted(
        (candidate for candidate in candidates
         if abs(candidate["bottom_x"] - rect_x) <= max_distance),
        key=lambda candidate: abs(candidate["bottom_x"] - rect_x),
    )
    if not nearby:
        return None
    if (len(nearby) > 1 and
            abs(nearby[1]["bottom_x"] - rect_x)
            - abs(nearby[0]["bottom_x"] - rect_x) <= ambiguity_margin):
        return None
    return nearby[0]


def _retained_direct_head_points(points: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """Keep only detector observations that directly describe a note head."""
    candidate_kind = "tap" if kind == "tap" else "hold_head" if kind == "hold" else None
    if candidate_kind is None:
        return []
    return [point for point in points if point["candidate_kind"] == candidate_kind]


def _majority_candidate_color(
    points: list[dict[str, Any]], kind: str, fallback_colors: list[str],
) -> str:
    """Choose note color from retained head observations, falling back only if absent."""
    head_colors = [
        point["candidate_color"]
        for point in _retained_direct_head_points(points, kind)
    ]
    colors = head_colors or fallback_colors
    return max(set(colors), key=colors.count)


def _observation_evidence_summary(
    points: list[dict[str, Any]], kind: str, confirmed: bool, kind_locked: bool,
    sample_limit: int = 12,
) -> dict[str, Any]:
    """Summarize unresolved detector observations without asserting note identity."""
    kind_counts: dict[str, int] = {}
    color_counts: dict[str, int] = {}
    for point in points:
        candidate_kind = str(point["candidate_kind"])
        candidate_color = str(point["candidate_color"])
        kind_counts[candidate_kind] = kind_counts.get(candidate_kind, 0) + 1
        color_counts[candidate_color] = color_counts.get(candidate_color, 0) + 1

    direct_heads = _retained_direct_head_points(points, kind)
    def sample(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if sample_limit <= 0 or not values:
            return []
        count = min(sample_limit, len(values))
        if count == 1:
            return [values[0]]
        indices = [round(index * (len(values) - 1) / (count - 1)) for index in range(count)]
        return [values[index] for index in indices]

    sampled_heads = sample(direct_heads)
    sampled_observations = sample(points)

    def value_range(axis: str) -> list[float] | None:
        values = [float(point[axis]) for point in points if point.get(axis) is not None]
        return [round(min(values), 2), round(max(values), 2)] if values else None

    return {
        "labels": ["PROVISIONAL", "NOT_GROUND_TRUTH", "DETECTOR_OBSERVATION_SUMMARY"],
        "observation_counts": {
            "by_candidate_kind": dict(sorted(kind_counts.items())),
            "by_candidate_color": dict(sorted(color_counts.items())),
            "direct_same_kind_head": len(direct_heads),
        },
        "tracker": {"confirmed": bool(confirmed), "kind_locked": bool(kind_locked)},
        "rectified_x_range_px": value_range("rectified_x"),
        "rectified_y_range_px": value_range("rectified_y"),
        "sampled_direct_head_observations": [
            {
                "frame": int(point["frame"]),
                "rectified_xy_px": [round(float(point["rectified_x"]), 2), round(float(point["rectified_y"]), 2)],
                "source_xy_px": [round(float(point["head_x"]), 2), round(float(point["head_y"]), 2)],
                "color": point["candidate_color"],
                "score_uncalibrated": round(float(point["candidate_score_uncalibrated"]), 4),
            }
            for point in sampled_heads
        ],
        "sampled_candidate_observations": [
            {
                "frame": int(point["frame"]),
                "capture_timestamp": round(float(point["capture_timestamp"]), 7),
                "candidate_kind": str(point["candidate_kind"]),
                "candidate_color": str(point["candidate_color"]),
                "score_uncalibrated": round(float(point["candidate_score_uncalibrated"]), 4),
                "source_bbox_px": [round(float(value), 2) for value in point["source_bbox"]],
                "rectified_bbox_px": [round(float(value), 2) for value in point["detector_rectified_bbox"]],
                "source_bbox_center_px_not_head_truth": [
                    round(float(point["source_bbox"][0]) + float(point["source_bbox"][2]) / 2, 2),
                    round(float(point["source_bbox"][1]) + float(point["source_bbox"][3]) / 2, 2),
                ],
                "labels": ["DETECTOR_OBSERVATION_ONLY", "NOT_GROUND_TRUTH"],
            }
            for point in sampled_observations
        ],
    }


def _component_extents(path: Any) -> dict[int, dict[str, Any]]:
    """Return observed vertical endpoints for each connected ribbon component.

    These are mask-derived observations only. They are never promoted to note
    identity truth, and callers must keep ambiguous shared components unresolved.
    """
    if path is None:
        return {}
    closed = cv2.morphologyEx(path, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    ys, xs = np.nonzero(labels)
    if not len(xs):
        return {}
    values = labels[ys, xs]
    order = np.argsort(values, kind="stable")
    values, ys, xs = values[order], ys[order], xs[order]
    starts = np.r_[0, np.flatnonzero(np.diff(values)) + 1]
    ends = np.r_[starts[1:], len(values)]
    result: dict[int, dict[str, Any]] = {}
    for start, end in zip(starts, ends):
        component = int(values[start])
        if component == 0:
            continue
        cy, cx = ys[start:end], xs[start:end]
        top, bottom = int(cy.min()), int(cy.max())
        top_x = float(np.mean(cx[cy <= top + 2]))
        bottom_x = float(np.mean(cx[cy >= bottom - 2]))
        bottom_band = cx[cy >= bottom - 2]
        x, y, w, h, area = map(int, stats[component])
        result[component] = {
            "top": [top_x, float(top)], "bottom": [bottom_x, float(bottom)],
            "bottom_band_x_span": [float(bottom_band.min()), float(bottom_band.max())],
            "bbox": [x, y, w, h], "area": area,
        }
    return result


def _cut_component_options(
    extents: dict[int, dict[str, Any]], bbox: tuple[float, float],
    rect_y: float, cut_y: int, lane_pixels: float,
) -> list[tuple[int, dict[str, Any]]]:
    """Find narrow cut-mask components that visibly reach the cut near a head."""
    bx, bw = bbox
    if bw <= 0 or abs(cut_y - rect_y) > 100:
        return []
    options = []
    for component_id, extent in extents.items():
        x, y, width, height = extent["bbox"]
        if height < 64 or width > lane_pixels * 1.25 or y + height < cut_y - 3:
            continue
        overlap = max(0.0, min(bx + bw, x + width) - max(bx, x))
        if overlap / bw < 0.80:
            continue
        if extent["top"][1] >= cut_y:
            continue
        options.append((component_id, extent))
    return options


def _unique_cut_matches(
    options_by_track: dict[str, list[tuple[int, dict[str, Any]]]],
) -> dict[str, tuple[int, dict[str, Any]]]:
    """Accept only one-to-one geometric matches; ambiguity stays unresolved."""
    owners: dict[int, set[str]] = {}
    for track_id, options in options_by_track.items():
        for component_id, _ in options:
            owners.setdefault(component_id, set()).add(track_id)
    return {
        track_id: options[0]
        for track_id, options in options_by_track.items()
        if len(options) == 1 and len(owners[options[0][0]]) == 1
    }


def _associate_native_cyan_tap_observations(
    observations: list[dict[str, Any]], histories: dict[str, dict[str, Any]], lane_pixels: float,
) -> list[dict[str, Any]]:
    """Attach a missed tracker frame only to one confirmed, locally aligned Tap path.

    The candidate itself is a directly measured native-frame face. Identity is
    linked retrospectively only when a same-color confirmed Tap has multiple
    direct observations before the candidate and one direct observation after
    it in the same lane, and the short, clip-local interpolation predicts the
    candidate uniquely. Thin fragment tracks cannot claim the full face. The
    interpolation is an association gate, not a speed model; no cross-song or
    fixed-speed assumption is used.
    """
    accepted: list[dict[str, Any]] = []
    for observation in sorted(observations, key=lambda point: (point["frame"], point["rectified_x"])):
        frame = int(observation["frame"])
        color = str(observation["candidate_color"])
        represented = any(
            point["frame"] == frame and point.get("candidate_kind") == "tap"
            and point.get("candidate_color") == color
            and _bbox_iou(point.get("detector_rectified_bbox", []), observation["detector_rectified_bbox"]) >= 0.50
            for rec in histories.values() for point in rec["points"]
        )
        if represented:
            continue

        matches: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], float, float, float, float]] = []
        for track_id, rec in histories.items():
            kinds = [kind for kind in rec["kind_history"] if kind in ("tap", "hold")]
            if (not rec["confirmed_seen"] or not kinds or kinds.count("tap") <= kinds.count("hold")):
                continue
            points = sorted(
                (point for point in rec["points"]
                 if point.get("candidate_kind") == "tap" and point.get("candidate_color") == color),
                key=lambda point: point["frame"],
            )
            if len(points) < 3:
                continue
            left_anchors = [point for point in points if int(point["frame"]) < frame]
            right_anchors = [point for point in points if int(point["frame"]) > frame]
            if not left_anchors or not right_anchors:
                continue
            previous, last = left_anchors[-2:] if len(left_anchors) >= 2 else (None, left_anchors[-1])
            following = right_anchors[0]
            left_gap = frame - int(last["frame"])
            bracket_span = int(following["frame"]) - int(last["frame"])
            if (previous is None or not 1 <= left_gap <= 3
                    or int(following["frame"]) <= frame
                    or int(float(last["rectified_x"]) // lane_pixels) != int(observation["lane"])):
                continue
            if bracket_span <= 1 or bracket_span > 8:
                continue
            fraction = left_gap / bracket_span
            expected_x = float(last["head_x"]) + fraction * (float(following["head_x"]) - float(last["head_x"]))
            expected_y = float(last["head_y"]) + fraction * (float(following["head_y"]) - float(last["head_y"]))
            measured_x = float(observation["head_x"])
            measured_y = float(observation["head_y"])
            last_box = last["source_bbox"]
            x_error, y_error = abs(measured_x - expected_x), abs(measured_y - expected_y)
            x_tolerance = max(24.0, float(last_box[2]) * 0.18)
            y_tolerance = max(18.0, float(last_box[3]) * 0.50)
            if x_error <= x_tolerance and y_error <= y_tolerance:
                matches.append((track_id, previous, last, following, x_error, y_error, x_tolerance, y_tolerance))

        if len(matches) != 1:
            continue
        track_id, previous, last, following, x_error, y_error, x_tolerance, y_tolerance = matches[0]
        rec = histories[track_id]
        point = {
            "frame": frame,
            "capture_timestamp": float(observation["capture_timestamp"]),
            "rectified_x": float(observation["rectified_x"]),
            "rectified_y": float(observation["rectified_y"]),
            "head_x": float(observation["head_x"]),
            "head_y": float(observation["head_y"]),
            "source_bbox": [round(float(value), 2) for value in observation["source_bbox"]],
            "detector_rectified_bbox": [float(value) for value in observation["detector_rectified_bbox"]],
            "candidate_kind": "tap",
            "candidate_color": color,
            "candidate_score_uncalibrated": float(observation["candidate_score_uncalibrated"]),
            "recovery_only": False,
            "upper_ribbon_px": 0.0,
            "lower_ribbon_px": 0.0,
            "tail_x_estimate": float(observation["head_x"]),
            "tail_y_estimate": float(observation["head_y"]),
            "tail_source": "TAP_HAS_NO_HOLD_TAIL",
            "retrospective_association": {
                "status": "OFFLINE_RETROSPECTIVE_NATIVE_TAP_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH",
                "track_id": track_id,
            "direct_anchor_frames": [int(last["frame"]), int(following["frame"])],
                "direct_observation_frame": frame,
                "source_motion_prediction_error_px": {"x": round(x_error, 2), "y": round(y_error, 2)},
                "source_motion_tolerance_px": {"x": round(x_tolerance, 2), "y": round(y_tolerance, 2)},
                "candidate_evidence": ["DIRECT_NATIVE_CYAN_FACE_EDGE_PAIR", "NOT_GROUND_TRUTH"],
                "competing_confirmed_track_matches": 0,
                "rule": "One unrepresented native-face observation is linked only to a unique confirmed same-color Tap in the same lane, bracketed by multiple direct heads on the left and one direct head on the right within an eight-frame local span, and aligned with the short local source-coordinate interpolation. The interpolation is not a fixed-speed model.",
            },
            "scene_source_observation_kind": "OFFLINE_NATIVE_CYAN_FACE_RETROSPECTIVE_ASSOCIATED",
        }
        rec["points"].append(point)
        rec["points"].sort(key=lambda item: item["frame"])
        rec["last_frame"] = max(int(rec["last_frame"]), frame)
        accepted.append({
            "track_id": track_id,
            "frame": frame,
            "source_bbox_px": point["source_bbox"],
            "anchor_frame": int(last["frame"]),
            "direct_anchor_frames": point["retrospective_association"]["direct_anchor_frames"],
            "source_motion_prediction_error_px": point["retrospective_association"]["source_motion_prediction_error_px"],
            "labels": ["DIRECT_SOURCE_OBSERVATION", "OFFLINE_RETROSPECTIVE_IDENTITY_LINK", "PROVISIONAL", "NOT_GROUND_TRUTH"],
        })
    return accepted


def _intervals(
    frames: list[int], frame_count: int,
    inferred_gaps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return observed visibility plus only explicitly evidence-backed inferred gaps."""
    if not frames:
        return []
    frames = sorted(set(frames))
    inferred = {
        (int(span["start_frame"]), int(span["end_frame"])): span
        for span in (inferred_gaps or [])
    }
    spans: list[dict[str, Any]] = []
    start = previous = frames[0]
    for current in frames[1:]:
        if current == previous + 1:
            previous = current
            continue
        spans.append({"state": "visible", "start_frame": start, "end_frame": previous + 1})
        gap = (previous + 1, current)
        if gap in inferred:
            spans.append(inferred[gap])
        start = previous = current
    spans.append({"state": "visible", "start_frame": start, "end_frame": previous + 1})
    return [
        span for span in spans
        if 0 <= span["start_frame"] < span["end_frame"] <= frame_count
    ]


def _unobserved_intervals(
    frames: list[int], frame_count: int,
    inferred_gaps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Record interior gaps without claiming that the note was occluded or present."""
    observed = sorted(set(frame for frame in frames if 0 <= frame < frame_count))
    inferred = {
        (int(span["start_frame"]), int(span["end_frame"]))
        for span in (inferred_gaps or [])
    }
    return [
        {
            "state": "UNOBSERVED",
            "start_frame": previous + 1,
            "end_frame": current,
            "labels": ["NO_DIRECT_NOTE_OBSERVATION", "NOT_OCCLUSION_EVIDENCE"],
        }
        for previous, current in zip(observed, observed[1:])
        if current > previous + 1 and (previous + 1, current) not in inferred
    ]


def _retrospective_partial_gaps(
    keyframe_points: list[dict[str, Any]], points: list[dict[str, Any]],
    kind: str, tracker_id: str, tracker_confirmed: bool, lane_pixels: float,
) -> list[dict[str, Any]]:
    """Infer short gaps only when one confirmed track has repeated aligned fragments.

    Direct same-kind heads must bracket a 5-18 frame gap. At least 65% of gap
    frames (minimum three) need same-color, path-aligned partial observations,
    with no run of missing fragment observations longer than three frames.
    Duration alone is never enough to infer occlusion.
    """
    if not tracker_confirmed or kind not in ("tap", "hold"):
        return []
    direct_kind = "tap" if kind == "tap" else "hold_head"
    anchors = sorted(
        (point for point in keyframe_points if point["candidate_kind"] == direct_kind),
        key=lambda point: point["frame"],
    )
    if len(anchors) < 2:
        return []
    result: list[dict[str, Any]] = []
    for left, right in zip(anchors, anchors[1:]):
        gap_start, gap_end = int(left["frame"]) + 1, int(right["frame"])
        gap_length = gap_end - gap_start
        if not 5 <= gap_length <= 18 or left["candidate_color"] != right["candidate_color"]:
            continue
        direct_heights = [
            float(point["detector_rectified_bbox"][3])
            for point in (left, right)
            if float(point["detector_rectified_bbox"][3]) > 0
        ]
        if not direct_heights:
            continue
        partial_height_limit = max(8.0, min(direct_heights) * 0.65)
        x_tolerance = max(24.0, lane_pixels * 0.75)
        y_tolerance = max(18.0, lane_pixels * 0.5)
        aligned: list[dict[str, Any]] = []
        for point in points:
            frame = int(point["frame"])
            if not gap_start <= frame < gap_end:
                continue
            if point["candidate_kind"] == direct_kind or point["candidate_color"] != left["candidate_color"]:
                continue
            bbox = point.get("detector_rectified_bbox", [0, 0, 0, 0])
            if float(bbox[3]) <= 0 or float(bbox[3]) > partial_height_limit:
                continue
            if float(point["candidate_score_uncalibrated"]) < 0.65:
                continue
            if kind == "hold":
                component_owners = point.get("component_head_owner_ids", [])
                if any(owner != tracker_id for owner in component_owners):
                    continue
            t = (frame - left["frame"]) / (right["frame"] - left["frame"])
            expected_x = float(left["rectified_x"]) + t * (float(right["rectified_x"]) - float(left["rectified_x"]))
            expected_y = float(left["rectified_y"]) + t * (float(right["rectified_y"]) - float(left["rectified_y"]))
            if (abs(float(point["rectified_x"]) - expected_x) > x_tolerance
                    or abs(float(point["rectified_y"]) - expected_y) > y_tolerance):
                continue
            aligned.append(point)
        needed = max(3, math.ceil(gap_length * 0.65))
        frames = sorted({int(point["frame"]) for point in aligned})
        if len(frames) < needed:
            continue
        gaps_between = [b - a - 1 for a, b in zip(frames, frames[1:])]
        if gaps_between and max(gaps_between) > 3:
            continue
        result.append({
            "state": "occluded", "start_frame": gap_start, "end_frame": gap_end,
            "labels": ["INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"],
            "evidence": {
                "status": "PROVISIONAL / NOT_GROUND_TRUTH",
                "tracker_id": tracker_id,
                "tracker_confirmed": True,
                "direct_head_anchor_frames": [int(left["frame"]), int(right["frame"])],
                "aligned_partial_observation_frames": frames,
                "partial_observation_kinds": sorted({str(point["candidate_kind"]) for point in aligned}),
                "partial_observations": [
                    {
                        "frame": int(point["frame"]),
                        "kind": str(point["candidate_kind"]),
                        "color": str(point["candidate_color"]),
                        "rectified_xy_px": [
                            round(float(point["rectified_x"]), 2),
                            round(float(point["rectified_y"]), 2),
                        ],
                        "source_xy_px": [
                            round(float(point["head_x"]), 2),
                            round(float(point["head_y"]), 2),
                        ],
                        "source_bbox_px": [round(float(value), 2) for value in point["source_bbox"]],
                        "score_uncalibrated": round(float(point["candidate_score_uncalibrated"]), 4),
                        "connected_component_head_owner_ids": point.get("component_head_owner_ids", []),
                        "labels": ["DIRECT_PARTIAL_OBSERVATION", "NOT_GROUND_TRUTH"],
                    }
                    for point in aligned
                ],
                "same_color_as_both_bracketing_heads": left["candidate_color"],
                "alignment_tolerance_rectified_px": [round(x_tolerance, 2), round(y_tolerance, 2)],
                "rule": "Repeated same-track, same-color partial observations follow the path between direct same-kind heads; gap duration alone is insufficient.",
            },
        })
    return result


def _retrospective_native_cyan_effect_gaps(
    video: Path, keyframe_points: list[dict[str, Any]], points: list[dict[str, Any]],
    kind: str, tracker_id: str, histories: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mark very short cyan Tap gaps only when a linked full face brackets them.

    This rule is deliberately narrower than duration-based interpolation: one
    endpoint must be a directly measured native cyan face linked to the track,
    the other endpoint must be a direct same-color head within eight frames,
    no competing confirmed same-lane Tap may span the gap, and the predicted
    source box must still contain cyan face pixels beneath a strong bright
    effect in every missing frame. The resulting frames stay explicitly
    INFERRED_OCCLUSION / OFFLINE_RETROSPECTIVE and are rendered as dashed heads.
    """
    if kind != "tap" or not any(point.get("retrospective_association") for point in keyframe_points):
        return []
    anchors = sorted(
        (point for point in keyframe_points if point.get("candidate_kind") == "tap"),
        key=lambda point: int(point["frame"]),
    )
    if len(anchors) < 2:
        return []
    direct_points = [
        point for point in points
        if point.get("candidate_kind") == "tap"
        and point.get("candidate_color") == anchors[0].get("candidate_color")
    ]
    direct_frames = {int(point["frame"]) for point in direct_points}
    result: list[dict[str, Any]] = []
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return []
    try:
        for left, right in zip(anchors, anchors[1:]):
            a, b = int(left["frame"]), int(right["frame"])
            gap_start, gap_end = a + 1, b
            gap_length = gap_end - gap_start
            if not 1 <= gap_length <= 4 or b - a > 8:
                continue
            if left.get("candidate_color") != right.get("candidate_color"):
                continue
            if not (left.get("retrospective_association") or right.get("retrospective_association")):
                continue
            if any(frame in direct_frames for frame in range(gap_start, gap_end)):
                continue
            lane = int(float(left["rectified_x"]) // 100)
            competing = False
            for other_id, rec in histories.items():
                if other_id == tracker_id or not rec.get("confirmed_seen"):
                    continue
                other = [
                    point for point in rec["points"]
                    if point.get("candidate_kind") == "tap"
                    and point.get("candidate_color") == left.get("candidate_color")
                    and int(float(point["rectified_x"]) // 100) == lane
                ]
                if any(gap_start <= int(point["frame"]) < gap_end for point in other):
                    competing = True
                    break
            if competing:
                continue

            per_frame: list[dict[str, Any]] = []
            enough_effect_evidence = True
            left_box = list(map(float, left["source_bbox"]))
            right_box = list(map(float, right["source_bbox"]))
            for frame in range(gap_start, gap_end):
                t = (frame - a) / (b - a)
                box = [left_box[i] + t * (right_box[i] - left_box[i]) for i in range(4)]
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
                ok, image = cap.read()
                if not ok:
                    enough_effect_evidence = False
                    break
                height, width = image.shape[:2]
                x0 = max(0, min(width, int(math.floor(box[0]))))
                y0 = max(0, min(height, int(math.floor(box[1]))))
                x1 = max(x0, min(width, int(math.ceil(box[0] + box[2]))))
                y1 = max(y0, min(height, int(math.ceil(box[1] + box[3]))))
                if x1 <= x0 or y1 <= y0:
                    enough_effect_evidence = False
                    break
                hsv = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
                cyan = cv2.inRange(hsv, np.array((84, 65, 110)), np.array((112, 255, 255))) > 0
                bright = hsv[:, :, 2] > 220
                low_saturation_bright = bright & (hsv[:, :, 1] < 120)
                cyan_fraction = float(np.mean(cyan))
                bright_fraction = float(np.mean(bright))
                white_flash_fraction = float(np.mean(low_saturation_bright))
                per_frame.append({
                    "frame": frame,
                    "source_bbox_interpolated_px_not_direct_measurement": [round(value, 2) for value in box],
                    "cyan_pixel_fraction": round(cyan_fraction, 4),
                    "bright_pixel_fraction": round(bright_fraction, 4),
                    "bright_low_saturation_fraction": round(white_flash_fraction, 4),
                })
                if cyan_fraction < 0.20 or bright_fraction < 0.65 or white_flash_fraction < 0.15:
                    enough_effect_evidence = False
            if not enough_effect_evidence or len(per_frame) != gap_length:
                continue
            result.append({
                "state": "occluded", "start_frame": gap_start, "end_frame": gap_end,
                "labels": ["INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"],
                "evidence": {
                    "status": "AUTO_VISUAL_REVIEWED / PROVISIONAL / NOT_GROUND_TRUTH",
                    "tracker_id": tracker_id,
                    "direct_head_anchor_frames": [a, b],
                    "native_face_identity_link_frame": (
                        a if left.get("retrospective_association") else b
                    ),
                    "per_frame_source_effect_metrics": per_frame,
                    "criteria": {
                        "maximum_gap_frames": 4,
                        "maximum_anchor_span_frames": 8,
                        "minimum_cyan_pixel_fraction": 0.20,
                        "minimum_bright_pixel_fraction": 0.65,
                        "minimum_bright_low_saturation_fraction": 0.15,
                        "competing_confirmed_same_lane_taps": 0,
                    },
                    "path_rule": "Interpolate only between direct same-track source heads within this clip; this is a short occlusion hypothesis, not a velocity model or a direct measurement.",
                },
            })
    finally:
        cap.release()
    return result


def _associate_external_partial_tap_tracks(
    histories: dict[str, dict[str, Any]], lane_pixels: float,
) -> dict[str, list[dict[str, Any]]]:
    """Bridge a confirmed Tap tracker gap to one unique aligned fragment tracker.

    This is deliberately Tap-only. It keeps the directly observed bottom path
    between same-color Tap anchors, checks fragment-center x against that path,
    and fits a linear vertical offset from the anchor-derived top edge. The
    partial detector box is never treated as a full head box or ground truth.
    Ambiguous many-to-one or one-to-many matches are rejected.
    """
    candidates: list[dict[str, Any]] = []
    for target_id, target in histories.items():
        if not target["confirmed_seen"]:
            continue
        anchors = sorted(
            (point for point in target["points"] if point["candidate_kind"] == "tap"),
            key=lambda point: point["frame"],
        )
        if len(anchors) < 2:
            continue
        for left, right in zip(anchors, anchors[1:]):
            start, end = int(left["frame"]) + 1, int(right["frame"])
            gap_length = end - start
            if not 5 <= gap_length <= 18 or left["candidate_color"] != right["candidate_color"]:
                continue
            left_box, right_box = left["source_bbox"], right["source_bbox"]
            min_height = min(float(left_box[3]), float(right_box[3]))
            partial_height_limit = max(8.0, min_height * 0.65)
            x_tolerance = max(32.0, lane_pixels * 0.32)
            partial_tracks: list[dict[str, Any]] = []
            for fragment_id, fragment in histories.items():
                if fragment_id == target_id or not fragment["confirmed_seen"]:
                    continue
                fragment_points = [
                    point for point in fragment["points"]
                    if start <= int(point["frame"]) < end
                    and point["candidate_kind"] == "plate_fragment"
                    and point["candidate_color"] == left["candidate_color"]
                    and float(point["candidate_score_uncalibrated"]) >= 0.65
                    and 0 < float(point["source_bbox"][3]) <= partial_height_limit
                ]
                # Require a fragment-only tracker with enough time coverage.
                if not fragment_points:
                    continue
                all_kinds = {point["candidate_kind"] for point in fragment["points"]}
                if all_kinds != {"plate_fragment"}:
                    continue
                expected_frames = max(3, math.ceil(gap_length * 0.65))
                observed_frames = sorted({int(point["frame"]) for point in fragment_points})
                if len(observed_frames) < expected_frames:
                    continue
                if max((b - a - 1 for a, b in zip(observed_frames, observed_frames[1:])), default=0) > 3:
                    continue
                residuals: list[tuple[float, float, float, dict[str, Any]]] = []
                for point in fragment_points:
                    frame = int(point["frame"])
                    t = (frame - int(left["frame"])) / (int(right["frame"]) - int(left["frame"]))
                    expected_x = float(left["head_x"]) + t * (float(right["head_x"]) - float(left["head_x"]))
                    expected_y = float(left["head_y"]) + t * (float(right["head_y"]) - float(left["head_y"]))
                    expected_height = float(left_box[3]) + t * (float(right_box[3]) - float(left_box[3]))
                    box = point["source_bbox"]
                    observed_x = float(box[0]) + float(box[2]) / 2
                    dx = observed_x - expected_x
                    if abs(dx) > x_tolerance:
                        continue
                    # A top-edge fragment can remain aligned while the note
                    # height changes. Fit only a smooth linear offset; reject
                    # irregular vertical jumps that suggest a different object.
                    expected_top = expected_y - expected_height
                    residuals.append((t, expected_top - float(box[1]), dx, point))
                if len(residuals) < expected_frames:
                    continue
                mean_t = sum(row[0] for row in residuals) / len(residuals)
                mean_r = sum(row[1] for row in residuals) / len(residuals)
                denom = sum((row[0] - mean_t) ** 2 for row in residuals)
                slope = (sum((row[0] - mean_t) * (row[1] - mean_r) for row in residuals) / denom) if denom else 0.0
                intercept = mean_r - slope * mean_t
                fit_errors = [abs(residual - (intercept + slope * t)) for t, residual, _, _ in residuals]
                y_fit_tolerance = max(12.0, lane_pixels * 0.12)
                if max(fit_errors, default=float("inf")) > y_fit_tolerance:
                    continue
                gap_frame_span = max(1, int(right["frame"]) - int(left["frame"]))
                if abs(slope) / gap_frame_span > max(3.0, lane_pixels * 0.03):
                    continue
                partial_tracks.append({
                    "fragment_id": fragment_id,
                    "points": [row[3] for row in residuals],
                    "residuals": residuals,
                    "x_tolerance": x_tolerance,
                    "y_fit_tolerance": y_fit_tolerance,
                    "vertical_offset_fit": {"intercept_px": intercept, "slope_px_per_normalized_gap": slope, "max_abs_error_px": max(fit_errors)},
                    "observed_frames": sorted({int(row[3]["frame"]) for row in residuals}),
                })
            if len(partial_tracks) == 1:
                candidates.append({
                    "target_id": target_id, "start": start, "end": end,
                    "left": left, "right": right, "fragment": partial_tracks[0],
                })

    # A confirmed fragment tracker may bridge only one target gap. Also reject
    # gaps where multiple candidate fragment tracks independently matched.
    fragment_use: dict[str, int] = {}
    for item in candidates:
        fragment_id = item["fragment"]["fragment_id"]
        fragment_use[fragment_id] = fragment_use.get(fragment_id, 0) + 1
    associated: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        fragment = item["fragment"]
        if fragment_use[fragment["fragment_id"]] != 1:
            continue
        left, right = item["left"], item["right"]
        bridge_points = []
        for point in fragment["points"]:
            frame = int(point["frame"])
            t = (frame - int(left["frame"])) / (int(right["frame"]) - int(left["frame"]))
            expected_bottom = float(left["head_y"]) + t * (float(right["head_y"]) - float(left["head_y"]))
            expected_center_x = float(left["head_x"]) + t * (float(right["head_x"]) - float(left["head_x"]))
            left_width, right_width = float(left["source_bbox"][2]), float(right["source_bbox"][2])
            expected_width = left_width + t * (right_width - left_width)
            box = point["source_bbox"]
            _, top, _, _ = map(float, box)
            head_height = expected_bottom - top
            if head_height <= float(box[3]) or head_height > max(100.0, lane_pixels):
                continue
            bridged = dict(point)
            bridged.update({
                "candidate_kind": "tap",
                # Partial boxes can be horizontally clipped. Use this note's
                # own bracketed head path for center and width; retain the raw
                # partial box only as source evidence and association input.
                "head_x": expected_center_x,
                "head_y": expected_bottom,
                "source_bbox": [expected_center_x - expected_width / 2, top, expected_width, head_height],
                "scene_source_observation_kind": "OFFLINE_RETROSPECTIVE_ASSOCIATED_PARTIAL_HEAD_EDGE",
                "partial_fragment_bbox": [round(float(value), 2) for value in box],
                "partial_fragment_tracker_id": fragment["fragment_id"],
                "partial_head_measurement_labels": ["SOURCE_PARTIAL_OBSERVATION", "OFFLINE_RETROSPECTIVE", "NOT_GROUND_TRUTH"],
            })
            bridge_points.append(bridged)
        if len(bridge_points) < max(3, math.ceil((item["end"] - item["start"]) * 0.65)):
            continue
        item["bridge_points"] = bridge_points
        item["evidence"] = {
            "status": "OFFLINE_RETROSPECTIVE_PARTIAL_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH",
            "target_tracker_id": item["target_id"],
            "fragment_tracker_id": fragment["fragment_id"],
            "direct_head_anchor_frames": [int(left["frame"]), int(right["frame"])],
            "partial_observation_frames": [int(point["frame"]) for point in bridge_points],
            "partial_observations": [
                {
                    "frame": int(point["frame"]),
                    "candidate_kind": "plate_fragment",
                    "color": str(point["candidate_color"]),
                    "source_bbox_px": [round(float(value), 2) for value in point["partial_fragment_bbox"]],
                    "score_uncalibrated": round(float(point["candidate_score_uncalibrated"]), 4),
                    "head_bottom_path_px": [round(float(point["head_x"]), 2), round(float(point["head_y"]), 2)],
                    "labels": ["SOURCE_PARTIAL_OBSERVATION", "NOT_GROUND_TRUTH"],
                }
                for point in bridge_points
            ],
            "horizontal_tolerance_px": round(float(fragment["x_tolerance"]), 2),
            "vertical_offset_fit": fragment["vertical_offset_fit"],
            "rule": "One confirmed same-color fragment-only tracker follows the interpolated path between direct Tap anchors; x alignment and a smooth fitted vertical top-edge offset are required; ambiguous links are rejected.",
        }
        associated.setdefault(item["target_id"], []).append(item)
    return associated


def _bbox_iou(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    ax, ay, aw, ah = map(float, a)
    bx, by, bw, bh = map(float, b)
    intersection = max(0.0, min(ax + aw, bx + bw) - max(ax, bx)) * max(
        0.0, min(ay + ah, by + bh) - max(ay, by)
    )
    union = max(0.0, aw * ah) + max(0.0, bw * bh) - intersection
    return intersection / union if union > 0 else 0.0


def _attach_retrospective_recovery_taps(
    recovery_points: list[dict[str, Any]],
    histories: dict[str, dict[str, Any]],
    max_rectified_bbox_width: float = 200.0,
    judgment_line_y: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Attach repeated recovery-only Tap faces to a unique nearby normal Tap anchor.

    This is a narrowly bounded offline association. It does not create a note
    without a tracker-attached endpoint and preserves the raw face detections.
    A recovery box spanning over two rectified lanes remains a line/effect or
    multi-object candidate; it is retained for review but cannot claim one Tap.
    A nearly stationary cluster whose boxes straddle the per-run judgment line
    is also retained for review but not attached: it may be the judgment band
    or its effect. This conservative gate suppresses only the retrospective
    association; it does not delete the detector evidence or direct tracks.
    """
    ordered = sorted(recovery_points, key=lambda p: (p["frame"], p["rectified_x"]))
    adjacent: dict[int, list[int]] = {}
    incoming: dict[int, list[int]] = {}
    for i, point in enumerate(ordered):
        for j, candidate in enumerate(ordered):
            if (candidate["frame"] != point["frame"] + 1
                    or candidate["candidate_color"] != point["candidate_color"]
                    or abs(candidate["rectified_x"] - point["rectified_x"]) > 24
                    or abs(candidate["rectified_y"] - point["rectified_y"]) > 18
                    or _bbox_iou(candidate["detector_rectified_bbox"], point["detector_rectified_bbox"]) < 0.5):
                continue
            adjacent.setdefault(i, []).append(j)
            incoming.setdefault(j, []).append(i)
    # Accept only mutual one-to-one links. Forks and merges remain unresolved.
    ambiguous: set[int] = set()
    for i, options in adjacent.items():
        if len(options) > 1:
            ambiguous.add(i)
            ambiguous.update(options)
    for j, options in incoming.items():
        if len(options) > 1:
            ambiguous.add(j)
            ambiguous.update(options)
    successor = {
        i: options[0] for i, options in adjacent.items()
        if i not in ambiguous and options[0] not in ambiguous
        and len(options) == 1 and len(incoming.get(options[0], ())) == 1
    }
    predecessor = {j: i for i, j in successor.items()}
    groups: list[list[dict[str, Any]]] = []
    visited: set[int] = set()
    for i in range(len(ordered)):
        if i in visited or i in predecessor or i in ambiguous:
            continue
        indices = [i]
        visited.add(i)
        while indices[-1] in successor:
            nxt = successor[indices[-1]]
            if nxt in visited:
                break
            indices.append(nxt)
            visited.add(nxt)
        groups.append([ordered[index] for index in indices])
    groups.extend([[ordered[i]] for i in range(len(ordered)) if i not in visited and i not in ambiguous])

    diagnostics: list[dict[str, Any]] = []
    for index in sorted(ambiguous):
        point = ordered[index]
        diagnostics.append({
            "status": "REJECTED / NOT_GROUND_TRUTH",
            "reason": "ambiguous_same_color_recovery_adjacency_fork_or_merge",
            "observation_indices": [point.get("observation_index")],
            "frames": [point["frame"]], "color": point["candidate_color"],
            "rectified_bbox": point["detector_rectified_bbox"],
            "score_uncalibrated": point["candidate_score_uncalibrated"],
            "plausible_successor_frames": [ordered[j]["frame"] for j in adjacent.get(index, ())],
            "plausible_predecessor_frames": [ordered[j]["frame"] for j in incoming.get(index, ())],
        })

    proposals: list[tuple[list[dict[str, Any]], str, dict[str, Any], dict[str, Any]]] = []
    for group in groups:
        diagnostic: dict[str, Any] = {
            "status": "REJECTED / NOT_GROUND_TRUTH",
            "reason": None,
            "observation_indices": [point.get("observation_index") for point in group],
            "frames": [point["frame"] for point in group],
            "color": group[0]["candidate_color"],
            "observations": [{
                "frame": point["frame"], "rectified_bbox": point["detector_rectified_bbox"],
                "score_uncalibrated": point["candidate_score_uncalibrated"],
            } for point in group],
            "tracker_owners_by_observation": [],
            "endpoint_candidates": [],
            "competing_tracker_observations": [],
        }
        diagnostics.append(diagnostic)
        wide_observations = [
            point for point in group
            if len(point.get("detector_rectified_bbox", ())) == 4
            and point["detector_rectified_bbox"][2] > max_rectified_bbox_width
        ]
        if wide_observations:
            diagnostic["reason"] = "recovery_bbox_exceeds_two_rectified_lanes"
            diagnostic["max_rectified_bbox_width_px"] = max_rectified_bbox_width
            diagnostic["rejected_bbox_widths_px"] = [
                point["detector_rectified_bbox"][2] for point in wide_observations
            ]
            continue
        if len(group) < 2:
            diagnostic["reason"] = "fewer_than_two_consecutive_recovery_observations"
            continue
        if judgment_line_y is not None:
            boxes = [point.get("detector_rectified_bbox", []) for point in group]
            valid_boxes = [box for box in boxes if len(box) == 4]
            stationary_judgment_band = (
                len(valid_boxes) == len(group)
                and all(
                    float(box[1]) <= float(judgment_line_y) + 4.0
                    and float(box[1]) + float(box[3]) >= float(judgment_line_y) - 20.0
                    for box in valid_boxes
                )
                and max(float(box[1]) for box in valid_boxes)
                    - min(float(box[1]) for box in valid_boxes) <= 3.0
                and max(float(box[1]) + float(box[3]) for box in valid_boxes)
                    - min(float(box[1]) + float(box[3]) for box in valid_boxes) <= 3.0
            )
            if stationary_judgment_band:
                diagnostic["reason"] = "stationary_recovery_cluster_overlaps_judgment_band"
                diagnostic["judgment_line_y"] = float(judgment_line_y)
                diagnostic["labels"] = [
                    "JUDGMENT_BAND_AMBIGUITY",
                    "RETAINED_SOURCE_OBSERVATION_NOT_ASSOCIATED",
                    "PROVISIONAL",
                    "NOT_GROUND_TRUTH",
                ]
                continue
        # A recovery face already recorded by the Tracker must not be added twice.
        represented_owners: list[set[str]] = []
        for point in group:
            owners = {
                track_id for track_id, rec in histories.items()
                for observed in rec["points"]
                if observed["frame"] == point["frame"]
                and observed.get("candidate_kind") == "tap"
                and observed.get("candidate_color") == point["candidate_color"]
                and _bbox_iou(observed.get("detector_rectified_bbox", []), point["detector_rectified_bbox"]) >= 0.5
            }
            represented_owners.append(owners)
        diagnostic["tracker_owners_by_observation"] = [sorted(owners) for owners in represented_owners]
        if any(len(owners) > 1 for owners in represented_owners):
            diagnostic["reason"] = "recovery_observation_overlaps_multiple_tracker_tracks"
            continue
        unrecorded = [point for point, owners in zip(group, represented_owners) if not owners]
        represented_tracks = set().union(*represented_owners) if represented_owners else set()
        if (len(unrecorded) < 2 or any(
                right["frame"] != left["frame"] + 1
                for left, right in zip(unrecorded, unrecorded[1:]))):
            diagnostic["reason"] = "fewer_than_two_unrecorded_consecutive_recovery_observations"
            diagnostic["represented_tracks"] = sorted(represented_tracks)
            continue
        endpoints: list[tuple[int, str, dict[str, Any]]] = []

        def is_confirmed_tap_track(rec: dict[str, Any]) -> bool:
            track_kinds = [kind for kind in rec["kind_history"] if kind in ("tap", "hold")]
            return bool(track_kinds) and track_kinds.count("tap") > track_kinds.count("hold") and rec["confirmed_seen"]

        # A tracker-attached recovery face can anchor a preceding unassigned
        # sequence; the endpoint need not have passed the causal detector's
        # recovery flag if Tracker did attach it to a confirmed Tap track.
        for point, owners in zip(group, represented_owners):
            if point["frame"] <= unrecorded[-1]["frame"] or len(owners) != 1:
                continue
            track_id = next(iter(owners))
            rec = histories[track_id]
            gap = point["frame"] - unrecorded[-1]["frame"]
            if (gap <= 2 and is_confirmed_tap_track(rec)
                    and point["candidate_color"] == unrecorded[-1]["candidate_color"]):
                endpoints.append((gap, track_id, point))
        for track_id, rec in histories.items():
            if not is_confirmed_tap_track(rec):
                continue
            for anchor in rec["points"]:
                gap = anchor["frame"] - group[-1]["frame"]
                if (1 <= gap <= 2 and anchor.get("candidate_kind") == "tap"
                        and anchor.get("candidate_color") == unrecorded[-1]["candidate_color"]
                        and _bbox_iou(anchor["detector_rectified_bbox"], unrecorded[-1]["detector_rectified_bbox"]) >= 0.5):
                    endpoints.append((gap, track_id, anchor))
        diagnostic["represented_tracks"] = sorted(represented_tracks)
        diagnostic["endpoint_candidates"] = [{
            "gap_frames": gap, "track_id": track_id, "frame": anchor["frame"],
            "color": anchor.get("candidate_color"), "kind": anchor.get("candidate_kind"),
            "recovery_only": bool(anchor.get("recovery_only", False)),
            "tracker_confirmed": bool(histories[track_id]["confirmed_seen"]),
            "tracker_kind_counts": {
                value: histories[track_id]["kind_history"].count(value)
                for value in ("tap", "hold", "pending")
            },
            "rectified_bbox": anchor.get("detector_rectified_bbox"),
            "bbox_iou": round(_bbox_iou(anchor["detector_rectified_bbox"], unrecorded[-1]["detector_rectified_bbox"]), 4),
        } for gap, track_id, anchor in endpoints]
        if endpoints:
            closest_gap = min(gap for gap, _, _ in endpoints)
            closest = [(track_id, anchor) for gap, track_id, anchor in endpoints if gap == closest_gap]
            if (len(closest) == 1
                    and (not represented_tracks or represented_tracks == {closest[0][0]})):
                diagnostic["selected_endpoint_track_id"] = closest[0][0]
                diagnostic["selected_endpoint_frame"] = closest[0][1]["frame"]
                proposals.append((unrecorded, closest[0][0], closest[0][1], diagnostic))
            elif len(closest) != 1:
                diagnostic["reason"] = "multiple_equally_close_tracker_endpoints"
            else:
                diagnostic["reason"] = "represented_observations_belong_to_different_tracker_track"
        else:
            diagnostic["reason"] = "no_same_color_confirmed_tap_endpoint_within_two_frames_and_iou_gate"

    # Enforce one-to-one ownership between a recovery sequence and a tracker anchor.
    ownership: dict[tuple[str, int], int] = {}
    for _, track_id, anchor, _ in proposals:
        key = (track_id, anchor["frame"])
        ownership[key] = ownership.get(key, 0) + 1
    links: list[dict[str, Any]] = []
    for group, track_id, anchor, diagnostic in proposals:
        if ownership[(track_id, anchor["frame"])] != 1:
            diagnostic["reason"] = "multiple_recovery_groups_claim_same_tracker_endpoint"
            continue
        rec = histories[track_id]
        competing = any(
            other_id != track_id
            and observed["frame"] in {point["frame"] for point in group}
            and _bbox_iou(observed.get("detector_rectified_bbox", []), point["detector_rectified_bbox"]) >= 0.5
            for other_id, other_rec in histories.items() for observed in other_rec["points"]
            for point in group
        )
        diagnostic["competing_tracker_observations"] = [{
            "track_id": other_id, "frame": observed["frame"],
            "kind": observed.get("candidate_kind"), "color": observed.get("candidate_color"),
            "rectified_bbox": observed.get("detector_rectified_bbox"),
        } for other_id, other_rec in histories.items() if other_id != track_id
          for observed in other_rec["points"] for point in group
          if observed["frame"] == point["frame"]
          and _bbox_iou(observed.get("detector_rectified_bbox", []), point["detector_rectified_bbox"]) >= 0.5]
        duplicate = any(
                point["frame"] == added["frame"] and point.get("candidate_kind") == "tap"
                for point in rec["points"] for added in group)
        if competing or duplicate:
            diagnostic["reason"] = "overlapping_competing_track_or_duplicate_same_frame_tap"
            continue
        for point in group:
            associated = dict(point)
            associated["retrospective_association"] = {
                "status": "OFFLINE_RETROSPECTIVE_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH",
                "anchor_track_id": track_id,
                "anchor_frame": anchor["frame"],
                "basis": "consecutive source-detected recovery-only Tap faces with matching color, bounded motion, and high-overlap unique tracker-attached Tap endpoint",
            }
            rec["points"].append(associated)
            rec["kind_history"].append("tap")
            rec["color_history"].append(point["candidate_color"])
            links.append({"track_id": track_id, "frame": point["frame"], "color": point["candidate_color"], "bbox": point["detector_rectified_bbox"]})
        rec["points"].sort(key=lambda p: p["frame"])
        diagnostic["status"] = "ACCEPTED / OFFLINE_RETROSPECTIVE_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH"
        diagnostic["reason"] = "unique_confirmed_tap_endpoint_and_no_spatial_competitor"
    return links, diagnostics


def _stationary_hold_candidate(rec: dict[str, Any], geometry: RunGeometry) -> dict[str, Any] | None:
    """Recognize a narrow, repeated green Hold-head pattern for offline review.

    This bypasses causal Tracker confirmation only when source-observed points
    repeatedly carry a green hold_head classification and a substantial upward
    ribbon. It does not synthesize head samples or extend the observed interval.
    """
    points = rec["points"]
    hold_heads = [point for point in points if point["candidate_kind"] == "hold_head"]
    ribbon_heads = [
        point for point in hold_heads
        if point["candidate_color"] == "green" and point["upper_ribbon_px"] >= 36
    ]
    if len(hold_heads) < 8 or len(ribbon_heads) < 8:
        return None
    observed_span = hold_heads[-1]["frame"] - hold_heads[0]["frame"]
    if observed_span < 12:
        return None
    anchored_heads = [
        point for point in hold_heads
        if point.get("component_head_rectified_x") is not None
        or point.get("cut_component_candidate") is not None
    ]
    if len(anchored_heads) < 4 or len(anchored_heads) / len(hold_heads) < 0.3:
        return None
    lane_counts: dict[int, int] = {}
    for point in anchored_heads:
        anchor_x = point.get("component_head_rectified_x")
        if anchor_x is None:
            anchor_x = point["rectified_x"]
        lane = min(5, max(0, int(anchor_x // geometry.lane_pixels)))
        lane_counts[lane] = lane_counts.get(lane, 0) + 1
    primary_lane = max(lane_counts, key=lambda lane: (lane_counts[lane], -lane))
    if (lane_counts[primary_lane] / len(anchored_heads) <= 0.5
            or max(lane_counts) - min(lane_counts) > 1):
        return None
    x_values = [
        point["component_head_rectified_x"]
        if point.get("component_head_rectified_x") is not None
        else point["rectified_x"]
        for point in anchored_heads
    ]
    center_drift = max(x_values) - min(x_values)
    if center_drift > geometry.lane_pixels * 0.8:
        return None
    y_values = [point["rectified_y"] for point in hold_heads]
    head_y_spread = max(y_values) - min(y_values)
    if head_y_spread > 48:
        return None
    return {
        "labels": ["OFFLINE_RETROSPECTIVE_STATIONARY_HOLD_CANDIDATE", "PROVISIONAL", "NOT_GROUND_TRUTH"],
        "observed_hold_head_frames": len(hold_heads),
        "observed_uniquely_owned_component_anchor_frames": len(anchored_heads),
        "observed_unowned_cut_component_anchor_frames": sum(
            point.get("cut_component_candidate") is not None for point in anchored_heads
        ),
        "observed_green_hold_head_ribbon_frames": len(ribbon_heads),
        "observed_frame_span": observed_span,
        "observed_lane": primary_lane,
        "observed_primary_lane_fraction": round(lane_counts[primary_lane] / len(anchored_heads), 3),
        "observed_head_center_drift_px": round(center_drift, 2),
        "observed_head_y_spread_px": round(head_y_spread, 2),
        "minimum_upper_ribbon_px": min(point["upper_ribbon_px"] for point in ribbon_heads),
    }


def reconstruct(source: Path, geometry_path: Path, output_json: Path, max_frames: int | None = None, index_path: Path | None = None) -> dict[str, Any]:
    video = source if source.is_file() else source / "live_source.mp4"
    run_dir = video.parent
    default_index = run_dir / "live_video_index.csv"
    index = index_path if index_path is not None else (default_index if default_index.is_file() else None)
    geometry_doc = json.loads(geometry_path.read_text(encoding="utf-8"))
    geometry = RunGeometry(geometry_doc)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"cannot decode {video}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    if index is not None:
        with index.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if total_frames != len(rows):
            cap.release()
            raise ValueError(f"video/index mismatch: {total_frames} != {len(rows)}")
        for frame_no, row in enumerate(rows):
            if "video_frame" in row and int(row["video_frame"]) != frame_no:
                cap.release()
                raise ValueError(f"index video_frame order mismatch at {frame_no}")
    else:
        rows = [{"capture_timestamp": frame_no / fps} for frame_no in range(total_frames)]
    process_frames = total_frames if max_frames is None else min(total_frames, max_frames)
    perception = OfflinePerception(geometry)
    tracker = Tracker(geometry)
    histories: dict[str, dict[str, Any]] = {}
    recovery_tap_points: list[dict[str, Any]] = []
    native_cyan_observations: list[dict[str, Any]] = []
    for frame_no in range(process_frames):
        ok, image = cap.read()
        if not ok:
            cap.release()
            raise ValueError(f"decode failed at frame {frame_no}")
        timestamp = float(rows[frame_no]["capture_timestamp"])
        detections = perception.detect(image)
        for detection, source_bbox, lane in getattr(perception, "last_native_observations", []):
            sx, sy, sw, sh = map(float, source_bbox)
            rx, ry, rw, rh = map(float, detection.bbox)
            native_cyan_observations.append({
                "frame": frame_no,
                "capture_timestamp": timestamp,
                "rectified_x": rx + rw / 2,
                "rectified_y": ry + rh,
                "head_x": sx + sw / 2,
                "head_y": sy + sh,
                "source_bbox": [sx, sy, sw, sh],
                "detector_rectified_bbox": [rx, ry, rw, rh],
                "candidate_kind": "tap",
                "candidate_color": detection.color,
                "candidate_score_uncalibrated": float(detection.score),
                "lane": int(lane),
            })
        for detection in detections:
            if not (detection.kind == "tap" and detection.recovery_only):
                continue
            bx, by, bw, bh = map(float, detection.bbox)
            rect_x = bx + bw / 2
            rect_y = by + bh
            source_x = _native_x(geometry, rect_x, rect_y)
            source_left = _native_x(geometry, bx, rect_y)
            source_right = _native_x(geometry, bx + bw, rect_y)
            recovery_tap_points.append({
                "observation_index": len(recovery_tap_points),
                "frame": frame_no, "capture_timestamp": timestamp,
                "rectified_x": rect_x, "rectified_y": rect_y,
                "head_x": source_x, "head_y": rect_y,
                "source_bbox": [min(source_left, source_right), by, abs(source_right - source_left), bh],
                "detector_rectified_bbox": [bx, by, bw, bh],
                "candidate_kind": "tap", "candidate_color": detection.color,
                "candidate_score_uncalibrated": float(detection.score),
                "upper_ribbon_px": float(detection.above), "lower_ribbon_px": float(detection.below),
                "tail_x_estimate": source_x, "tail_y_estimate": rect_y,
                "tail_source": "recovery_only_direct_face_observation",
                "recovery_only": True,
            })
        notes = tracker.update(detections, timestamp, labels=perception.last_labels, path_mask=perception.last_path)
        component_extents = _component_extents(perception.last_path)
        cut_y = max(0, int(round(geometry.hit_y - 60)))
        cut_path = perception.last_path.copy() if perception.last_path is not None else None
        if cut_path is not None:
            cut_path[cut_y:, :] = 0
        cut_component_extents = _component_extents(cut_path)
        component_head_owners: dict[int, set[str]] = {}
        for candidate in notes:
            if (candidate.head and candidate.last_seen == timestamp and candidate.kind == "hold"
                    and candidate.detection.kind == "hold_head" and candidate.detection.component > 0):
                component_head_owners.setdefault(int(candidate.detection.component), set()).add(candidate.uid)
        cut_matches_by_track: dict[str, dict[str, Any]] = {}
        cut_options_by_track: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for candidate in notes:
            if (not candidate.head or candidate.last_seen != timestamp
                    or candidate.kind != "hold" or candidate.detection.kind != "hold_head"
                    or candidate.detection.color != "green"):
                continue
            sample = candidate.head[-1]
            if sample[0] != timestamp:
                continue
            rect_y = float(sample[1])
            if not cut_y - 32 <= rect_y <= geometry.hit_y + 40:
                continue
            bx, _, bw, _ = map(float, candidate.detection.bbox)
            cut_options_by_track[candidate.uid] = _cut_component_options(
                cut_component_extents, (bx, bw), rect_y, cut_y, geometry.lane_pixels,
            )
        for track_id, (cut_id, extent) in _unique_cut_matches(cut_options_by_track).items():
            cut_matches_by_track[track_id] = {
                "component_id": cut_id, "top_x": extent["top"][0],
                "top_y": extent["top"][1], "bbox": extent["bbox"],
                "bottom_x": extent["bottom"][0], "tracker_component_owner_count": 0,
                "candidate_detector_owner_count": 1,
                "association": "UNIQUE_GEOMETRIC_CUT_COMPONENT_MATCH / PROVISIONAL / NOT_GROUND_TRUTH",
            }
        for note in notes:
            if not note.head or note.last_seen != timestamp:
                continue
            sample = note.head[-1]
            if sample[0] != timestamp:
                continue
            rect_y = float(sample[1])
            rect_x = float((sample[2] + sample[3]) * geometry.plane_width / 2)
            source_x = _native_x(geometry, rect_x, rect_y)
            bx, by, bw, bh = map(float, note.detection.bbox)
            source_left = _native_x(geometry, bx, rect_y)
            source_right = _native_x(geometry, bx + bw, rect_y)
            upper_ribbon = float(note.detection.above)
            lower_ribbon = float(note.detection.below)
            tail_y = max(0.0, rect_y - upper_ribbon)
            tail_x = _native_x(geometry, rect_x, tail_y)
            tail_source = "local_ribbon_depth_candidate_capped_by_observer"
            component_id = int(note.detection.component)
            extent = component_extents.get(component_id)
            component_head_rectified_x = None
            component_head_x = component_head_y = component_head_width = None
            component_head_bbox = None
            component_tail_x = component_tail_y = None
            cut_component_candidate = cut_matches_by_track.get(note.uid)
            unowned_component_candidates = []
            for candidate_component_id, candidate_extent in component_extents.items():
                candidate_top_x, candidate_top_y = candidate_extent["top"]
                candidate_bottom_x, candidate_bottom_y = candidate_extent["bottom"]
                candidate_height = candidate_extent["bbox"][3]
                owner_count = len(component_head_owners.get(candidate_component_id, ()))
                if (owner_count == 0 and candidate_height >= 64
                        and candidate_top_y < candidate_bottom_y
                        and abs(candidate_bottom_y - rect_y) <= 32
                        and candidate_height >= max(upper_ribbon, lower_ribbon) + 8):
                    unowned_component_candidates.append({
                        "component_id": candidate_component_id,
                        "top_x": candidate_top_x, "top_y": candidate_top_y,
                        "bottom_x": candidate_bottom_x, "bottom_y": candidate_bottom_y,
                        "bbox": candidate_extent["bbox"],
                        "bottom_band_x_span": candidate_extent["bottom_band_x_span"],
                        "head_owner_count": owner_count,
                    })
            if (note.kind == "hold" and note.detection.kind == "hold_head" and extent
                    and len(component_head_owners.get(component_id, ())) == 1
                    and extent["bbox"][3] >= 64):
                top_x, top_y = extent["top"]
                bottom_x, bottom_y = extent["bottom"]
                endpoint_gap = bottom_y - top_y
                if (abs(bottom_y - rect_y) <= 32 and top_y < bottom_y
                        and endpoint_gap >= max(upper_ribbon, lower_ribbon) + 8):
                    component_head_rectified_x = bottom_x
                    component_head_x = _native_x(geometry, bottom_x, bottom_y)
                    component_head_y = bottom_y
                    band_left, band_right = extent["bottom_band_x_span"]
                    source_band_left = _native_x(geometry, band_left, bottom_y)
                    source_band_right = _native_x(geometry, band_right, bottom_y)
                    component_head_width = abs(source_band_right - source_band_left)
                    component_head_bbox = [
                        min(source_band_left, source_band_right), bottom_y,
                        component_head_width, bh,
                    ]
                    component_tail_x = _native_x(geometry, top_x, top_y)
                    component_tail_y = top_y
                    tail_x, tail_y = component_tail_x, component_tail_y
                    tail_source = "OBSERVED_COLOR_COMPONENT_UPPER_ENDPOINT_CANDIDATE / NOT_GROUND_TRUTH"
                else:
                    # Preserve the earlier endpoint fallback when the component
                    # cannot support a bounded lower-head anchor.
                    above_head_endpoints = [
                        endpoint for endpoint in ((top_x, top_y), (bottom_x, bottom_y))
                        if endpoint[1] < rect_y
                    ]
                    endpoint_x, endpoint_y = max(
                        above_head_endpoints,
                        key=lambda endpoint: abs(endpoint[1] - rect_y),
                        default=(None, None),
                    )
                    if (endpoint_y is not None
                            and abs(endpoint_y - rect_y) >= max(upper_ribbon, lower_ribbon) + 8):
                        tail_x = _native_x(geometry, endpoint_x, endpoint_y)
                        tail_y = endpoint_y
                        tail_source = "OBSERVED_COLOR_COMPONENT_ENDPOINT_CANDIDATE / NOT_GROUND_TRUTH"
            rec = histories.setdefault(note.uid, {
                "track_id": note.uid, "kind_history": [], "color_history": [],
                "points": [], "tail_points": [], "first_frame": frame_no,
                "last_frame": frame_no, "max_observations": 0,
                "confirmed_seen": False, "kind_locked_seen": False,
                "identity_states": [], "visibility_states": [],
            })
            if not rec["points"] or rec["points"][-1]["frame"] != frame_no:
                rec["points"].append({
                    "frame": frame_no, "capture_timestamp": timestamp,
                    "rectified_x": rect_x, "rectified_y": rect_y,
                    "head_x": source_x, "head_y": rect_y,
                    "component_head_rectified_x": component_head_rectified_x,
                    "component_head_x": component_head_x,
                    "component_head_y": component_head_y,
                    "component_head_width": component_head_width,
                    "component_head_bbox": component_head_bbox,
                    "component_tail_x": component_tail_x,
                    "component_tail_y": component_tail_y,
                    "source_bbox": [round(source_left, 2), round(by, 2), round(source_right - source_left, 2), round(bh, 2)],
                    "detector_rectified_bbox": [bx, by, bw, bh],
                    "candidate_kind": note.detection.kind,
                    "candidate_color": note.detection.color,
                    "candidate_score_uncalibrated": float(note.detection.score),
                    "recovery_only": bool(note.detection.recovery_only),
                    "upper_ribbon_px": upper_ribbon, "lower_ribbon_px": lower_ribbon,
                    "tail_x_estimate": tail_x, "tail_y_estimate": tail_y,
                    "tail_source": tail_source,
                    "component_id": component_id,
                    "component_head_owner_ids": sorted(component_head_owners.get(component_id, ())),
                    "component_bbox_observed": extent["bbox"] if extent else None,
                    "component_head_owner_count": len(component_head_owners.get(component_id, ())),
                    "unowned_component_candidates": unowned_component_candidates,
                    "cut_component_candidate": cut_component_candidate,
                })
            rec["last_frame"] = frame_no
            rec["max_observations"] = max(rec["max_observations"], int(note.observations))
            rec["confirmed_seen"] |= bool(note.confirmed)
            rec["kind_locked_seen"] |= bool(note.kind_locked)
            rec["kind_history"].append(note.kind)
            rec["color_history"].append(note.color)
            rec["identity_states"].append(note.identity_state)
            rec["visibility_states"].append(note.visibility_state)
            if note.tail and note.tail[-1][0] == timestamp:
                tail_sample = note.tail[-1]
                tail_rect_x = float((tail_sample[2] + tail_sample[3]) * geometry.plane_width / 2)
                tail_rect_y = float(tail_sample[1])
                rec["tail_points"].append({
                    "frame": frame_no, "capture_timestamp": timestamp,
                    "x": _native_x(geometry, tail_rect_x, tail_rect_y), "y": tail_rect_y,
                })
    cap.release()

    native_cyan_associations = _associate_native_cyan_tap_observations(
        native_cyan_observations, histories, geometry.lane_pixels,
    )
    retrospective_recovery_links, recovery_link_diagnostics = _attach_retrospective_recovery_taps(
        recovery_tap_points, histories,
        max_rectified_bbox_width=2 * geometry.lane_pixels,
        judgment_line_y=float(geometry_doc["judgment_line_y"]),
    )
    external_partial_bridges = _associate_external_partial_tap_tracks(
        histories, geometry.lane_pixels,
    )

    scene_notes: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for track_id, rec in sorted(histories.items()):
        points = rec["points"]
        kinds = [kind for kind in rec["kind_history"] if kind in ("tap", "hold")]
        if not points or not kinds:
            continue
        kind = max(set(kinds), key=kinds.count)
        keyframe_points = _retained_direct_head_points(points, kind)
        direct_keyframe_count = len(keyframe_points)
        partial_bridge_records = external_partial_bridges.get(track_id, []) if kind == "tap" else []
        for bridge in partial_bridge_records:
            keyframe_points.extend(bridge["bridge_points"])
        keyframe_points.sort(key=lambda point: point["frame"])
        stable = len(keyframe_points) >= 3 and rec["confirmed_seen"]
        offline_hold_evidence = (
            _stationary_hold_candidate(rec, geometry)
            if kind == "hold" and not stable else None
        )
        if offline_hold_evidence is not None:
            keyframe_points = [
                point for point in keyframe_points
                if point["candidate_kind"] == "hold_head"
                and point["candidate_color"] == "green"
                and point["upper_ribbon_px"] >= 36
                and point["tail_y_estimate"] < geometry_doc["judgment_line_y"]
            ]
            if (sum(
                    point["component_head_x"] is not None
                    or point.get("cut_component_candidate") is not None
                    for point in keyframe_points
                ) < 4
                    or len(keyframe_points) < 8):
                offline_hold_evidence = None
        if not stable and offline_hold_evidence is None:
            review_queue.append({
                "candidate_id": track_id, "candidate_kind": kind,
                "first_frame": rec["first_frame"], "last_frame": rec["last_frame"],
                "observations": len(points), "status": "UNRESOLVED_PROVISIONAL_CANDIDATE",
                "reason": "insufficient temporal confirmation from provisional detector/tracker",
                "observation_evidence": _observation_evidence_summary(
                    points, kind, rec["confirmed_seen"], rec["kind_locked_seen"],
                ),
            })
            continue
        keyframes = []
        for point in keyframe_points:
            use_component_anchor = (
                offline_hold_evidence is not None
                and point["component_head_x"] is not None
            )
            use_observed_detector_anchor = (
                offline_hold_evidence is not None and not use_component_anchor
            )
            unowned_component_match = None
            if use_observed_detector_anchor:
                unowned_component_match = _unique_lane_near_component(
                    point["unowned_component_candidates"], point["rectified_x"],
                    geometry.lane_pixels * 0.8,
                )
            if use_component_anchor:
                head_x = point["component_head_x"]
                head_y = point["component_head_y"]
                bbox = point["component_head_bbox"]
            elif use_observed_detector_anchor:
                # The repeated detector head remains direct source evidence when
                # an effect splits the long color component. Anchor its bottom
                # to this clip's estimated judgment line and label that estimate.
                head_y = float(geometry_doc["judgment_line_y"])
                head_x = _native_x(geometry, point["rectified_x"], head_y)
                rb_x, rb_y, rb_w, rb_h = point["detector_rectified_bbox"]
                bx0 = _native_x(geometry, rb_x, head_y)
                bx1 = _native_x(geometry, rb_x + rb_w, head_y)
                bbox = [min(bx0, bx1), head_y - rb_h, abs(bx1 - bx0), rb_h]
            else:
                head_x = point["head_x"]
                head_y = point["head_y"]
                bbox = point["source_bbox"]
            item = {
                "frame": point["frame"], "capture_timestamp": point["capture_timestamp"],
                "head_x": round(head_x, 2), "head_y": round(head_y, 2),
                "source_bbox": bbox,
                "head_width": bbox[2], "head_height": bbox[3],
                "source_observation_kind": point.get("scene_source_observation_kind", point["candidate_kind"]),
                "candidate_color_observed": point["candidate_color"],
                "candidate_score_uncalibrated": point["candidate_score_uncalibrated"],
            }
            if point.get("partial_head_measurement_labels"):
                item["partial_fragment_bbox"] = point["partial_fragment_bbox"]
                item["partial_fragment_tracker_id"] = point["partial_fragment_tracker_id"]
                item["head_measurement_labels"] = point["partial_head_measurement_labels"]
            if point.get("retrospective_association") is not None:
                item["association_evidence"] = point["retrospective_association"]
            if offline_hold_evidence is not None:
                item["head_source"] = (
                    "UNIQUELY_OWNED_COLOR_COMPONENT_LOWER_ENDPOINT_CANDIDATE / NOT_GROUND_TRUTH"
                    if use_component_anchor else (
                        "TRACKER_ASSOCIATED_DETECTOR_HEAD_WITH_PER_RUN_JUDGMENT_LINE_ANCHOR / NOT_GROUND_TRUTH"
                        if use_observed_detector_anchor else "TRACKER_ASSOCIATED_DETECTOR_HEAD_CANDIDATE / NOT_GROUND_TRUTH"
                    )
                )
            if kind == "hold":
                tracker_tail = next(
                    (tail for tail in reversed(rec["tail_points"])
                     if tail["frame"] == point["frame"] and tail["y"] < head_y),
                    None,
                )
                if (use_component_anchor and point["component_tail_y"] is not None
                        and point["component_tail_y"] < head_y):
                    item["tail_x"] = round(point["component_tail_x"], 2)
                    item["tail_y"] = round(point["component_tail_y"], 2)
                    item["tail_source"] = "UNIQUELY_OWNED_COLOR_COMPONENT_UPPER_ENDPOINT_CANDIDATE / NOT_GROUND_TRUTH"
                elif use_observed_detector_anchor and point.get("cut_component_candidate") is not None:
                    cut_candidate = point["cut_component_candidate"]
                    item["tail_x"] = round(_native_x(geometry, cut_candidate["top_x"], cut_candidate["top_y"]), 2)
                    item["tail_y"] = round(cut_candidate["top_y"], 2)
                    item["tail_source"] = "UNOWNED_CUT_MASK_COMPONENT_ENDPOINT_CANDIDATE / NOT_GROUND_TRUTH"
                    item["tail_component_bbox_rectified_observation"] = cut_candidate["bbox"]
                    item["tail_component_head_owner_count"] = 0
                    item["tail_component_detector_candidate_count"] = cut_candidate["candidate_detector_owner_count"]
                    item["tail_component_identity_ambiguous"] = True
                elif tracker_tail is not None:
                    item["tail_x"] = round(tracker_tail["x"], 2)
                    item["tail_y"] = round(tracker_tail["y"], 2)
                    item["tail_source"] = "TRACKER_ATTACHED_TAIL_CANDIDATE / NOT_GROUND_TRUTH"
                else:
                    if use_observed_detector_anchor:
                        if unowned_component_match is not None:
                            item["tail_x"] = round(_native_x(geometry, unowned_component_match["top_x"], unowned_component_match["top_y"]), 2)
                            item["tail_y"] = round(unowned_component_match["top_y"], 2)
                            item["tail_source"] = "UNOWNED_LANE_NEAR_COLOR_COMPONENT_ENDPOINT_CANDIDATE / NOT_GROUND_TRUTH"
                            item["tail_component_bbox_rectified_observation"] = unowned_component_match["bbox"]
                            item["tail_component_head_owner_count"] = unowned_component_match["head_owner_count"]
                            item["tail_component_identity_ambiguous"] = False
                        else:
                            tail_y = max(0.0, head_y - point["upper_ribbon_px"])
                            item["tail_x"] = round(_native_x(geometry, point["rectified_x"], tail_y), 2)
                            item["tail_y"] = round(tail_y, 2)
                            item["tail_source"] = "OBSERVED_LOCAL_GREEN_RIBBON_DEPTH_CANDIDATE / NOT_GROUND_TRUTH"
                    else:
                        item["tail_x"] = round(point["tail_x_estimate"], 2)
                        item["tail_y"] = round(point["tail_y_estimate"], 2)
                        item["tail_source"] = point["tail_source"]
                if item["tail_y"] >= head_y:
                    # Every provisional candidate above points toward smaller
                    # source y. Reject a connected-component endpoint on the
                    # far side of this head and keep only locally observed
                    # ribbon depth (or a degenerate body when none is visible).
                    guarded_tail_y = max(0.0, head_y - max(0.0, point["upper_ribbon_px"]))
                    item["tail_x"] = round(_native_x(geometry, point["rectified_x"], guarded_tail_y), 2)
                    item["tail_y"] = round(guarded_tail_y, 2)
                    item["tail_source"] = "DIRECTIONAL_GUARD_LOCAL_GREEN_RIBBON_FALLBACK / NOT_GROUND_TRUTH"
                    item["tail_component_identity_ambiguous"] = True
                item.setdefault("tail_component_bbox_rectified_observation", point["component_bbox_observed"])
                item.setdefault("tail_component_head_owner_count", point["component_head_owner_count"])
                item.setdefault("tail_component_identity_ambiguous", point["component_head_owner_count"] > 1)
            keyframes.append(item)
        inferred_gaps = _retrospective_partial_gaps(
            keyframe_points, points, kind, track_id, rec["confirmed_seen"],
            geometry.lane_pixels,
        )
        inferred_gaps.extend(_retrospective_native_cyan_effect_gaps(
            video, keyframe_points, points, kind, track_id, histories,
        ))
        confidence = min(0.94, 0.35 + min(direct_keyframe_count, 12) * 0.025 + (0.12 if rec["confirmed_seen"] else 0) + (0.08 if rec["kind_locked_seen"] else 0))
        majority_color = _majority_candidate_color(keyframe_points, kind, rec["color_history"])
        color = {"cyan": "#35D5FF", "yellow": "#FFCF4A", "pink": "#FF5CC8", "green": "#62E57A", "neutral": "#F0F0F0"}.get(majority_color, "#F0F0F0")
        scene_notes.append({
            "id": track_id,
            "type": "Tap" if kind == "tap" else "Hold",
            "lane": (
                offline_hold_evidence["observed_lane"]
                if offline_hold_evidence is not None
                else min(5, max(0, int(keyframe_points[0]["rectified_x"] // geometry.lane_pixels)))
            ),
            "confidence": round(confidence, 3),
            "confidence_status": "AUTO_HEURISTIC / NOT_CALIBRATED / PROVISIONAL",
            "color": color,
            "source": {
                "coordinate_system": "encoded_source_frame_px_origin_top_left",
                "provenance": "Legacy Perception candidates plus offline native-cyan edge-pair observations and causal Tracker association; not ground truth",
                "video_sha256": sha256(video), "index_sha256": sha256(index) if index is not None else None,
                "geometry_sha256": sha256(geometry_path),
            },
            "intervals": _intervals(
                [point["frame"] for point in keyframe_points], total_frames,
                inferred_gaps,
            ),
            "unobserved_intervals": _unobserved_intervals(
                [point["frame"] for point in keyframe_points], total_frames,
                inferred_gaps,
            ),
            "keyframes": keyframes,
            "association_status": (
                "OFFLINE_RETROSPECTIVE_PARTIAL_TRACK_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH"
                if partial_bridge_records else (
                    "OFFLINE_RETROSPECTIVE_STATIONARY_HOLD_CANDIDATE / PROVISIONAL / NOT_GROUND_TRUTH"
                    if offline_hold_evidence is not None else (
                        "OFFLINE_RETROSPECTIVE_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH"
                        if any(point.get("retrospective_association") for point in keyframe_points)
                        else "AUTO_VISUAL_REVIEWED / PROVISIONAL"
                    )
                )
            ),
            **({"source_partial_associations": [bridge["evidence"] for bridge in partial_bridge_records]}
               if partial_bridge_records else {}),
            **({"offline_stationary_hold_candidate_evidence": offline_hold_evidence}
               if offline_hold_evidence is not None else {}),
            "head_body_tail_evidence": {
                "hold_body": "straight head-to-tail geometry rendered; tail extent may be inferred from ribbon depth",
                "tail_observations": len(rec["tail_points"]),
                "tracker_identity_confirmed": rec["confirmed_seen"],
                "tracker_kind_locked": rec["kind_locked_seen"],
            } if kind == "hold" else {"tap_face_observations": len(points)},
        })

    timestamps = [float(row["capture_timestamp"]) for row in rows[:process_frames]]
    scene = {
        "schema_version": 1,
        "title": f"Provisional geometry reconstruction {run_dir.name}",
        "fps": fps,
        "frame_count": process_frames,
        "canvas": {"width": geometry.width, "height": geometry.height, "background": "#000000"},
        "track_guides": geometry_doc["track_guides"],
        "judgment_line": {
            "from": [round(float(geometry.boundaries(geometry_doc["judgment_line_y"])[0]), 2), geometry_doc["judgment_line_y"]],
            "to": [round(float(geometry.boundaries(geometry_doc["judgment_line_y"])[-1]), 2), geometry_doc["judgment_line_y"]],
        },
        "notes": scene_notes,
        "scene_status": "AUTO_RECONSTRUCTED / PROVISIONAL / NOT_GROUND_TRUTH",
        "source": {
            "run_id": run_dir.name, "video_path": video.as_posix(),
            "video_sha256": sha256(video), "index_path": index.as_posix() if index is not None else None,
            "index_sha256": sha256(index) if index is not None else None,
            "timestamp_source": "read_only_index_capture_timestamp" if index is not None else "encoded_video_frame_index_divided_by_this_clip_fps",
            "geometry_json": geometry_path.as_posix(),
            "geometry_sha256": sha256(geometry_path),
            "timestamp_basis": "per-frame capture_timestamp from read-only live_video_index.csv",
            "comparison_sync_basis": "encoded video_frame index; do not retime from nominal fps or infer common song speed",
        },
        "source_frame_timestamps": timestamps,
        "reconstruction_method": "Legacy src.perception/src.tracking read-only as provisional evidence generators plus isolated native-coordinate cyan face edge-pair observations and unique local retrospective Tap identity links; per-clip rectification; no key-event or mask ground truth",
        "review_queue": review_queue,
        "offline_native_cyan_tap_associations": {
            "status": "OFFLINE_RETROSPECTIVE / PROVISIONAL / NOT_GROUND_TRUTH",
            "direct_native_candidate_observations": len(native_cyan_observations),
            "accepted_unique_local_links": native_cyan_associations,
            "rule_scope": "Only direct native-frame cyan face edge-pair observations; unique confirmed same-color Tap path in the same lane bracketed by direct anchors and matching the local source path.",
        },
        "retrospective_recovery_tap_associations": retrospective_recovery_links,
        "recovery_only_tap_observations": [{
            "observation_index": point["observation_index"], "frame": point["frame"],
            "color": point["candidate_color"], "rectified_bbox": point["detector_rectified_bbox"],
            "rectified_head_bottom_xy": [round(point["rectified_x"], 2), round(point["rectified_y"], 2)],
            "source_head_bottom_xy": [round(point["head_x"], 2), round(point["head_y"], 2)],
            "score_uncalibrated": round(point["candidate_score_uncalibrated"], 4),
            "labels": ["DIRECT_DETECTOR_OBSERVATION", "PROVISIONAL", "NOT_GROUND_TRUTH"],
        } for point in recovery_tap_points],
        "recovery_tap_association_diagnostics": {
            "labels": ["PROVISIONAL", "NOT_GROUND_TRUTH", "OFFLINE_RETROSPECTIVE_DECISION_TRACE"],
            "recovery_observation_count": len(recovery_tap_points),
            "diagnostic_group_count": len(recovery_link_diagnostics),
            "groups": recovery_link_diagnostics,
        },
        "candidate_summary_not_ground_truth": {
            "scene_note_candidates": len(scene_notes),
            "unresolved_tracks": len(review_queue),
            "review_note": "These are output candidate tracks only, not true object counts or a completeness claim.",
        },
    }
    scene, association_refinement = refine_scene_track_discontinuities(scene, geometry_doc)
    scene["track_association_refinement"] = association_refinement
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(scene, indent=2), encoding="utf-8")
    return {
        "run_id": run_dir.name, "frames_processed": process_frames,
        "scene_note_candidates_not_ground_truth": len(scene_notes),
        "unresolved_tracks": len(review_queue),
        "offline_native_cyan_direct_observations": len(native_cyan_observations),
        "offline_native_cyan_accepted_links": len(native_cyan_associations),
        "scene_json": output_json.as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_video_or_run_dir", type=Path)
    parser.add_argument("geometry_json", type=Path)
    parser.add_argument("output_scene_json", type=Path)
    parser.add_argument("--max-frames", type=int, default=None, help="bounded diagnostic window; not a complete Scene")
    parser.add_argument("--index", type=Path, default=None, help="optional per-frame CSV with video_frame/capture_timestamp")
    args = parser.parse_args()
    print(json.dumps(reconstruct(args.source_video_or_run_dir, args.geometry_json, args.output_scene_json, args.max_frames, args.index), indent=2))


if __name__ == "__main__":
    main()
