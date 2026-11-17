"""Create source review sheets at fixed temporal positions for every inventoried run."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("output/geometry_video_v1/inventory.json"))
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    samples = []
    for run in inventory:
        if run.get("availability") != "AVAILABLE":
            continue
        count = int(run["video"].get("nb_read_frames") or run["index"]["rows"])
        csv_path = args.recording_root / run["run_id"] / "live_video_index.csv"
        with csv_path.open("r", newline="", encoding="utf-8-sig") as stream:
            index = list(csv.DictReader(stream))
        cap = cv2.VideoCapture(str(args.recording_root / run["run_id"] / "live_source.mp4"))
        for fraction, label in ((0.10, "early"), (0.50, "middle"), (0.90, "late")):
            frame_no = min(count - 1, round((count - 1) * fraction))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            ok, frame = cap.read()
            if not ok:
                continue
            row = index[frame_no]
            thumb = cv2.resize(frame, (426, 240), interpolation=cv2.INTER_AREA)
            cv2.rectangle(thumb, (0, 0), (426, 30), (10, 10, 10), -1)
            title = f"{run['run_id']} {label} frame={frame_no} capture={float(row['capture_timestamp']):.3f}s"
            cv2.putText(thumb, title, (5, 21), cv2.FONT_HERSHEY_SIMPLEX, .43, (255, 255, 255), 1, cv2.LINE_AA)
            name = f"{run['run_id']}_{label}_f{frame_no:06d}.jpg"
            cv2.imwrite(str(args.out / name), thumb)
            samples.append((run["run_id"], label, thumb))
        cap.release()
    canvas = np.zeros((len(samples) * 260, 426, 3), dtype=np.uint8)
    for row, (_, _, thumb) in enumerate(samples):
        canvas[row * 260:row * 260 + 240] = thumb
    sheet = args.out / "source_head_middle_tail_contact_sheet.jpg"
    cv2.imwrite(str(sheet), canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"Wrote {len(samples)} source samples to {args.out} and {sheet}")
    return 0 if len(samples) == len(inventory) * 3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
