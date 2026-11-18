#!/usr/bin/env python3
"""Build a provisional geometry and Scene package from one MP4 clip."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import cv2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT_ROOT = (ROOT / "output" / "geometry_scene_v2").resolve()
sys.path.insert(0, str(HERE))

from estimate_geometry import detect
from reconstruct_scene import reconstruct
from render_scene import render
from render_comparison import render as render_comparison


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"cannot decode video: {path}")
    result = {
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "fps": float(cap.get(cv2.CAP_PROP_FPS)),
        "size": [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))],
    }
    result["last_frame_decodes"] = False
    if result["frames"] > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, result["frames"] - 1)
        result["last_frame_decodes"] = bool(cap.read()[0])
    cap.release()
    return result


def _clip_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", value):
        raise ValueError("clip ID must be 1-80 letters, digits, dots, underscores, or hyphens and start with a letter or digit")
    return value


def process_clip(video: Path, output_dir: Path, index: Path | None = None, clip_id: str | None = None) -> dict[str, Any]:
    video = video.resolve(strict=True)
    if not video.is_file() or video.suffix.lower() != ".mp4":
        raise ValueError("input must be an existing MP4 file")
    if index is not None:
        index = index.resolve(strict=True)
        if not index.is_file():
            raise ValueError("--index must be a CSV file")
    elif (video.parent / "live_video_index.csv").is_file():
        raise ValueError("a sibling live_video_index.csv exists; pass it explicitly with --index or move the clip to a directory without it")

    output_dir = output_dir.resolve()
    if output_dir == OUTPUT_ROOT or not output_dir.is_relative_to(OUTPUT_ROOT):
        raise ValueError(f"output directory must be a child of {OUTPUT_ROOT}")
    if output_dir == video.parent or video.is_relative_to(output_dir):
        raise ValueError("output directory must not contain or be the source video directory")
    if index is not None and (output_dir == index.parent or index.is_relative_to(output_dir)):
        raise ValueError("output directory must not contain or be the index directory")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {output_dir}")

    run_id = _clip_id(clip_id if clip_id is not None else re.sub(r"[^A-Za-z0-9._-]+", "_", video.stem).strip("._-")[:80] or "clip")
    output_dir.mkdir(parents=True, exist_ok=True)
    source_hash_before = sha256(video)
    index_hash_before = sha256(index) if index is not None else None
    paths = {name: output_dir / name for name in ("geometry.json", "scene.json", "geometry.mp4", "comparison.mp4")}

    geometry = detect(video, index)
    geometry["run_id"] = run_id
    geometry["truth_status"] = "AUTO_GEOMETRY_ESTIMATE / PROVISIONAL / NOT_GROUND_TRUTH"
    geometry["labels"] = ["PROVISIONAL", "NOT_GROUND_TRUTH"]
    geometry["source"]["video_path"] = video.as_posix()
    geometry["source"]["index_path"] = index.as_posix() if index else None
    geometry["source"]["index_sha256"] = index_hash_before
    paths["geometry.json"].write_text(json.dumps(geometry, indent=2), encoding="utf-8")

    summary = reconstruct(video, paths["geometry.json"], paths["scene.json"], index_path=index)
    summary["run_id"] = run_id
    scene = json.loads(paths["scene.json"].read_text(encoding="utf-8"))
    scene["title"] = f"Provisional geometry reconstruction {run_id}"
    scene["source"]["run_id"] = run_id
    scene["source"]["timestamp_basis"] = (
        "per-frame capture_timestamp from explicitly supplied read-only index"
        if index else "encoded video frame index divided by this clip's fps"
    )
    render(scene, paths["geometry.mp4"])
    pair_info = render_comparison(video, paths["geometry.mp4"], paths["comparison.mp4"])
    paths["scene.json"].write_text(json.dumps(scene, indent=2), encoding="utf-8")

    source_probe = probe(video)
    geometry_probe = probe(paths["geometry.mp4"])
    comparison_probe = probe(paths["comparison.mp4"])
    expected_frames = geometry["source"]["frame_count"]
    if source_probe["frames"] != expected_frames or geometry_probe["frames"] != expected_frames or comparison_probe["frames"] != expected_frames:
        raise ValueError("source and rendered videos must have the full matching frame count")
    if not all(p["last_frame_decodes"] for p in (source_probe, geometry_probe, comparison_probe)):
        raise ValueError("could not decode the last frame of source or rendered video")
    if any(abs(p["fps"] - source_probe["fps"]) > 1e-6 for p in (geometry_probe, comparison_probe)):
        raise ValueError("rendered FPS does not match source FPS")
    source_size = source_probe["size"]
    if geometry_probe["size"] != source_size or comparison_probe["size"] != [source_size[0] * 2, source_size[1]]:
        raise ValueError("render dimensions do not match source and side-by-side pairing")
    if scene["frame_count"] != expected_frames or scene["canvas"]["width"] != source_size[0] or scene["canvas"]["height"] != source_size[1]:
        raise ValueError("Scene dimensions or frame count do not match source video")

    outputs = {name: {"path": path.name, "sha256": sha256(path)} for name, path in paths.items()}
    manifest = {
        "schema": "geometry_scene_v2.clip_build.v1",
        "status": "AUTO_RECONSTRUCTED / PROVISIONAL / NOT_GROUND_TRUTH",
        "run_id": run_id,
        "source_video": {"path": video.as_posix(), "sha256_before": source_hash_before, **source_probe},
        "source_index": {"path": index.as_posix(), "sha256_before": index_hash_before} if index else None,
        "geometry_config": {"path": paths["geometry.json"].name, "sha256": outputs["geometry.json"]["sha256"]},
        "pipeline_sources": {
            name: {"path": (HERE / name).as_posix(), "sha256": sha256(HERE / name)}
            for name in ("process_clip.py", "estimate_geometry.py", "offline_perception.py", "reconstruct_scene.py", "render_scene.py", "render_comparison.py")
        },
        "outputs": outputs,
        "geometry_video_probe": geometry_probe,
        "comparison_video_probe": {**comparison_probe, "pairing": pair_info["sync_basis"]},
        "scene_build_summary": summary,
        "labels": ["PROVISIONAL", "NOT_GROUND_TRUTH"],
    }
    if sha256(video) != source_hash_before:
        raise ValueError("source video hash changed during processing")
    if index is not None and sha256(index) != index_hash_before:
        raise ValueError("source index hash changed during processing")
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_mp4", type=Path)
    parser.add_argument("output_dir", type=Path, help="new directory under output/geometry_scene_v2/")
    parser.add_argument("--index", type=Path, default=None, help="optional read-only CSV with one row per encoded frame")
    parser.add_argument("--id", dest="clip_id", help="simple clip label; defaults to the input filename")
    args = parser.parse_args()
    print(json.dumps(process_clip(args.source_mp4, args.output_dir, args.index, args.clip_id), indent=2))


if __name__ == "__main__":
    main()
