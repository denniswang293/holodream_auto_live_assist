"""Audit V8.5 suppressed UNKNOWN fragments against same-frame Tap tracker inputs.

This is a trace audit only. Tracker UIDs are provider-local hypotheses, not
cross-version or physical-note ground truth.
"""
from __future__ import annotations

import argparse
import ast
import csv
from collections import Counter, defaultdict
from pathlib import Path


def parse_bbox(value: str) -> tuple[int, int, int, int] | None:
    try:
        parts = ast.literal_eval(value)
        if len(parts) != 4:
            return None
        return tuple(int(v) for v in parts)
    except (ValueError, SyntaxError, TypeError):
        return None


def contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    x, y, w, h = outer
    ix, iy, iw, ih = inner
    return x <= ix and y <= iy and x + w >= ix + iw and y + h >= iy + ih


def suppression_geometry(
    fragment: tuple[int, int, int, int], face: tuple[int, int, int, int]
) -> str | None:
    """Mirror the two geometric clauses in EarlyPerception's suppression rule."""
    x, y, w, h = fragment
    tx, ty, tw, th = face
    area = max(1, w * h)
    intersection = max(0, min(x + w, tx + tw) - max(x, tx)) * max(
        0, min(y + h, ty + th) - max(y, ty)
    )
    if (
        w == 12 and h == 8 and intersection >= 0.90 * area
        and area <= 0.12 * max(1, tw * th) and w <= 0.35 * tw and h <= 0.50 * th
    ):
        return "IN_PANEL_12X8_SIGNATURE"
    if h > 4 or w < 8:
        return None
    horizontal = max(0, min(x + w, tx + tw) - max(x, tx))
    if horizontal < 0.90 * w:
        return None
    if y >= ty + 0.65 * th and y >= ty + th - 4 and y + h <= ty + th + 1:
        return "BOTTOM_BEVEL_RAIL"
    return None


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace",
        nargs="?",
        type=Path,
        default=root / "output/analysis_v86_autoloop/iteration_0037/fixed_full_narrow/run_20261106T164049_800126Z/candidate_trace.csv",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=root / "output/analysis_v86_autoloop/iteration_0039/neutral_fragment_identity_audit.csv",
    )
    parser.add_argument(
        "--baseline-trace",
        type=Path,
        default=root / "output/analysis_v86_autoloop/iteration_0037/fixed_full_baseline_repeat/run_20261106T164049_800126Z/candidate_trace.csv",
    )
    args = parser.parse_args()
    if not args.trace.is_file():
        parser.error(f"trace not found: {args.trace}")
    if not args.baseline_trace.is_file():
        parser.error(f"baseline trace not found: {args.baseline_trace}")

    baseline_suppressed: dict[tuple[int, str], str] = {}
    with args.baseline_trace.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if (
                row.get("provider") == "v85"
                and row.get("candidate_stage") == "segmentation_to_detector"
                and (row.get("conversion") or "").startswith("suppressed")
            ):
                try:
                    baseline_suppressed[(int(row["video_frame"]), row.get("bbox", ""))] = row.get("conversion", "")
                except (KeyError, ValueError):
                    continue

    # Retain only the rows needed for this audit; the full trace is ~135 MB.
    by_frame: dict[int, dict[str, list[dict[str, str]]]] = defaultdict(
        lambda: {"suppressed": [], "faces": [], "tracker_faces": []}
    )
    with args.trace.open(newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row.get("provider") != "v85":
                continue
            stage = row.get("candidate_stage")
            role = row.get("role")
            if stage == "segmentation_to_detector" and row.get("conversion") == "suppressed_occluded_fragment":
                bucket = "suppressed"
            elif stage == "segmentation_to_detector" and role == "tap_face":
                bucket = "faces"
            elif stage == "tracker_input" and role == "tap_face":
                bucket = "tracker_faces"
            else:
                continue
            try:
                frame = int(row["video_frame"])
            except (KeyError, ValueError):
                continue
            by_frame[frame][bucket].append(row)

    fields = [
        "video_frame", "source_frame", "capture_timestamp", "acquired_timestamp",
        "fragment_component_id", "fragment_bbox", "fragment_color", "fragment_area",
        "parent_face_match_count", "parent_face_bboxes", "parent_face_component_ids",
        "suppression_geometry_match",
        "parent_tracker_uid_provider_local", "tracker_confirmed", "tracker_state",
        "tracker_reason", "timing_reason", "scheduled_press", "scheduler_pending",
        "parent_mapping_status", "suppression_reason",
        "baseline_conversion_same_frame_bbox", "suppression_delta_status",
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    totals = Counter()
    uid_stats: dict[str, Counter] = defaultdict(Counter)
    with args.output.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for frame in sorted(by_frame):
            group = by_frame[frame]
            faces = [r for r in group["faces"] if parse_bbox(r.get("bbox", ""))]
            tracker_rows: dict[tuple[int, int, int, int], dict[str, str]] = {}
            for row in group["tracker_faces"]:
                bbox = parse_bbox(row.get("bbox", ""))
                if bbox is not None:
                    tracker_rows[bbox] = row
            for fragment in group["suppressed"]:
                totals["suppressed_rows"] += 1
                fb = parse_bbox(fragment.get("bbox", ""))
                baseline_conversion = baseline_suppressed.get((frame, fragment.get("bbox", "")), "")
                if baseline_conversion:
                    delta_status = "BASELINE_SUPPRESSION_SAME_FRAME_BBOX"
                    totals["baseline_suppression_same_bbox_rows"] += 1
                elif fb and fb[2:] == (12, 8):
                    delta_status = "NEW_12X8_SIGNATURE_SUPPRESSION"
                    totals["new_12x8_signature_rows"] += 1
                else:
                    delta_status = "NEW_OR_UNMATCHED_SUPPRESSION"
                    totals["new_or_unmatched_suppression_rows"] += 1
                matches: list[tuple[dict[str, str], str]] = []
                for face in faces:
                    face_box = parse_bbox(face["bbox"])
                    geom = suppression_geometry(fb, face_box) if fb and face_box else None
                    if geom:
                        matches.append((face, geom))
                # Never resolve multiple geometrically eligible parents by
                # choosing an arbitrary smallest box. Keep those rows UNKNOWN.
                parent = matches[0][0] if len(matches) == 1 else None
                tracker = tracker_rows.get(parse_bbox(parent["bbox"])) if parent else None
                if matches:
                    totals["geometric_parent_match_rows"] += 1
                    totals["geometric_parent_pair_count"] += len(matches)
                    if len(matches) > 1:
                        totals["ambiguous_multiple_parent_rows"] += 1
                    totals[matches[0][1].lower() + "_rows"] += 1
                else:
                    totals["no_matching_suppression_geometry_rows"] += 1
                if tracker:
                    totals["same_frame_tracker_input"] += 1
                    if tracker.get("tracker_uid"):
                        totals["assigned_provider_local_uid"] += 1
                        uid = tracker["tracker_uid"]
                    else:
                        totals["unassigned_tracker_input"] += 1
                        uid = "UNASSIGNED"
                    uid_stats[uid]["suppressed_rows"] += 1
                    uid_stats[uid]["confirmed_rows"] += tracker.get("tracker_confirmed") == "True"
                    uid_stats[uid]["scheduled_rows"] += bool(tracker.get("scheduled_press"))
                else:
                    uid = ""
                    totals["no_exact_parent_tracker_input"] += 1
                writer.writerow({
                    "video_frame": frame,
                    "source_frame": fragment.get("source_frame", ""),
                    "capture_timestamp": fragment.get("capture_timestamp", ""),
                    "acquired_timestamp": fragment.get("acquired_timestamp", ""),
                    "fragment_component_id": fragment.get("component_id", ""),
                    "fragment_bbox": fragment.get("bbox", ""),
                    "fragment_color": fragment.get("color", ""),
                    "fragment_area": fragment.get("area", ""),
                    "parent_face_match_count": len(matches),
                    "parent_face_bboxes": "|".join(face.get("bbox", "") for face, _ in matches),
                    "parent_face_component_ids": "|".join(face.get("component_id", "") for face, _ in matches),
                    "suppression_geometry_match": matches[0][1] if len(matches) == 1 else ("AMBIGUOUS_MULTIPLE" if matches else "NONE"),
                    "parent_tracker_uid_provider_local": uid,
                    "tracker_confirmed": tracker.get("tracker_confirmed", "") if tracker else "",
                    "tracker_state": tracker.get("tracker_state", "") if tracker else "",
                    "tracker_reason": tracker.get("tracker_reason", "") if tracker else "",
                    "timing_reason": tracker.get("timing_reason", "") if tracker else "",
                    "scheduled_press": tracker.get("scheduled_press", "") if tracker else "",
                    "scheduler_pending": tracker.get("scheduler_pending", "") if tracker else "",
                    "parent_mapping_status": (
                        "AMBIGUOUS_MULTIPLE_PARENTS" if len(matches) > 1 else
                        "SAME_FRAME_TRACKER_INPUT_MATCH" if tracker and tracker.get("tracker_uid") else
                        "UNASSIGNED_TRACKER_INPUT" if tracker else
                        "TAP_FACE_NO_EXACT_TRACKER_INPUT" if parent else
                        "NO_MATCHING_SUPPRESSION_GEOMETRY"
                    ),
                    "suppression_reason": fragment.get("reason", ""),
                    "baseline_conversion_same_frame_bbox": baseline_conversion,
                    "suppression_delta_status": delta_status,
                })

    print(f"trace={args.trace}")
    print(f"baseline_trace={args.baseline_trace}")
    print(f"output={args.output}")
    print("totals=" + ", ".join(f"{k}={v}" for k, v in sorted(totals.items())))
    print("provider_local_uid_groups=" + str(len(uid_stats)))
    print("top_provider_local_uids=" + repr(sorted(uid_stats.items(), key=lambda kv: kv[1]['suppressed_rows'], reverse=True)[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
