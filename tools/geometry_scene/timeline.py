"""Scene JSON + per-frame time index to timestamp-aligned pure geometry MP4."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import time
from pathlib import Path

from .renderer import render_scene_frame
from .scene_io import load_scene
from .video import VFRVideoWriter


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_timeline(scene_path: Path, frame_index_path: Path, run_id: str,
                    output_path: Path) -> dict:
    scene = load_scene(scene_path)
    if scene.run_id not in (run_id, "synthetic", "unknown"):
        raise ValueError(f"scene run_id {scene.run_id!r} does not match {run_id!r}")
    with frame_index_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["run_id"] == run_id]
    if not rows:
        raise ValueError(f"no timeline rows for {run_id}")
    rows.sort(key=lambda r: int(r["video_frame"]))
    if [int(r["video_frame"]) for r in rows] != list(range(len(rows))):
        raise ValueError("source frame index is missing, duplicated, or out of order")
    times = [float(r["acquired_elapsed_seconds"]) for r in rows]
    if times[0] != 0 or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("acquired timestamp timeline must start at 0 and increase strictly")
    final_duration = times[-1] - times[-2] if len(times) > 1 else 1 / 25
    render_ms: list[float] = []
    encode_ms: list[float] = []
    frame_mapping = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with VFRVideoWriter(output_path, scene.width, scene.height, final_duration) as writer:
        for i, (row, t) in enumerate(zip(rows, times)):
            start = time.perf_counter()
            image = render_scene_frame(scene, t)
            render_ms.append((time.perf_counter() - start) * 1000)
            start = time.perf_counter()
            output_pts = writer.write(image, t)
            encode_ms.append((time.perf_counter() - start) * 1000)
            frame_mapping.append({
                "run_id": run_id, "output_frame": i, "source_video_frame": int(row["video_frame"]),
                "source_frame": row["source_frame"], "source_mp4_pts_seconds": row["source_pts_seconds"],
                "capture_timestamp": row["capture_timestamp"], "acquired_timestamp": row["acquired_timestamp"],
                "scene_time_seconds": t, "geometry_output_pts_90k": output_pts,
                "geometry_output_pts_seconds": output_pts / 90_000,
                "timestamp_quantization_error_seconds": output_pts / 90_000 - t,
                "mapping_status": "EXACT_SOURCE_INDEX_FRAME",
            })
    mapping_path = output_path.with_name("geometry_frame_index.csv")
    with mapping_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(frame_mapping[0])); writer.writeheader(); writer.writerows(frame_mapping)
    pts_errors = [abs(r["timestamp_quantization_error_seconds"]) for r in frame_mapping]
    summary = {
        "run_id": run_id, "scene_sha256": file_sha256(scene_path),
        "source_frame_index_sha256": file_sha256(frame_index_path),
        "geometry_video_sha256": file_sha256(output_path), "frame_index_sha256": file_sha256(mapping_path),
        "frames": len(rows), "notes_in_scene": len(scene.notes),
        "rendered_typed_tracks": sum(n.kind != "UNKNOWN" for n in scene.notes),
        "render_time_ms": {"mean": statistics.fmean(render_ms), "p50": statistics.median(render_ms),
                           "p95": sorted(render_ms)[int(.95 * (len(render_ms)-1))], "max": max(render_ms)},
        "video_encode_write_ms": {"mean": statistics.fmean(encode_ms), "p50": statistics.median(encode_ms),
                                  "p95": sorted(encode_ms)[int(.95 * (len(encode_ms)-1))], "max": max(encode_ms)},
        "timestamp_error_seconds": {"max_abs": max(pts_errors), "p95_abs": sorted(pts_errors)[int(.95*(len(pts_errors)-1))]},
        "timeline": "INDEX_ACQUIRED_TIMESTAMP_VFR_PTS_1_90000",
        "renderer_input_boundary": "SCENE_JSON_AND_FRAME_INDEX_ONLY",
    }
    summary_path = output_path.with_name("geometry_render_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
