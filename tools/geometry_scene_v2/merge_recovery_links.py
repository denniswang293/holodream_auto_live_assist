#!/usr/bin/env python3
"""Merge explicitly selected provisional recovery observations into a full Scene."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _mark_observed_visible(intervals: list[dict[str, Any]], frame: int, frame_count: int) -> list[dict[str, Any]]:
    if not 0 <= frame < frame_count:
        raise ValueError(f"frame outside Scene: {frame}")
    result: list[dict[str, Any]] = []
    covered = False
    for span in intervals:
        start, end = int(span["start_frame"]), int(span["end_frame"])
        if not start <= frame < end:
            result.append(dict(span))
            continue
        covered = True
        if span["state"] == "visible":
            result.append(dict(span))
            continue
        if start < frame:
            left = dict(span)
            left["end_frame"] = frame
            result.append(left)
        result.append({"state": "visible", "start_frame": frame, "end_frame": frame + 1,
                       "labels": ["OFFLINE_RETROSPECTIVE_ASSOCIATION", "PROVISIONAL", "NOT_GROUND_TRUTH"]})
        if frame + 1 < end:
            right = dict(span)
            right["start_frame"] = frame + 1
            result.append(right)
    if not covered:
        result.append({"state": "visible", "start_frame": frame, "end_frame": frame + 1,
                       "labels": ["OFFLINE_RETROSPECTIVE_ASSOCIATION", "PROVISIONAL", "NOT_GROUND_TRUTH"]})
    result.sort(key=lambda item: (item["start_frame"], item["end_frame"]))
    compact: list[dict[str, Any]] = []
    for span in result:
        if (compact and compact[-1]["state"] == span["state"] == "visible"
                and compact[-1]["end_frame"] == span["start_frame"]):
            compact[-1]["end_frame"] = span["end_frame"]
            labels = list(dict.fromkeys(compact[-1].get("labels", []) + span.get("labels", [])))
            if labels:
                compact[-1]["labels"] = labels
        else:
            compact.append(span)
    return compact


def merge(baseline_path: Path, candidate_path: Path, output_path: Path, track_ids: list[str]) -> dict[str, Any]:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if baseline["source"]["run_id"] != candidate["source"]["run_id"]:
        raise ValueError("source run IDs differ")
    for key in ("video_sha256", "index_sha256", "geometry_sha256"):
        if baseline["source"].get(key) != candidate["source"].get(key):
            raise ValueError(f"source provenance differs: {key}")
    if baseline["frame_count"] != candidate["frame_count"] or baseline["fps"] != candidate["fps"]:
        raise ValueError("Scene frame count or FPS differs")

    links_by_track: dict[str, list[dict[str, Any]]] = {}
    for link in candidate.get("retrospective_recovery_tap_associations", []):
        links_by_track.setdefault(link["track_id"], []).append(link)
    base_notes = {note["id"]: note for note in baseline["notes"]}
    candidate_notes = {note["id"]: note for note in candidate["notes"]}
    merged: list[dict[str, Any]] = []
    for track_id in track_ids:
        if track_id not in links_by_track or track_id not in base_notes or track_id not in candidate_notes:
            raise ValueError(f"selected track missing from candidate links or either Scene: {track_id}")
        base_note, candidate_note = base_notes[track_id], candidate_notes[track_id]
        if base_note["type"] != "Tap" or candidate_note["type"] != "Tap":
            raise ValueError(f"selected track is not a Tap: {track_id}")
        selected_frames = {link["frame"] for link in links_by_track[track_id]}
        recovered = [key for key in candidate_note["keyframes"] if key["frame"] in selected_frames]
        if selected_frames != {key["frame"] for key in recovered}:
            raise ValueError(f"candidate Scene lacks a selected recovery keyframe: {track_id}")
        if any(not key.get("association_evidence", {}).get("status", "").startswith("OFFLINE_RETROSPECTIVE_ASSOCIATION") for key in recovered):
            raise ValueError(f"recovery keyframe missing retrospective association label: {track_id}")

        by_frame = {key["frame"]: key for key in base_note["keyframes"]}
        for key in recovered:
            old = by_frame.get(key["frame"])
            if old is not None:
                if old.get("source_observation_kind") == "tap":
                    old_box, new_box = old.get("source_bbox"), key.get("source_bbox")
                    if not old_box or not new_box:
                        raise ValueError(f"cannot compare coincident Tap anchors at {track_id}:{key['frame']}")
                    dx = abs((old_box[0] + old_box[2] / 2) - (new_box[0] + new_box[2] / 2))
                    dy = abs((old_box[1] + old_box[3]) - (new_box[1] + new_box[3]))
                    if dx > 40 or dy > 24:
                        raise ValueError(f"recovery keyframe conflicts with existing Tap anchor: {track_id}:{key['frame']}")
                elif old.get("source_observation_kind") != "plate_fragment":
                    raise ValueError(f"unexpected same-frame keyframe kind: {track_id}:{key['frame']}")
            by_frame[key["frame"]] = key
            base_note["intervals"] = _mark_observed_visible(base_note["intervals"], int(key["frame"]), baseline["frame_count"])
        base_note["keyframes"] = [by_frame[frame] for frame in sorted(by_frame)]
        base_note["association_status"] = "OFFLINE_RETROSPECTIVE_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH"
        base_note.setdefault("source", {})["recovery_link_merge"] = {
            "candidate_scene": candidate_path.as_posix(),
            "selected_frames": sorted(selected_frames),
            "association_status": "OFFLINE_RETROSPECTIVE_ASSOCIATION / PROVISIONAL / NOT_GROUND_TRUTH",
        }
        merged.extend({"track_id": track_id, "frame": key["frame"],
                       "association_evidence": key["association_evidence"]} for key in recovered)

    baseline["selected_retrospective_recovery_associations"] = merged
    baseline["automatic_visual_review"] = {
        "status": "AUTO_VISUAL_REVIEWED / PROVISIONAL",
        "scope": "Run7 recovery-link frames 1039-1042 for note:1173; selected source-visible Tap alignment reviewed in synchronized comparison.",
        "limitations": "Review is sparse and not ground truth; remaining links, Holds, and full-run note completeness are unresolved.",
    }
    if output_path.exists():
        raise FileExistsError(f"refusing to overwrite Scene: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return {"run_id": baseline["source"]["run_id"], "selected_tracks": track_ids,
            "merged_direct_observation_frames": len(merged), "scene_path": output_path.as_posix()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_scene", type=Path)
    parser.add_argument("candidate_scene", type=Path)
    parser.add_argument("output_scene", type=Path)
    parser.add_argument("--track-id", action="append", required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args.baseline_scene, args.candidate_scene, args.output_scene, args.track_id), indent=2))


if __name__ == "__main__":
    main()
