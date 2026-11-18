#!/usr/bin/env python3
"""Build one provisional Scene, blank geometry render, and frame-paired comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from reconstruct_scene import reconstruct
from render_scene import render
from render_comparison import render as render_comparison


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict[str, object]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"cannot decode output {path}")
    result = {
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "fps": float(cap.get(cv2.CAP_PROP_FPS)),
        "size": [int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))],
    }
    if result["frames"]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(result["frames"]) - 1)
        ok, _ = cap.read()
        result["last_frame_decodes"] = bool(ok)
    cap.release()
    return result


def process(source: Path, geometry_json: Path, output_dir: Path, index: Path | None = None) -> dict[str, object]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_path, geometry_path, comparison_path = (output_dir / name for name in ("scene.json", "geometry.mp4", "comparison.mp4"))
    scene_info = reconstruct(source, geometry_json, scene_path, index_path=index)
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    render(scene, geometry_path)
    video = source if source.is_file() else source / "live_source.mp4"
    pair_info = render_comparison(video, geometry_path, comparison_path)
    scene["automatic_visual_review"] = {
        "status": "NOT_REVIEWED",
        "scope": "No source/geometry visual review has been performed yet for this run.",
    }
    scene_path.write_text(json.dumps(scene, indent=2), encoding="utf-8")
    source_index = index if index is not None else (video.parent / "live_video_index.csv" if (video.parent / "live_video_index.csv").is_file() else None)
    geometry_probe, comparison_probe = probe(geometry_path), probe(comparison_path)
    if geometry_probe["frames"] != scene["frame_count"] or comparison_probe["frames"] != scene["frame_count"]:
        raise ValueError("rendered frame counts do not match the Scene/source")
    if tuple(geometry_probe["size"]) != (scene["canvas"]["width"], scene["canvas"]["height"]):
        raise ValueError("geometry resolution does not match the Scene canvas")
    manifest = {
        "schema": "geometry_scene_v2.run_build.v1",
        "status": "AUTO_RECONSTRUCTED / PROVISIONAL / NOT_GROUND_TRUTH",
        "run_id": scene["source"]["run_id"],
        "source_video_sha256_before": sha256(video),
        "source_index_sha256_before": sha256(source_index) if source_index else None,
        "geometry_config_sha256": sha256(geometry_json),
        "pipeline_sources": {
            name: {"path": (HERE / name).as_posix(), "sha256": sha256(HERE / name)}
            for name in ("process_run.py", "reconstruct_scene.py", "render_scene.py", "render_comparison.py")
        },
        "scene": {"path": scene_path.name, "sha256": sha256(scene_path), "candidate_tracks_not_ground_truth": len(scene["notes"]), "unresolved_tracks": len(scene["review_queue"])},
        "geometry_video": {"path": geometry_path.name, "sha256": sha256(geometry_path), **geometry_probe},
        "comparison_video": {"path": comparison_path.name, "sha256": sha256(comparison_path), **comparison_probe, "pairing": pair_info["sync_basis"]},
        "scene_build_summary": scene_info,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if sha256(video) != manifest["source_video_sha256_before"]:
        raise ValueError("source video hash changed during processing")
    if source_index and sha256(source_index) != manifest["source_index_sha256_before"]:
        raise ValueError("source index hash changed during processing")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_video_or_run_dir", type=Path)
    parser.add_argument("geometry_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--index", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(process(args.source_video_or_run_dir, args.geometry_json, args.output_dir, args.index), indent=2))


if __name__ == "__main__":
    main()
