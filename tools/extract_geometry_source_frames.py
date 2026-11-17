"""Extract exact source frame IDs with names tied to their recording index."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/full_frames"))
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--frame", action="append", type=int, default=[])
    args = parser.parse_args()
    runs = args.run or [p.name for p in sorted(args.recording_root.glob("run_*")) if p.is_dir()]
    args.out.mkdir(parents=True, exist_ok=True)
    for run_id in runs:
        base = args.recording_root / run_id
        with (base / "live_video_index.csv").open("r", newline="", encoding="utf-8-sig") as stream:
            index = list(csv.DictReader(stream))
        cap = cv2.VideoCapture(str(base / "live_source.mp4"))
        for frame_id in args.frame:
            if not 0 <= frame_id < len(index):
                print(f"{run_id} frame {frame_id}: OUT_OF_RANGE")
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ok, frame = cap.read()
            if not ok:
                print(f"{run_id} frame {frame_id}: DECODE_ERROR")
                continue
            row = index[frame_id]
            name = f"{run_id}_f{frame_id:06d}_t{float(row['capture_timestamp']):.3f}.png"
            cv2.imwrite(str(args.out / name), frame)
            print(args.out / name)
        cap.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
