#!/usr/bin/env python3
"""Pair source and geometry-only renders frame-for-frame for review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def render(source_path: Path, geometry_path: Path, output_path: Path) -> dict[str, object]:
    source = cv2.VideoCapture(str(source_path))
    geometry = cv2.VideoCapture(str(geometry_path))
    if not source.isOpened() or not geometry.isOpened():
        source.release(); geometry.release()
        raise ValueError("could not open source and geometry videos")
    source_count = int(source.get(cv2.CAP_PROP_FRAME_COUNT))
    geometry_count = int(geometry.get(cv2.CAP_PROP_FRAME_COUNT))
    source_fps = float(source.get(cv2.CAP_PROP_FPS))
    geometry_fps = float(geometry.get(cv2.CAP_PROP_FPS))
    sw, sh = int(source.get(cv2.CAP_PROP_FRAME_WIDTH)), int(source.get(cv2.CAP_PROP_FRAME_HEIGHT))
    gw, gh = int(geometry.get(cv2.CAP_PROP_FRAME_WIDTH)), int(geometry.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if source_count != geometry_count or abs(source_fps - geometry_fps) > 1e-6:
        source.release(); geometry.release()
        raise ValueError(f"frame/fps mismatch: source {source_count}@{source_fps}, geometry {geometry_count}@{geometry_fps}")
    if (sw, sh) != (gw, gh):
        source.release(); geometry.release()
        raise ValueError(f"resolution mismatch: source {(sw, sh)}, geometry {(gw, gh)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), source_fps, (sw + gw, sh), True)
    if not writer.isOpened():
        source.release(); geometry.release()
        raise RuntimeError(f"could not open comparison writer: {output_path}")
    written = 0
    try:
        while written < source_count:
            ok_source, source_frame = source.read()
            ok_geometry, geometry_frame = geometry.read()
            if not ok_source or not ok_geometry:
                raise ValueError(f"decode ended before aligned frame {written}")
            writer.write(cv2.hconcat((source_frame, geometry_frame)))
            written += 1
    finally:
        source.release(); geometry.release(); writer.release()
    return {
        "frames": written, "fps": source_fps, "size": [sw + gw, sh],
        "duration_s": written / source_fps,
        "sync_basis": "one-to-one encoded video frame index; source capture_timestamp remains in the Scene JSON",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_mp4", type=Path)
    parser.add_argument("geometry_mp4", type=Path)
    parser.add_argument("comparison_mp4", type=Path)
    args = parser.parse_args()
    print(json.dumps(render(args.source_mp4, args.geometry_mp4, args.comparison_mp4), indent=2))


if __name__ == "__main__":
    main()
