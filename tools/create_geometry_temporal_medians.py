"""Reduce moving notes/effects with per-run temporal medians for rail review."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/geometry_alignment_review/temporal_medians"))
    parser.add_argument("--samples", type=int, default=41)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    all_medians = []
    for run in sorted(p for p in args.recording_root.glob("run_*") if p.is_dir()):
        cap = cv2.VideoCapture(str(run / "live_source.mp4"))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        for frame_no in np.linspace(1, max(1, count - 2), args.samples, dtype=int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_no))
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
        cap.release()
        if not frames:
            print(f"{run.name}: NO_DECODED_SAMPLES")
            continue
        median = np.median(np.stack(frames), axis=0).astype(np.uint8)
        path = args.out / f"{run.name}_median_{len(frames)}.png"
        cv2.imwrite(str(path), median)
        all_medians.append(median)
        print(path)
    if all_medians:
        combined = np.median(np.stack(all_medians), axis=0).astype(np.uint8)
        path = args.out / f"all_runs_median_{len(all_medians)}.png"
        cv2.imwrite(str(path), combined)
        print(path)
    return 0 if len(all_medians) == len(list(args.recording_root.glob("run_*"))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
