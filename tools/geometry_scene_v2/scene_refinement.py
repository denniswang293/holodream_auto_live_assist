"""Conservative offline Scene Timeline refinements for tracker identity breaks."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


SPLIT_LABELS = [
    "OFFLINE_RETROSPECTIVE_TRACK_DISCONTINUITY",
    "AUTO_VISUAL_REVIEWED",
    "PROVISIONAL",
    "NOT_GROUND_TRUTH",
]


def _rectified_lane_q(x: float, y: float, rail_boundaries: list[dict[str, float]]) -> float:
    boundaries = [
        rail["top_intercept_x"] + rail["slope_dx_per_dy"] * y
        for rail in rail_boundaries
    ]
    for lane in range(6):
        if boundaries[lane] <= x <= boundaries[lane + 1]:
            width = boundaries[lane + 1] - boundaries[lane]
            if width <= 0:
                return float(lane)
            return lane + (x - boundaries[lane]) / width
    return 0.0 if x < boundaries[0] else 6.0


def _direct_tap_keyframe(keyframe: dict[str, Any]) -> bool:
    return (
        keyframe.get("source_observation_kind") == "tap"
        and not keyframe.get("association_evidence")
        and not keyframe.get("head_measurement_labels")
    )


def _visibility_for_frames(
    frames: list[int], existing: list[dict[str, Any]], frame_count: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rebuild visible spans and retain only already-supported inferred gaps."""
    observed = sorted(set(frame for frame in frames if 0 <= frame < frame_count))
    intervals: list[dict[str, Any]] = []
    unobserved: list[dict[str, Any]] = []
    if not observed:
        return intervals, unobserved

    def prior_gap(start: int, end: int) -> dict[str, Any] | None:
        return next((
            span for span in existing
            if span.get("state") == "occluded"
            and span.get("start_frame") == start
            and span.get("end_frame") == end
            and {"INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"}.issubset(set(span.get("labels", [])))
        ), None)

    start = previous = observed[0]
    for current in observed[1:]:
        if current == previous + 1:
            previous = current
            continue
        intervals.append({"state": "visible", "start_frame": start, "end_frame": previous + 1})
        gap_start, gap_end = previous + 1, current
        gap = prior_gap(gap_start, gap_end)
        if gap:
            intervals.append(deepcopy(gap))
        else:
            unobserved.append({
                "state": "UNOBSERVED", "start_frame": gap_start, "end_frame": gap_end,
                "labels": ["NO_DIRECT_NOTE_OBSERVATION", "NOT_OCCLUSION_EVIDENCE"],
            })
        start = previous = current
    intervals.append({"state": "visible", "start_frame": start, "end_frame": previous + 1})
    return intervals, unobserved


def refine_scene_track_discontinuities(
    scene: dict[str, Any], geometry_doc: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split only direct Tap tracks with a one-frame lane jump and upward reversal.

    The gate is geometric and local to this clip: consecutive direct Tap faces
    must move at least one rectified lane sideways while the observed head
    moves upward by at least six source pixels. This catches source identity
    swaps without assuming a cross-song or within-song movement speed. Holds,
    partial/retrospective anchors, frame gaps, and downward-moving candidates
    are left untouched.
    """
    frame_count = int(scene["frame_count"])
    rails = geometry_doc["rail_boundaries"]
    all_ids = {str(note["id"]) for note in scene.get("notes", [])}
    output: list[dict[str, Any]] = []
    split_records: list[dict[str, Any]] = []

    for note in scene.get("notes", []):
        keyframes = sorted(note.get("keyframes", []), key=lambda item: int(item["frame"]))
        cut_indices: list[tuple[int, dict[str, Any]]] = []
        if note.get("type") == "Tap":
            for index, (left, right) in enumerate(zip(keyframes, keyframes[1:]), start=1):
                if not (_direct_tap_keyframe(left) and _direct_tap_keyframe(right)):
                    continue
                if left.get("candidate_color_observed") != right.get("candidate_color_observed"):
                    continue
                if int(right["frame"]) - int(left["frame"]) != 1:
                    continue
                lane_delta = (
                    _rectified_lane_q(float(right["head_x"]), float(right["head_y"]), rails)
                    - _rectified_lane_q(float(left["head_x"]), float(left["head_y"]), rails)
                )
                upward_delta = float(right["head_y"]) - float(left["head_y"])
                if abs(lane_delta) >= 1.0 and upward_delta <= -6.0:
                    cut_indices.append((index, {
                        "split_before_frame": int(right["frame"]),
                        "previous_frame": int(left["frame"]),
                        "rectified_lane_q_delta": round(lane_delta, 4),
                        "source_head_y_delta_px": round(upward_delta, 2),
                        "labels": list(SPLIT_LABELS),
                    }))

        # Do not turn a single detector outlier into its own note candidate.
        valid_cuts = [
            item for item in cut_indices
            if item[0] >= 3 and len(keyframes) - item[0] >= 3
        ]
        if not valid_cuts:
            output.append(note)
            continue

        boundaries = [0] + [item[0] for item in valid_cuts] + [len(keyframes)]
        for segment_no, (begin, end) in enumerate(zip(boundaries, boundaries[1:])):
            segment = deepcopy(note)
            segment_frames = keyframes[begin:end]
            original_id = str(note["id"])
            if segment_no == 0:
                segment_id = original_id
            else:
                segment_id = f"{original_id}#segment@{segment_frames[0]['frame']}"
                suffix = 2
                while segment_id in all_ids:
                    segment_id = f"{original_id}#segment@{segment_frames[0]['frame']}-{suffix}"
                    suffix += 1
            all_ids.add(segment_id)
            segment["id"] = segment_id
            segment["keyframes"] = segment_frames
            frames = [int(item["frame"]) for item in segment_frames]
            segment["intervals"], segment["unobserved_intervals"] = _visibility_for_frames(
                frames, note.get("intervals", []), frame_count,
            )
            if segment_frames:
                first = segment_frames[0]
                q = _rectified_lane_q(float(first["head_x"]), float(first["head_y"]), rails)
                segment["lane"] = min(5, max(0, int(q)))
            segment["confidence"] = min(float(note.get("confidence", 0.65)), 0.65)
            segment["association_status"] = (
                "OFFLINE_RETROSPECTIVE_TRACK_DISCONTINUITY_SPLIT / "
                "AUTO_VISUAL_REVIEWED / PROVISIONAL / NOT_GROUND_TRUTH"
            )
            segment["association_split"] = {
                "original_track_id": original_id,
                "segment_number_zero_based": segment_no,
                "segment_count": len(boundaries) - 1,
                "evidence": [deepcopy(item[1]) for item in valid_cuts],
                "labels": list(SPLIT_LABELS),
            }
            if segment.get("type") == "Tap":
                segment.setdefault("head_body_tail_evidence", {})[
                    "tap_face_observations"
                ] = len(segment_frames)
            output.append(segment)

        split_records.append({
            "original_track_id": str(note["id"]),
            "segment_ids": [str(item["id"]) for item in output[-(len(boundaries) - 1):]],
            "cuts": [deepcopy(item[1]) for item in valid_cuts],
            "labels": list(SPLIT_LABELS),
        })

    result = deepcopy(scene)
    result["notes"] = output
    return result, {
        "status": "OFFLINE_RETROSPECTIVE / PROVISIONAL / NOT_GROUND_TRUTH",
        "rule": "same-color consecutive direct Tap faces, |delta rectified lane q| >= 1.0, source head y delta <= -6 px, at least 3 observations on both sides",
        "split_track_count": len(split_records),
        "split_records": split_records,
    }
