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
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8-sig"))
    playfield = Playfield.from_config(cfg["playfield"], cfg["reference_resolution"])
    detector_cfg = {**cfg["detector"], "reference_resolution": cfg["reference_resolution"]}
    tracker = SimpleTracker({**cfg["tracker"], "max_eta_s": cfg["events"]["max_eta_s"]},
                            cfg["predictor"]["particle"], hit_y=325.5)
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
        tracks = tracker.update([c for c in candidates if is_simple_tap(c)],
                                frame_index / 60.0, playing=True)
        for track in tracks:
            if track.candidate.appearance != "pink_candidate":
                continue
            rows.append({"frame": frame_index, "track_id": track.track_id,
                         "bbox": track.candidate.bbox, "appearance": track.candidate.appearance,
                         "note_type": track.candidate.note_type,
                         "status": track.status, "confirmed_note_type": track.confirmed_note_type or "",
                         "observations": track.observations, "missed": track.missed,
                         "stable_keys": "|".join(track.stable_keys),
                         "hit_at": track.prediction.hit_time if track.prediction.hit_time is not None else "",
                         "candidate_count": len(pink), "candidate_note_types": "|".join(c.note_type for c in pink)})
        frame_index += 1
    cap.release()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["status"]
    with args.out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"frames": frame_index, "pink_track_rows": len(rows),
                      "pink_track_ids": len({r["track_id"] for r in rows}),
                      "confirmed_track_ids": len({r["track_id"] for r in rows if r["confirmed_note_type"]}),
                      "output": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
