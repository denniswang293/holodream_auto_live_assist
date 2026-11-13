"""Offline causal V8.4 lane-filter review renderer (never opens an actuator)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lane_filter import CHANNELS, LaneFilter  # noqa: E402
from src.model import Geometry  # noqa: E402


def read_index(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {int(r.get("video_frame", r.get("encoded_frame", -1))): r
                for r in csv.DictReader(f) if r.get("video_frame", r.get("encoded_frame", "")).isdigit()}


def run(run_dir: Path, out_root: Path, limit: int | None = None) -> Path:
    run_dir = run_dir.resolve()
    source = run_dir / "live_source.mp4"
    index_path = run_dir / "live_video_index.csv"
    if not source.is_file() or not index_path.is_file():
        raise FileNotFoundError(f"need live_source.mp4 and live_video_index.csv in {run_dir}")
    index = read_index(index_path)
    run_id = run_dir.name
    out = out_root.resolve() / run_id
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    geometry = Geometry(ROOT / "config/geometry_live_assist.json")
    lane_filter = LaneFilter(geometry)
    observations_path = out / "observations.csv"
    summary_path = out / "frame_summary.csv"
    video_path = out / "filtered_video.mp4"
    side_path = out / "side_by_side.mp4"
    obs_fields = list(__import__('dataclasses').fields(__import__('src.lane_filter', fromlist=['LaneObservation']).LaneObservation))
    obs_names = [f.name for f in obs_fields]
    raw_writer = None
    filtered_writer = side_writer = None
    mask_frames: list[np.ndarray] = []
    frame_rows = []
    counts = {c: 0 for c in CHANNELS}
    missing_index = 0
    decoded = 0
    cpu_times: list[float] = []
    last_capture = None
    reversals = 0
    try:
        with observations_path.open("w", newline="", encoding="utf-8") as fo, summary_path.open("w", newline="", encoding="utf-8") as fs:
            ow = csv.DictWriter(fo, fieldnames=obs_names); ow.writeheader()
            sw = csv.DictWriter(fs, fieldnames=["video_frame", "source_frame", "capture_timestamp", "acquired_timestamp", "index_present", "observation_count", "roles", "cpu_ms"]); sw.writeheader()
            while limit is None or decoded < limit:
                ok, frame = cap.read()
                if not ok: break
                t0 = time.perf_counter()
                idx = index.get(decoded)
                if idx is None:
                    missing_index += 1
                    capture_at = acquired_at = None
                    source_frame = decoded
                else:
                    capture_at = float(idx.get("capture_timestamp", idx.get("captured_at", "nan")))
                    acquired_at = float(idx.get("acquired_timestamp", idx.get("acquired_at", "nan")))
                    source_frame = int(idx.get("source_frame", decoded))
                    if last_capture is not None and capture_at < last_capture: reversals += 1
                    last_capture = capture_at
                normalized = geometry.normalize(frame)
                if capture_at is not None and np.isfinite(capture_at) and np.isfinite(acquired_at) and acquired_at >= capture_at:
                    observations, masks, canvas = lane_filter.process(frame, run_id=run_id,
                        source_frame=source_frame, video_frame=decoded,
                        captured_at=capture_at, acquired_at=acquired_at)
                else:
                    observations, masks, canvas = [], {c: np.zeros((geometry.height, geometry.plane_width), np.uint8) for c in CHANNELS}, np.zeros((geometry.height, geometry.plane_width, 3), np.uint8)
                for item in observations:
                    ow.writerow(item.csv_row()); counts[item.mask_ref] = counts.get(item.mask_ref, 0) + 1
                # Render lane edges and the configured judgment line in clean, fixed colors.
                for x in range(7):
                    pts = []
                    for yy in np.linspace(geometry.top_y, geometry.hit_y, 24):
                        bx = geometry.boundaries(yy)[x] * geometry.plane_width / geometry.width
                        pts.append((int(round(bx)), int(round(yy))))
                    cv2.polylines(canvas, [np.asarray(pts, np.int32)], False, (90, 90, 90), 1)
                hy = int(round(geometry.hit_y)); cv2.line(canvas, (0, hy), (geometry.plane_width - 1, hy), (0, 230, 255), 2)
                small = canvas
                if filtered_writer is None:
                    filtered_writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (small.shape[1], small.shape[0]))
                    side_writer = cv2.VideoWriter(str(side_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (normalized.shape[1] * 2, normalized.shape[0]))
                filtered_writer.write(small)
                right = cv2.resize(small, (normalized.shape[1], normalized.shape[0]), interpolation=cv2.INTER_NEAREST)
                side_writer.write(np.concatenate((normalized, right), axis=1))
                packed = np.stack([masks[c] for c in CHANNELS], axis=0)
                mask_frames.append(packed)
                elapsed = (time.perf_counter() - t0) * 1000; cpu_times.append(elapsed)
                roles = "|".join(sorted({o.role for o in observations}))
                sw.writerow({"video_frame": decoded, "source_frame": source_frame,
                    "capture_timestamp": "" if capture_at is None else capture_at,
                    "acquired_timestamp": "" if acquired_at is None else acquired_at,
                    "index_present": bool(idx), "observation_count": len(observations), "roles": roles, "cpu_ms": f"{elapsed:.3f}"})
                frame_rows.append({"video_frame": decoded, "source_frame": source_frame,
                    "capture_timestamp": capture_at, "acquired_timestamp": acquired_at,
                    "observation_count": len(observations), "roles": roles, "cpu_ms": elapsed})
                decoded += 1
    finally:
        cap.release()
        if filtered_writer: filtered_writer.release()
        if side_writer: side_writer.release()
    if mask_frames:
        np.savez_compressed(out / "masks.npz", channel_names=np.asarray(CHANNELS), masks=np.stack(mask_frames))
    # Select notable review frames by evidence types and sample across observed detections.
    review = out / "review_frames"; review.mkdir(exist_ok=True)
    for stale in review.glob("frame_*.png"):
        stale.unlink()
    observed = sorted({r["video_frame"] for r in frame_rows if r["observation_count"]})
    selected = sorted({observed[round(i * (len(observed) - 1) / 11)]
                       for i in range(min(12, len(observed)))} if observed else set())
    if selected:
        cap = cv2.VideoCapture(str(video_path))
        for n in selected:
            cap.set(cv2.CAP_PROP_POS_FRAMES, n); ok, image = cap.read()
            if ok: cv2.imwrite(str(review / f"frame_{n:06d}.png"), image)
        cap.release()
    elapsed_s = sum(cpu_times) / 1000
    manifest = {"run_id": run_id, "source_video": str(source), "source_index": str(index_path),
        "mode": "filtered", "partial": limit is not None and decoded >= limit,
        "limit_frames": limit, "decoded_frames": decoded, "index_rows": len(index),
        "missing_index_rows": missing_index, "capture_timestamp_reversals": reversals,
        "preview_fps_only": fps, "all_measurement_timing_uses_index_capture_timestamp": True,
        "geometry_status": geometry.status, "geometry_sha256": geometry.sha256,
        "candidate_is_legacy_perception_adapter_unverified": True,
        "observations": sum(counts.values()), "role_counts": counts,
        "cpu_ms_per_frame_mean": float(np.mean(cpu_times)) if cpu_times else None,
        "cpu_ms_per_frame_p50": float(np.percentile(cpu_times, 50)) if cpu_times else None,
        "cpu_ms_per_frame_p90": float(np.percentile(cpu_times, 90)) if cpu_times else None,
        "outputs": [p.name for p in (video_path, side_path, observations_path, summary_path, out / "masks.npz") if p.exists()]}
    (out / "audit.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "quality_report.json").write_text(json.dumps({"status": "EXPERIMENTAL_UNVALIDATED",
        "physical_note_recall": "NOT_EVALUABLE_NO_MANUAL_PHYSICAL_NOTE_ANNOTATIONS",
        "false_positive_per_minute": "NOT_EVALUABLE_NO_ANNOTATED_NEGATIVE_INTERVALS",
        "tap_hold_confusion": "NOT_EVALUABLE_NO_MANUAL_PHYSICAL_NOTE_ANNOTATIONS",
        "identity_switch_false_merge_fragment_duplication": "NOT_EVALUABLE_NO_PHYSICAL_NOTE_IDS",
        "hold_owner_accuracy": "NOT_EVALUABLE_NO_VERIFIED_HEAD_TAIL_OWNERS",
        "hold_release_reference_error_ms": "NOT_EVALUABLE_NO_VERIFIED_RELEASE_REFERENCES",
        "matched_reference_action_recall": "NOT_EVALUABLE_NO_ANNOTATED_REFERENCE_ACTIONS",
        "timing_error_and_deadline_misses": "NOT_RUN_NO_BASELINE_CANDIDATE_REPLAY",
        "capture_to_decision_latency_and_cpu": "MEASURED_OFFLINE_RENDER_WALL_TIME_ONLY",
        "game_grade": "UNVERIFIED",
        "candidate_action_replay": "NOT_RUN_NO_REPLAY_MODULE_OR_ADAPTER",
        "known_uid_cases": "NOT_RECONSTRUCTED_AS_PHYSICAL_NOTE_TRUTH",
        "limitations": ["Roles adapt the existing detector; this is not an independent V8.4 perception result.",
                        "No annotation is consumed by the causal processing path.",
                        "Geometry remains pending calibration."]}, indent=2), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "output/analysis_lane_filter_v84")
    ap.add_argument("--mode", choices=("baseline", "filtered", "compare"), default="filtered")
    ap.add_argument("--limit-frames", type=int)
    args = ap.parse_args()
    if args.mode != "filtered":
        ap.error("baseline/compare require the not-yet-implemented replay adapter; only filtered is currently available")
    out = run(args.run_dir, args.out, args.limit_frames)
    print(out)


if __name__ == "__main__": main()
