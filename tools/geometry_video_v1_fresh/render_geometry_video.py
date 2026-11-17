from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.geometry_rebuild_v1.geometry import Geometry
from src.geometry_rebuild_v1.render import blank_geometry, geometry_frame
from src.geometry_rebuild_v1.segment import Candidate, detect_candidates
from tools.geometry_v1_fresh.inventory import inventory_recordings, write_inventory


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_no_overwrite(path: Path, data: dict) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def source_pts(video: Path) -> list[float]:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
               "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(video)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return [float(row["best_effort_timestamp_time"]) for row in data.get("frames", [])]


def index_rows(path: Path) -> list[dict]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    x1, y1 = max(ax, bx), max(ay, by)
    x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


class LocalIdentity:
    """Causal source-space association; never predicts or draws hidden pixels."""

    def __init__(self) -> None:
        self.next_id = 1
        self.active: list[dict] = []

    def assign(self, candidates: list[Candidate], frame_index: int) -> list[str]:
        self.active = [t for t in self.active if frame_index - t["last_frame"] <= 5]
        pairs = []
        for ci, c in enumerate(candidates):
            x, y, w, h = c.bbox; cx, cy = x + w / 2, y + h / 2
            for ti, track in enumerate(self.active):
                if track["color"] != c.color:
                    continue
                tx, ty, tw, th = track["bbox"]; tcx, tcy = tx + tw / 2, ty + th / 2
                dist = math.hypot(cx - tcx, cy - tcy)
                iou = _bbox_iou(c.bbox, track["bbox"])
                if iou >= .03 or dist <= max(20, .45 * max(h, th)):
                    pairs.append((dist - iou * 20, ci, ti))
        matched_c, matched_t, result = set(), set(), [None] * len(candidates)
        for _, ci, ti in sorted(pairs):
            if ci in matched_c or ti in matched_t:
                continue
            result[ci] = self.active[ti]["id"]
            matched_c.add(ci); matched_t.add(ti)
        for ci, c in enumerate(candidates):
            if result[ci] is None:
                result[ci] = f"note-{self.next_id:06d}"; self.next_id += 1
                self.active.append({"id": result[ci], "bbox": c.bbox, "color": c.color,
                                    "last_frame": frame_index})
            else:
                tid = result[ci]
                for track in self.active:
                    if track["id"] == tid:
                        track.update(bbox=c.bbox, last_frame=frame_index)
                        break
        return result


def independent_horizontal_audit(frame: np.ndarray, geometry: Geometry,
                                 candidates: list[Candidate]) -> list[dict]:
    # Independent grayscale horizontal-edge scan, not the HSV candidate mask.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 65, 160)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=25,
                            minLineLength=16, maxLineGap=2)
    rows = []
    if lines is None:
        return rows
    for x1, y1, x2, y2 in lines[:, 0, :]:
        if abs(int(y2) - int(y1)) > 2 or abs(int(x2) - int(x1)) < 15:
            continue
        y = (int(y1) + int(y2)) // 2
        if y > geometry.judgment_band[1] + 45:
            continue
        x = min(int(x1), int(x2)); w = abs(int(x2) - int(x1)) + 1
        if x + w < geometry.rails[0].x(y) or x > geometry.rails[-1].x(y):
            continue
        bbox = (x, y - 2, w, 5)
        best_iou = 0.0; best_type = "NONE"
        for c in candidates:
            overlap = _bbox_iou(bbox, c.bbox)
            if overlap > best_iou:
                best_iou, best_type = overlap, c.candidate_type
        rows.append({"bbox": [x, y - 2, w, 5], "line_length_px": w,
                     "best_candidate_iou": round(best_iou, 4),
                     "best_candidate_type": best_type,
                     "status": "overlaps_candidate" if best_iou >= .06 else "independent_unmatched_horizontal_evidence"})
    return rows


def _quantiles(values: list[float]) -> dict:
    if not values:
        return {"median_ms": None, "p95_ms": None, "max_ms": None}
    return {"median_ms": round(float(np.median(values)), 3),
            "p95_ms": round(float(np.percentile(values, 95)), 3),
            "max_ms": round(float(np.max(values)), 3)}


def render_run(run_dir: Path, out_root: Path, geometry: Geometry,
               fps: float, max_frames: int | None = None,
               start_frame: int = 0) -> dict:
    run_id = run_dir.name
    target = out_root / run_id
    if target.exists():
        raise FileExistsError(f"refusing to overwrite run output {target}")
    target.mkdir(parents=True)
    video, index = run_dir / "live_source.mp4", run_dir / "live_video_index.csv"
    rows = index_rows(index)
    pts = source_pts(video)
    if len(rows) != len(pts):
        raise ValueError(f"source PTS/index mismatch {run_id}: {len(pts)} vs {len(rows)}")
    if start_frame < 0 or start_frame >= len(rows):
        raise ValueError(f"start frame out of range for {run_id}: {start_frame}")
    available = len(rows) - start_frame
    expected = min(available, max_frames) if max_frames else available
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot decode {video}")
    if start_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if (width, height) != (geometry.width, geometry.height):
        raise ValueError(f"unexpected dimensions {width}x{height} in {run_id}")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    geom_path, comp_path = target / "geometry.mp4", target / "comparison.mp4"
    writer = cv2.VideoWriter(str(geom_path), fourcc, fps, (width, height))
    comparison_writer = cv2.VideoWriter(str(comp_path), fourcc, fps, (width * 2, height))
    if not writer.isOpened() or not comparison_writer.isOpened():
        cap.release(); writer.release(); comparison_writer.release()
        raise RuntimeError("OpenCV mp4v writer could not be opened")

    frame_index_path = target / "frame_index.csv"
    instance_path = target / "instances.jsonl"
    uncertain_path = target / "uncertain_candidates.csv"
    audit_path = target / "independent_horizontal_audit.csv"
    stage_ms = {"decode": [], "segment_and_pixel_evidence": [], "geometry_render": [],
                "comparison_compose_and_encode": [], "serialization": []}
    type_counts = {"TAP": 0, "HOLD": 0, "UNKNOWN": 0}
    reason_counts: dict[str, int] = {}
    total_audit, unmatched_audit = 0, 0
    background_components_rejected = 0
    windows: dict[int, tuple[int, np.ndarray, np.ndarray, int]] = {}
    identity = LocalIdentity()
    with frame_index_path.open("w", newline="", encoding="utf-8") as index_f, \
         instance_path.open("w", encoding="utf-8") as inst_f, \
         uncertain_path.open("w", newline="", encoding="utf-8") as unc_f, \
         audit_path.open("w", newline="", encoding="utf-8") as audit_f:
        index_fields = ["output_frame", "source_frame", "video_pts_s", "capture_timestamp",
                        "acquired_timestamp", "elapsed_s", "encoded_at_host", "frame_join"]
        index_writer = csv.DictWriter(index_f, fieldnames=index_fields); index_writer.writeheader()
        unc_fields = ["frame", "source_frame", "capture_timestamp", "bbox", "color", "confidence", "reason", "pixel_area", "mask_shape"]
        unc_writer = csv.DictWriter(unc_f, fieldnames=unc_fields); unc_writer.writeheader()
        audit_fields = ["frame", "source_frame", "capture_timestamp", "bbox", "line_length_px", "best_candidate_iou", "best_candidate_type", "status"]
        audit_writer = csv.DictWriter(audit_f, fieldnames=audit_fields); audit_writer.writeheader()
        for i in range(expected):
            t0 = time.perf_counter_ns(); ok, source = cap.read(); t1 = time.perf_counter_ns()
            if not ok:
                raise RuntimeError(f"decode stopped at frame {i}/{expected} in {run_id}")
            source_i = start_frame + i
            idx = rows[source_i]
            seg0 = time.perf_counter_ns()
            candidates, uncertain, detector_diag = detect_candidates(source, geometry, source_i)
            background_components_rejected += detector_diag["scene_background_components_rejected"]
            ids = identity.assign(candidates, source_i)
            seg1 = time.perf_counter_ns()
            render0 = time.perf_counter_ns(); geometric = geometry_frame(geometry, candidates); render1 = time.perf_counter_ns()
            geom_write0 = time.perf_counter_ns(); writer.write(geometric)
            comparison_writer.write(np.hstack((source, geometric))); geom_write1 = time.perf_counter_ns()

            obj = {"run_id": run_id, "frame": source_i, "source_frame": int(float(idx["source_frame"])),
                   "video_pts_s": pts[source_i], "capture_timestamp": float(idx["capture_timestamp"]),
                   "acquired_timestamp": float(idx["acquired_timestamp"]),
                   "timestamp_policy": "SOURCE_VIDEO_PTS_FOR_MP4; INDEX_CAPTURE_AND_ACQUIRED_PRESERVED",
                   "offline_mode": "CURRENT_FRAME_CAUSAL; NO_FUTURE_FRAMES",
                   "candidates": []}
            for ci, candidate in enumerate(candidates):
                type_counts[candidate.candidate_type] += 1
                if candidate.reason:
                    reason = candidate.reason or "unknown"
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1
                item = candidate.to_dict(); item["candidate_id"] = f"{run_id}:{i}:{ci:04d}"
                item["track_id"] = ids[ci]
                obj["candidates"].append(item)
            ser0 = time.perf_counter_ns(); inst_f.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n")
            index_writer.writerow({"output_frame": i, "source_frame": idx["source_frame"],
                                   "video_pts_s": pts[source_i], "capture_timestamp": idx["capture_timestamp"],
                                   "acquired_timestamp": idx["acquired_timestamp"], "elapsed_s": idx["elapsed_s"],
                                   "encoded_at_host": idx["encoded_at_host"], "frame_join": "EXACT_SOURCE_FRAME_INDEX"})
            for u in uncertain:
                unc_writer.writerow({"frame": i, "source_frame": idx["source_frame"],
                                     "capture_timestamp": idx["capture_timestamp"],
                                     "bbox": json.dumps(u["bbox"]), "color": u["color"],
                                     "confidence": u["confidence"], "reason": u["reason"],
                                     "pixel_area": u["pixel_area"], "mask_shape": json.dumps(u["mask_shape"])})
            if i % 30 == 0:
                audits = independent_horizontal_audit(source, geometry, candidates)
                for a in audits:
                    audit_writer.writerow({"frame": source_i, "source_frame": idx["source_frame"],
                                           "capture_timestamp": idx["capture_timestamp"],
                                           "bbox": json.dumps(a["bbox"]), **{k: a[k] for k in audit_fields[4:]}})
                    total_audit += 1
                    if a["status"] == "independent_unmatched_horizontal_evidence": unmatched_audit += 1
            ser1 = time.perf_counter_ns()
            stage_ms["decode"].append((t1 - t0) / 1e6)
            stage_ms["segment_and_pixel_evidence"].append((seg1 - seg0) / 1e6)
            stage_ms["geometry_render"].append((render1 - render0) / 1e6)
            stage_ms["comparison_compose_and_encode"].append((geom_write1 - geom_write0) / 1e6)
            stage_ms["serialization"].append((ser1 - ser0) / 1e6)

            window = min(5, (i * 6) // max(expected, 1))
            score = len(uncertain) + max(0, len(audits) - len(candidates))
            prev = windows.get(window)
            if prev is None or score > prev[3]:
                windows[window] = (i, source.copy(), geometric.copy(), score)
            if i in {0, expected // 2, expected - 1}:
                windows[10 + i] = (i, source.copy(), geometric.copy(), -1)
        cap.release(); writer.release(); comparison_writer.release()

    review_dir = target / "review_windows"; review_dir.mkdir()
    for i, source, geometric, score in windows.values():
        canvas = np.hstack((source, geometric))
        cv2.imwrite(str(review_dir / f"frame_{i:06d}_source_geometry.png"), canvas)
        if score >= 0:
            cv2.imwrite(str(review_dir / f"frame_{i:06d}_source.png"), source)
    unc_count = sum(1 for _ in uncertain_path.open("r", encoding="utf-8")) - 1
    source_duration_pts = pts[start_frame + expected - 1] - pts[start_frame] if expected else 0.0
    timestamp_duration = float(rows[start_frame + expected - 1]["capture_timestamp"]) - float(rows[start_frame]["capture_timestamp"]) if expected else 0.0
    qc = {"run_id": run_id, "frames": expected, "source_frames": len(rows), "source_pts_frames": len(pts),
          "status": "PROVISIONAL_PIXEL_TO_GEOMETRY", "type_counts": type_counts,
          "uncertain_rows": unc_count, "uncertainty_reasons": reason_counts,
          "scene_background_components_rejected": background_components_rejected,
          "independent_horizontal_audit": {"sample_every_n_frames": 30, "horizontal_edge_candidates": total_audit,
                                            "unmatched_candidates": unmatched_audit,
                                            "interpretation": "review_queue_only_not_ground_truth"},
          "processing_ms": {k: _quantiles(v) for k, v in stage_ms.items()},
          "media_timeline": {"mp4_fps": fps, "source_pts_duration_s": source_duration_pts,
                             "capture_timestamp_span_s": timestamp_duration,
                             "warning": "MP4 reproduces source frame PTS cadence; capture/acquired timestamps are separately preserved in frame_index.csv."},
          "physical_note_precision_recall": "NOT_EVALUABLE_NO_INDEPENDENT_HUMAN_LABELS",
          "visual_review": "AUTO_VISUAL_REVIEWED_PROVISIONAL",
          "keyboard_or_scheduler_used": False}
    qc_path = target / "qc_summary.json"; json_no_overwrite(qc_path, qc)
    calibration_path = out_root / "calibration_geometry.json"
    manifest = {"schema": "fresh-geometry-v1-run-manifest-1", "run_id": run_id,
                "source_video": str(video.as_posix()), "source_index": str(index.as_posix()),
                "source_video_sha256": sha256(video), "source_index_sha256": sha256(index),
                "calibration_sha256": sha256(calibration_path), "source_frame_count": len(rows),
                "output_frame_count": expected, "source_start_frame": start_frame,
                "source_pts_sha256": hashlib.sha256(json.dumps(pts[start_frame:start_frame+expected]).encode()).hexdigest(),
                "frame_join": "EXACT_SOURCE_FRAME_INDEX", "frame_timeline": "source video PTS; capture/acquired timestamps in frame_index.csv",
                "offline_mode": "CURRENT_FRAME_CAUSAL", "future_frames_used": False}
    json_no_overwrite(target / "manifest.json", manifest)
    files = [p for p in target.rglob("*") if p.is_file() and p.name != "checksums.json"]
    hashes = {str(p.relative_to(target).as_posix()): sha256(p) for p in files}
    json_no_overwrite(target / "checksums.json", {"files": hashes})
    return qc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fresh, offline-only Geometry V1 render pipeline")
    parser.add_argument("--input-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1/fresh_20261117"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inventory", action="store_true")
    group.add_argument("--preview", action="store_true")
    group.add_argument("--run", metavar="RUN_ID")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--max-frames", type=int, help="synthetic/development quick check only")
    parser.add_argument("--start-frame", type=int, default=0, help="start source frame for a bounded review window")
    args = parser.parse_args(argv)
    out = args.out.resolve(); input_root = args.input_root.resolve(strict=True)
    if args.inventory:
        path = out / "source_inventory"
        rows = inventory_recordings(input_root)
        for p in write_inventory(rows, path): print(p)
        return 0
    geometry_path = out / "calibration_geometry.json"
    if not geometry_path.is_file():
        raise SystemExit("run source geometry calibration first")
    geometry = Geometry.from_dict(json.loads(geometry_path.read_text(encoding="utf-8")))
    if args.preview:
        path = out / "blank_geometry_preview.mp4"
        if path.exists(): raise SystemExit(f"refusing to overwrite {path}")
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 60.0,
                                 (geometry.width, geometry.height))
        frame = blank_geometry(geometry)
        for _ in range(180): writer.write(frame)
        writer.release(); print(path); return 0
    if args.run:
        ids = [args.run]
    else:
        ids = sorted(p.name for p in input_root.glob("run_*") if (p / "live_source.mp4").is_file())
    inventory_json = out / "source_inventory" / "inventory.json"
    if inventory_json.is_file():
        inventory_rows = json.loads(inventory_json.read_text(encoding="utf-8-sig"))["runs"]
    else:
        inventory_rows = inventory_recordings(input_root)
    meta = {row["run"]: row for row in inventory_rows}
    summaries = []
    for run_id in ids:
        if run_id not in meta:
            raise SystemExit(f"unavailable source run: {run_id}")
        source_dir = input_root / run_id
        if sha256(source_dir / "live_source.mp4") != meta[run_id]["video_sha256"]:
            raise SystemExit(f"source video changed since fresh inventory: {run_id}")
        if sha256(source_dir / "live_video_index.csv") != meta[run_id]["index_sha256"]:
            raise SystemExit(f"source index changed since fresh inventory: {run_id}")
        fps_text = meta[run_id]["average_fps"]
        numerator, denominator = fps_text.split("/")
        fps = float(numerator) / max(float(denominator), 1.0)
        summary = render_run(input_root / run_id, out, geometry, fps, args.max_frames, args.start_frame)
        summaries.append(summary)
        print(json.dumps({"run": run_id, "frames": summary["frames"], "types": summary["type_counts"],
                          "segment_median_ms": summary["processing_ms"]["segment_and_pixel_evidence"]["median_ms"]},
                         ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
