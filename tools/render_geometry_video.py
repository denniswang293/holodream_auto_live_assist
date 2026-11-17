"""Render all or selected recordings as a clean, source-aligned geometry video."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import statistics
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.geometry_video.geometry import VideoGeometry
from src.geometry_video.renderer import render_geometry_frame
from src.geometry_video.segmenter import Candidate, PixelGeometryConverter


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ffmpeg_writer(path: Path, width: int, height: int, fps: float, crf: int) -> subprocess.Popen:
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pix_fmt", "bgr24", "-video_size", f"{width}x{height}", "-framerate", f"{fps:.9f}",
               "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(crf),
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)]
    return subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def candidate_dict(candidate: Candidate, frame_no: int, run_id: str, object_no: int) -> dict:
    def compact_spans(rows: list[list[int]]) -> dict:
        packed = struct.pack(f"<{len(rows)*3}H", *(value for row in rows for value in row)) if rows else b""
        return {"encoding": "zlib-u16le-triplets-v1", "run_count": len(rows),
                "data_base64": base64.b64encode(zlib.compress(packed, 1)).decode("ascii")}

    evidence = dict(candidate.pixel_evidence)
    evidence["mask_spans_rle"] = compact_spans(evidence.get("mask_spans_rle", []))
    parts = []
    for source_part in candidate.parts:
        part = dict(source_part)
        if candidate.class_name == "TAP":
            # Tap part and instance cover the same observed pixels; reference
            # the instance mask instead of serializing a second identical RLE.
            part.pop("mask_spans_rle", None)
            part["mask_ref"] = "pixel_evidence.mask_spans_rle"
        else:
            part["mask_spans_rle"] = compact_spans(part.get("mask_spans_rle", []))
        parts.append(part)
    return {
        "instance_id": f"{run_id}:f{frame_no:06d}:o{object_no:03d}",
        "frame_id": frame_no, "class": candidate.class_name, "color": candidate.color_name,
        "confidence": round(candidate.confidence, 4), "bbox": list(candidate.bbox),
        "polygon": candidate.polygon, "pixel_evidence": evidence,
        "parts": parts, "uncertainty_reasons": candidate.uncertainty_reasons,
        "provenance": "CURRENT_FRAME_SOURCE_PIXELS_ONLY",
    }


def save_inventory_markdown(items: list[dict], out: Path) -> None:
    lines = ["# Geometry Video V1 source inventory", "",
             "Generated from the currently preserved read-only `output/recording/`.",
             "All eight complete Runs share 1280x720, H.264, nominal 60fps, and indexed capture/acquired timestamps.",
             "Development set: first six chronological Runs. Holdout set: final two Runs, not used to fit pixel thresholds.", "",
             "| Run | Status | Frames | Duration | Index rows | CFR PTS | Capture monotonic | SHA-256 (source video) |",
             "|---|---|---:|---:|---:|---|---|---|"]
    for item in items:
        video, index = item.get("video", {}), item.get("index", {})
        lines.append(f"| `{item['run_id']}` | {item['availability']} | {video.get('nb_read_frames','')} | {video.get('duration','')} s | {index.get('rows','')} | {video.get('pts_cfr_within_1ms','')} | {index.get('capture_timestamp_strictly_increasing','')} | `{item.get('video_sha256','')}` |")
    lines += ["", "Every file in each Run directory (video, index, markers, player key events, session metadata) has a SHA-256 in `inventory.json`.",
              "Frame-level PTS values are retained in `inventory.json`; `frame_index.csv` maps exact source frame IDs to output frames and recorded capture/acquired times.",
              "Player key event CSVs are inventory-only. They are not note labels or geometry ground truth."]
    (out / "inventory.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


def render_blank_preview(geometry: VideoGeometry, out_root: Path, fps: float = 60.0,
                         seconds: float = 3.0, filename: str = "blank_geometry_preview.mp4") -> Path:
    """Write a short geometry-only clip; this path never decodes recordings."""
    if Path(filename).name != filename or not filename.lower().endswith(".mp4"):
        raise ValueError("Preview name must be a simple MP4 filename")
    path = out_root / filename
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing preview: {path}")
    frame_count = round(fps * seconds)
    writer = ffmpeg_writer(path, geometry.width, geometry.height, fps, 20)
    frame = render_geometry_frame(geometry, [])
    try:
        for _ in range(frame_count):
            if writer.poll() is not None:
                raise RuntimeError("ffmpeg encoder exited before the geometry preview was written")
            writer.stdin.write(frame.tobytes())
        writer.stdin.close()
        stderr = writer.stderr.read().decode("utf-8", errors="replace")
        code = writer.wait()
        if code:
            raise RuntimeError(f"ffmpeg failed ({code}): {stderr[-4000:]}")
    except Exception:
        if writer.poll() is None:
            writer.kill()
        writer.wait()
        path.unlink(missing_ok=True)
        raise
    return path


def run_render(run: dict, recording_root: Path, out_root: Path, geometry: VideoGeometry,
               geometry_config: Path, inventory_file: Path) -> dict:
    run_id = run["run_id"]
    source_dir = recording_root / run_id
    source_path = source_dir / "live_source.mp4"
    index_path = source_dir / "live_video_index.csv"
    dest = out_root / run_id
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing output directory: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    with index_path.open("r", newline="", encoding="utf-8-sig") as stream:
        index = list(csv.DictReader(stream))
    pts = run["video"].get("pts_time_values", [])
    if len(index) != int(run["video"].get("nb_read_frames", -1)) or len(pts) != len(index):
        raise ValueError(f"Source frame/index/PTS count mismatch for {run_id}")
    if not run["video"].get("pts_strictly_increasing") or not run["video"].get("pts_cfr_within_1ms"):
        raise ValueError(f"Non-monotonic or variable source PTS requires timestamp-aware output for {run_id}")
    fps = 1.0 / float(run["video"]["pts_median_interval_s"])
    converter = PixelGeometryConverter(geometry)
    source = cv2.VideoCapture(str(source_path))
    if not source.isOpened():
        raise RuntimeError(f"Cannot decode {source_path}")
    geom_path, comparison_path = dest/"geometry.mp4", dest/"comparison.mp4"
    geometry_writer = ffmpeg_writer(geom_path, geometry.width, geometry.height, fps, 23)
    compare_writer = ffmpeg_writer(comparison_path, geometry.width*2, geometry.height, fps, 28)
    frame_index_path = dest/"frame_index.csv"
    instances_path = dest/"instances.jsonl"
    uncertain_path = dest/"uncertain_candidates.csv"
    issue_path = dest/"issue_log.csv"
    counts = {"frames": 0, "tap_instances": 0, "hold_instances": 0,
              "uncertain_candidates": 0, "decode_failures": 0}
    capture_intervals = []
    segment_ms, render_ms, conversion_ms, composite_ms, frame_ms = [], [], [], [], []
    issue_counts: dict[str, int] = {}
    previous_capture = None
    with frame_index_path.open("w", newline="", encoding="utf-8") as fi, \
         instances_path.open("w", encoding="utf-8") as ji, \
         uncertain_path.open("w", newline="", encoding="utf-8") as ui, \
         issue_path.open("w", newline="", encoding="utf-8") as ii:
        fw = csv.DictWriter(fi, fieldnames=["output_frame", "source_video_frame", "source_frame",
                                            "source_pts_s", "output_pts_s", "pts_delta_s",
                                            "capture_timestamp", "acquired_timestamp"])
        fw.writeheader()
        uw = csv.DictWriter(ui, fieldnames=["run_id", "frame_id", "capture_timestamp", "instance_id",
                                             "candidate_class", "color", "confidence", "bbox",
                                             "pixel_count", "reasons", "polygon"])
        uw.writeheader()
        iw = csv.DictWriter(ii, fieldnames=["run_id", "frame_id", "source_pts_s", "capture_timestamp",
                                             "issue", "instance_id", "bbox", "confidence"])
        iw.writeheader()
        for frame_no in range(len(index)):
            ok, frame = source.read()
            if not ok:
                counts["decode_failures"] += 1
                break
            frame_start = time.perf_counter()
            stage_start = time.perf_counter()
            objects, uncertain = converter.segment(frame)
            segment_ms.append((time.perf_counter()-stage_start)*1000)
            stage_start = time.perf_counter()
            geo_frame = render_geometry_frame(geometry, objects)
            render_ms.append((time.perf_counter()-stage_start)*1000)
            if geometry_writer.poll() is not None or compare_writer.poll() is not None:
                raise RuntimeError("ffmpeg encoder exited before all frames were written")
            geometry_writer.stdin.write(geo_frame.tobytes())
            comparison = cv2.hconcat((frame, geo_frame))
            stage_start = time.perf_counter()
            compare_writer.stdin.write(comparison.tobytes())
            composite_ms.append((time.perf_counter()-stage_start)*1000)
            row = index[frame_no]
            capture_time = float(row["capture_timestamp"])
            output_pts = frame_no / fps
            source_pts = float(pts[frame_no])
            # The source uses a zero-based CFR PTS clock; retain exact values
            # separately so timing truth never falls back to frame/fps.
            fw.writerow({"output_frame": frame_no, "source_video_frame": row["video_frame"],
                         "source_frame": row["source_frame"], "source_pts_s": f"{source_pts:.9f}",
                         "output_pts_s": f"{output_pts:.9f}",
                         "pts_delta_s": f"{output_pts-(source_pts-float(pts[0])):.9f}",
                         "capture_timestamp": row["capture_timestamp"], "acquired_timestamp": row["acquired_timestamp"]})
            if previous_capture is not None:
                capture_intervals.append(capture_time-previous_capture)
            previous_capture = capture_time
            all_objects = [candidate_dict(c, frame_no, run_id, n) for n,c in enumerate(objects)]
            all_uncertain = [candidate_dict(c, frame_no, run_id, n+len(objects)) for n,c in enumerate(uncertain)]
            stage_start = time.perf_counter()
            ji.write(json.dumps({"run_id": run_id, "frame_id": frame_no,
                                 "source_pts_s": source_pts, "capture_timestamp": capture_time,
                                 "acquired_timestamp": float(row["acquired_timestamp"]),
                                 "instances": all_objects, "uncertain_candidates": all_uncertain}, separators=(",", ":"))+"\n")
            conversion_ms.append((time.perf_counter()-stage_start)*1000)
            for candidate in all_uncertain:
                uw.writerow({"run_id": run_id, "frame_id": frame_no, "capture_timestamp": capture_time,
                             "instance_id": candidate["instance_id"], "candidate_class": candidate["class"],
                             "color": candidate["color"], "confidence": candidate["confidence"],
                             "bbox": json.dumps(candidate["bbox"]),
                             "pixel_count": candidate["pixel_evidence"]["mask_pixel_count"],
                             "reasons": "|".join(candidate["uncertainty_reasons"]),
                             "polygon": json.dumps(candidate["polygon"], separators=(",", ":"))})
                reasons = candidate["uncertainty_reasons"] or ["unspecified_uncertainty"]
                for reason in reasons:
                    issue_counts[reason] = issue_counts.get(reason, 0) + 1
                    iw.writerow({"run_id": run_id, "frame_id": frame_no, "source_pts_s": f"{source_pts:.9f}",
                                 "capture_timestamp": row["capture_timestamp"], "issue": reason,
                                 "instance_id": candidate["instance_id"],
                                 "bbox": json.dumps(candidate["bbox"]), "confidence": candidate["confidence"]})
            counts["frames"] += 1
            counts["tap_instances"] += sum(c.class_name == "TAP" for c in objects)
            counts["hold_instances"] += sum(c.class_name == "HOLD" for c in objects)
            counts["uncertain_candidates"] += len(uncertain)
            frame_ms.append((time.perf_counter()-frame_start)*1000)
            if frame_no % 300 == 0:
                print(f"{run_id}: {frame_no}/{len(index)} frames; tap={counts['tap_instances']} hold={counts['hold_instances']} uncertain={counts['uncertain_candidates']}", flush=True)
        source.release()
    encode_flush_ms = []
    for writer in (geometry_writer, compare_writer):
        try:
            writer.stdin.close()
        except Exception:
            pass
        encode_start = time.perf_counter()
        stderr = writer.stderr.read().decode("utf-8", errors="replace")
        code = writer.wait()
        encode_flush_ms.append((time.perf_counter()-encode_start)*1000)
        if code:
            raise RuntimeError(f"ffmpeg failed ({code}): {stderr[-4000:]}")
    if counts["frames"] != len(index) or counts["decode_failures"]:
        raise RuntimeError(f"Incomplete source decode for {run_id}: {counts}")
    source_sha_now = file_sha256(source_path)
    if source_sha_now != run["video_sha256"]:
        raise RuntimeError(f"Source video changed during processing: {run_id}")
    rate = float(run["video"]["pts_median_interval_s"])
    pts_deltas = [float(frame_no/fps-(pts[frame_no]-pts[0])) for frame_no in range(len(pts))]
    qc = {
        "run_id": run_id, "status": "PROVISIONAL_PIXEL_CONVERSION",
        **counts, "source_sha256": source_sha_now, "index_sha256": run["index_sha256"],
        "geometry_config_sha256": file_sha256(geometry_config),
        "inventory_sha256": file_sha256(inventory_file), "source_codec": run["video"]["codec_name"],
        "source_fps": fps, "source_frame_count": len(index), "index_frame_count": len(index),
        "source_pts_monotonic": run["video"]["pts_strictly_increasing"],
        "source_pts_cfr_within_1ms": run["video"]["pts_cfr_within_1ms"],
        "max_abs_pts_mapping_error_s": max(map(abs, pts_deltas), default=0),
        "capture_interval_median_s": float(np.median(capture_intervals)) if capture_intervals else None,
        "capture_interval_p99_s": float(np.percentile(capture_intervals, 99)) if capture_intervals else None,
        "processing_ms": {"segmenter_median": statistics.median(segment_ms),
                          "segmenter_p95": float(np.percentile(segment_ms, 95)),
                          "geometry_render_median": statistics.median(render_ms),
                          "geometry_render_p95": float(np.percentile(render_ms, 95)),
                          "data_conversion_write_median": statistics.median(conversion_ms),
                          "data_conversion_write_p95": float(np.percentile(conversion_ms, 95)),
                          "comparison_pipe_write_median": statistics.median(composite_ms),
                          "comparison_pipe_write_p95": float(np.percentile(composite_ms, 95)),
                          "frame_loop_median": statistics.median(frame_ms),
                          "frame_loop_p95": float(np.percentile(frame_ms, 95)),
                          "encoder_close_flush_total_ms": sum(encode_flush_ms)},
        "uncertainty_reason_counts": issue_counts,
        "physical_note_precision_recall": "NOT_EVALUABLE_NO_INDEPENDENT_HUMAN_LABELS",
        "visual_review": "AUTO_VISUAL_REVIEWED_PROVISIONAL",
        "unresolved_hold_head_tail_ownership": "REVIEW_REQUIRED",
    }
    (dest/"qc_summary.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")
    checksums = {name: file_sha256(dest/name) for name in
                 ("geometry.mp4", "comparison.mp4", "frame_index.csv", "instances.jsonl", "uncertain_candidates.csv", "issue_log.csv", "qc_summary.json")}
    checksums.update({"source_video_sha256": source_sha_now, "source_index_sha256": run["index_sha256"],
                      "geometry_config_sha256": file_sha256(geometry_config)})
    (dest/"checksums.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")
    return qc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1"))
    parser.add_argument("--geometry", type=Path, default=Path("config/geometry_video_v1.json"))
    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--preview-name", default="blank_geometry_preview.mp4",
                        help="Preview MP4 basename; use a new name to preserve an earlier preview")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="render every available indexed source Run")
    group.add_argument("--preview", action="store_true", help="render a short blank geometry-only preview; does not decode source Runs")
    group.add_argument("--inventory", action="store_true", help="refresh read-only inventory and exit")
    args = parser.parse_args()
    if args.inventory:
        inv = subprocess.run([sys.executable, str(ROOT/"tools/inventory_geometry_video.py"),
                              "--input-root", str(args.input_root), "--out", str(args.out)], check=False)
        return inv.returncode
    inventory_path = args.out/"inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    available = [row for row in inventory if row.get("availability") == "AVAILABLE"]
    if args.run:
        selected = [row for row in available if row["run_id"] in args.run]
        missing = set(args.run)-{row["run_id"] for row in selected}
        if missing:
            raise SystemExit(f"Unknown or unavailable Runs: {sorted(missing)}")
    elif args.all:
        selected = available
    else:
        selected = available[:1]
    if args.all and len(selected) != len(available):
        raise SystemExit("--all requires every available Run selected")
    geometry = VideoGeometry(args.geometry)
    cfg_hash_before = file_sha256(args.geometry)
    source_cfg_hash = file_sha256(ROOT/"config/geometry_live_assist.json")
    (args.out/"config_snapshot.json").write_text(json.dumps({
        "geometry_video_config": geometry.document, "geometry_video_sha256": cfg_hash_before,
        "live_geometry_config_sha256_read_only": source_cfg_hash,
        "source_note_timing_calibration_modified": False,
    }, indent=2), encoding="utf-8")
    save_inventory_markdown(inventory, args.out)
    if args.preview:
        path = render_blank_preview(geometry, args.out, filename=args.preview_name)
        print(json.dumps({"preview": str(path), "duration_s": 3.0, "fps": 60,
                          "source_recordings_decoded": False}, indent=2))
        return 0
    results = []
    for row in selected:
        results.append(run_render(row, args.input_root, args.out, geometry, args.geometry, inventory_path))
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
