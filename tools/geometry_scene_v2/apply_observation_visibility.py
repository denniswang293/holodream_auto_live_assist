#!/usr/bin/env python3
"""Re-render a Scene using only directly observed visibility spans.

Existing note keyframes and source coordinates are preserved. Detector gaps
are stored as unobserved metadata; this tool does not infer note presence or
occlusion from a gap's duration.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import cv2

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT_ROOT = (ROOT / "output" / "geometry_scene_v2").resolve()
sys.path.insert(0, str(HERE))

from reconstruct_scene import _intervals, _unobserved_intervals
from render_scene import render, validate_scene
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


def apply(scene: dict[str, Any]) -> dict[str, Any]:
    scene = json.loads(json.dumps(scene))
    totals = {"removed_inferred_spans": 0, "removed_inferred_frames": 0, "unobserved_spans": 0}
    for note in scene["notes"]:
        frame_count = scene["frame_count"]
        old_intervals = note.get("intervals", [])
        inferred = [
            span for span in old_intervals
            if span.get("state") == "occluded"
            and {"INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"}.issubset(set(span.get("labels", [])))
        ]
        directly_observed_occlusion = [
            span for span in old_intervals
            if span.get("state") == "occluded"
            and not {"INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"}.intersection(set(span.get("labels", [])))
        ]
        frames = [key["frame"] for key in note["keyframes"]]
        visible = _intervals(frames, frame_count)
        retained = sorted([*visible, *directly_observed_occlusion], key=lambda span: span["start_frame"])
        for left, right in zip(retained, retained[1:]):
            if left["end_frame"] > right["start_frame"]:
                raise ValueError(f"observed and directly labeled occlusion intervals overlap for {note['id']}")
        unobserved = _unobserved_intervals(frames, frame_count)
        if directly_observed_occlusion:
            unobserved = [
                gap for gap in unobserved
                if not any(
                    max(gap["start_frame"], span["start_frame"]) < min(gap["end_frame"], span["end_frame"])
                    for span in directly_observed_occlusion
                )
            ]
        note["intervals"] = retained
        note["unobserved_intervals"] = unobserved
        totals["removed_inferred_spans"] += len(inferred)
        totals["removed_inferred_frames"] += sum(span["end_frame"] - span["start_frame"] for span in inferred)
        totals["unobserved_spans"] += len(unobserved)
    scene["visibility_policy"] = {
        "version": "direct-observation-only-v1",
        "status": "PROVISIONAL",
        "rule": "A detector gap is not occlusion evidence. Only source-reviewed or explicitly observed occlusion may be placed in intervals; unobserved gaps remain metadata and are not rendered.",
        **totals,
    }
    scene["automatic_visual_review"] = {
        "status": "NOT_REVIEWED",
        "scope": "Visibility intervals were revised; the regenerated geometry has not yet received source comparison review.",
    }
    return validate_scene(scene)


def process(scene_path: Path, source_video: Path, output_dir: Path, index: Path | None = None) -> dict[str, Any]:
    scene_path = scene_path.resolve(strict=True)
    source_video = source_video.resolve(strict=True)
    if index is not None:
        index = index.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir == OUTPUT_ROOT or not output_dir.is_relative_to(OUTPUT_ROOT):
        raise ValueError(f"output directory must be a child of {OUTPUT_ROOT}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {output_dir}")
    source_hash_before = sha256(source_video)
    index_hash_before = sha256(index) if index else None
    original = json.loads(scene_path.read_text(encoding="utf-8"))
    old_scene_hash = sha256(scene_path)
    source_probe = probe(source_video)
    if source_probe["frames"] != original["frame_count"]:
        raise ValueError("source/Scene frame count mismatch")
    if index is not None:
        with index.open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != source_probe["frames"]:
            raise ValueError("source index row count does not match the encoded frame count")
    new_scene = apply(original)
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_out = output_dir / "scene.json"
    geometry_out = output_dir / "geometry.mp4"
    comparison_out = output_dir / "comparison.mp4"
    scene_out.write_text(json.dumps(new_scene, indent=2), encoding="utf-8")
    render(new_scene, geometry_out)
    pair_info = render_comparison(source_video, geometry_out, comparison_out)
    geometry_probe, comparison_probe = probe(geometry_out), probe(comparison_out)
    if not all(p["last_frame_decodes"] for p in (source_probe, geometry_probe, comparison_probe)):
        raise ValueError("source or output final frame did not decode")
    if any(p["frames"] != source_probe["frames"] for p in (geometry_probe, comparison_probe)):
        raise ValueError("rendered frame count differs from source")
    if any(abs(p["fps"] - source_probe["fps"]) > 1e-6 for p in (geometry_probe, comparison_probe)):
        raise ValueError("rendered FPS differs from source")
    if geometry_probe["size"] != source_probe["size"] or comparison_probe["size"] != [2 * source_probe["size"][0], source_probe["size"][1]]:
        raise ValueError("rendered dimensions differ from source/pairing contract")
    if sha256(source_video) != source_hash_before or (index and sha256(index) != index_hash_before):
        raise ValueError("source or index hash changed during processing")
    run_id = new_scene.get("source", {}).get("run_id", source_video.stem)
    manifest = {
        "schema": "geometry_scene_v2.visibility_revision.v1",
        "status": "AUTO_RECONSTRUCTED / PROVISIONAL / NOT_GROUND_TRUTH",
        "run_id": run_id,
        "source_scene": {"path": scene_path.as_posix(), "sha256": old_scene_hash},
        "source_video": {"path": source_video.as_posix(), "sha256_before": source_hash_before, **source_probe},
        "source_index": {"path": index.as_posix(), "sha256_before": index_hash_before} if index else None,
        "pipeline_sources": {
            name: {"path": (HERE / name).as_posix(), "sha256": sha256(HERE / name)}
            for name in ("apply_observation_visibility.py", "reconstruct_scene.py", "render_scene.py", "render_comparison.py")
        },
        "visibility_policy": new_scene["visibility_policy"],
        "outputs": {
            "scene": {"path": scene_out.name, "sha256": sha256(scene_out)},
            "geometry": {"path": geometry_out.name, "sha256": sha256(geometry_out), **geometry_probe},
            "comparison": {"path": comparison_out.name, "sha256": sha256(comparison_out), **comparison_probe, "pairing": pair_info["sync_basis"]},
        },
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path)
    parser.add_argument("source_mp4", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--index", type=Path, default=None)
    args = parser.parse_args()
    print(json.dumps(process(args.scene, args.source_mp4, args.output_dir, args.index), indent=2))


if __name__ == "__main__":
    main()
