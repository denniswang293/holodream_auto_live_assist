"""Offline pink-candidate -> SimpleTracker replay; never sends input."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2

from src.detector import detect
from src.geometry import Playfield
from src.simple_tracker import SimpleTracker, is_simple_tap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--index", type=Path, default=None,
                        help="live_video_index.csv with source-frame capture timestamps")
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    playfield = Playfield.from_config(cfg["playfield"], cfg["reference_resolution"])
    detector_cfg = {**cfg["detector"], "reference_resolution": cfg["reference_resolution"]}
    tracker = SimpleTracker({**cfg["tracker"], "max_eta_s": cfg["events"]["max_eta_s"]},
                            cfg["predictor"]["particle"], hit_y=325.5)
    index_path = args.index
    if index_path is None:
        sibling = args.source.parent / "live_video_index.csv"
        index_path = sibling if sibling.exists() else None
    timestamps = {}
    if index_path is not None and index_path.exists():
        with index_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    # The clean source MP4 is indexed by source_video_frame;
                    # source_frame is the capture sequence and can skip when
                    # frames are dropped.
                    source_frame = int(row.get("source_video_frame", row.get("source_frame", row.get("video_frame", ""))))
                    timestamps[source_frame] = float(row["capture_timestamp"])
                except (TypeError, ValueError, KeyError):
                    continue
    cap = cv2.VideoCapture(str(args.source))
    rows, frame_index = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        diagnostics = {}
        candidates = detect(frame, playfield, cfg["key_map"], detector_cfg,
                            diagnostics, frame_index=frame_index)
        pink = [c for c in candidates if c.appearance == "pink_candidate"]
        capture_timestamp = timestamps.get(frame_index)
        timestamp_source = "capture_timestamp" if capture_timestamp is not None else "frame_fallback"
        if capture_timestamp is None:
            capture_timestamp = frame_index / 60.0
        tracks = tracker.update([c for c in candidates if is_simple_tap(c)],
                                capture_timestamp, playing=True)
        visible = list(tracks)
        for track in visible + list(tracker.finished):
            if track.candidate.appearance != "pink_candidate":
                continue
            rows.append({"frame": frame_index, "track_id": track.track_id,
                         "bbox": track.candidate.bbox, "appearance": track.candidate.appearance,
                         "note_type": track.candidate.note_type,
                         "status": track.status, "confirmed_note_type": track.confirmed_note_type or "",
                         "observations": track.observations, "missed": track.missed,
                         "stable_keys": "|".join(track.stable_keys),
                         "hit_at": track.prediction.hit_time if track.prediction.hit_time is not None else "",
                         "candidate_count": len(pink), "candidate_note_types": "|".join(c.note_type for c in pink),
                         "capture_timestamp": capture_timestamp,
                         "timestamp_source": timestamp_source,
                         "track_reason": track.reason,
                         "association_reject_reason": track.association_reject_reason,
                         "finalized": int(track in tracker.finished)})
        frame_index += 1
    cap.release()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["status"]
    with args.out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    summary_rows = []
    by_track = {}
    for row in rows:
        by_track.setdefault(int(row["track_id"]), []).append(row)
    intervals = {
        track_id: (min(int(r["frame"]) for r in track_rows),
                   max(int(r["frame"]) for r in track_rows))
        for track_id, track_rows in by_track.items()
    }
    for track_id, track_rows in sorted(by_track.items()):
        first_frame, last_frame = intervals[track_id]
        nearby_uid = any(
            other_id != track_id and not (last_frame < other_first - 2 or
                                          other_last < first_frame - 2)
            for other_id, (other_first, other_last) in intervals.items())
        observed = [int(r["observations"]) for r in track_rows]
        times = [float(r["capture_timestamp"]) for r in track_rows]
        summary_rows.append({
            "track_id": track_id,
            "rows": len(track_rows),
            "first_frame": first_frame,
            "last_frame": last_frame,
            "first_capture_timestamp": min(times),
            "last_capture_timestamp": max(times),
            "duration_ms": (max(times) - min(times)) * 1000.0,
            "max_observations": max(observed),
            "max_missed": max(int(r["missed"]) for r in track_rows),
            "final_status": track_rows[-1]["status"],
            "final_reason": track_rows[-1]["track_reason"],
            "final_association_reject_reason": track_rows[-1]["association_reject_reason"],
            "confirmed": bool(track_rows[-1]["confirmed_note_type"]),
            "candidate_frames": sum(int(r["candidate_count"]) > 0 for r in track_rows),
            "nearby_uid_rebuild": nearby_uid,
        })
    summary_path = args.out.with_name(args.out.stem + "_summary.csv")
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        fields = list(summary_rows[0]) if summary_rows else ["status"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(summary_rows)
    print(json.dumps({"frames": frame_index, "pink_track_rows": len(rows),
                      "pink_track_ids": len({r["track_id"] for r in rows}),
                      "confirmed_track_ids": len({r["track_id"] for r in rows if r["confirmed_note_type"]}),
                      "timestamp_source": "capture_timestamp" if timestamps else "frame_fallback",
                      "output": str(args.out), "summary": str(summary_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
