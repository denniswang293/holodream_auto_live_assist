"""Profile segmentation internals on indexed high-cost frames and controls.

This is an offline diagnostic. It decodes the immutable source sequentially,
profiles only LanePixelSegmenter.segment(), and excludes video encoding.
"""
from __future__ import annotations

import argparse
import cProfile
import csv
from dataclasses import asdict
import hashlib
import io
import json
import pstats
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lane_segmentation import LanePixelSegmenter  # noqa: E402
from src.model import Geometry  # noqa: E402
from tools.replay_lane_filter import read_index  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        fields = list(dict.fromkeys(key for row in rows for key in row))
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def output_fingerprints(result) -> tuple[str, str]:
    """Hash exact role masks and the complete ordered component records."""
    mask_digest = hashlib.sha256()
    for role, mask in result.masks.items():
        mask_digest.update(role.encode("utf-8"))
        mask_digest.update(b"\0")
        mask_digest.update(mask.dtype.str.encode("ascii"))
        mask_digest.update(repr(mask.shape).encode("ascii"))
        mask_digest.update(mask.tobytes(order="C"))
    component_bytes = json.dumps(
        [asdict(component) for component in result.components],
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    return mask_digest.hexdigest(), hashlib.sha256(component_bytes).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path,
                        default=ROOT / "output/recording/run_20261106T164049_800126Z")
    parser.add_argument("--prior-profile-dir", type=Path,
                        default=ROOT / "output/analysis_v86_autoloop/iteration_0058/measured_repeats2")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "output/analysis_v86_autoloop/iteration_0067/tap_recovery_diagnostics")
    parser.add_argument("--top-frames", type=int, default=24)
    parser.add_argument("--control-frames", type=int, default=8)
    args = parser.parse_args()
    run_dir, prior_dir, out = args.run_dir.resolve(), args.prior_profile_dir.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    by_frame: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    profile_files = sorted(prior_dir.glob("repeat_*/v85/run_*/stage_profile_by_frame.csv"))
    if len(profile_files) != 2:
        raise RuntimeError(f"expected two prior V85 profiles; found {len(profile_files)}")
    for path in profile_files:
        for row in read_rows(path):
            frame = int(row["video_frame"])
            for metric in ("class_component_loop_ms", "tap_panel_recovery_ms"):
                if row.get(metric):
                    by_frame[frame][metric].append(float(row[metric]))
    ranking = sorted(
        ((frame, statistics.mean(values["class_component_loop_ms"]))
         for frame, values in by_frame.items() if values["class_component_loop_ms"]),
        key=lambda item: (-item[1], item[0]),
    )
    hot = [frame for frame, _ in ranking[:args.top_frames]]
    hot_set = set(hot)
    controls = [frame for frame, _ in ranking if frame not in hot_set]
    if controls:
        step = max(1, len(controls) // max(1, args.control_frames))
        controls = controls[step // 2::step][:args.control_frames]
    selected = set(hot) | set(controls)

    index = read_index(run_dir / "live_video_index.csv")
    cap = cv2.VideoCapture(str(run_dir / "live_source.mp4"))
    if not cap.isOpened():
        raise RuntimeError(f"could not open source video in {run_dir}")
    geometry = Geometry(ROOT / "config/geometry_live_assist.json")
    segmenter = LanePixelSegmenter()
    segmenter.profile_tap_recovery = True
    profiler = cProfile.Profile()
    rows = []
    decoded = 0
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                break
            frame = decoded
            decoded += 1
            if frame not in selected:
                continue
            index_row = index.get(frame)
            if index_row is None:
                raise RuntimeError(f"source frame {frame} missing from index")
            normalized_started = time.perf_counter()
            normalized = geometry.normalize(image)
            normalize_ms = (time.perf_counter() - normalized_started) * 1000
            rectify_started = time.perf_counter()
            rectified = geometry.rectify(normalized)
            rectify_ms = (time.perf_counter() - rectify_started) * 1000
            profiler.enable()
            segment_started = time.perf_counter()
            result = segmenter.segment(rectified, geometry, frame_index=frame)
            segmentation_ms = (time.perf_counter() - segment_started) * 1000
            profiler.disable()
            mask_sha256, ordered_components_sha256 = output_fingerprints(result)
            rows.append({
                "video_frame": frame,
                "source_frame": int(index_row.get("source_frame", frame)),
                "capture_timestamp": index_row["capture_timestamp"],
                "sample_role": "hot" if frame in hot_set else "control",
                "prior_class_component_mean_ms": statistics.mean(by_frame[frame]["class_component_loop_ms"]),
                "prior_tap_panel_recovery_mean_ms": statistics.mean(by_frame[frame]["tap_panel_recovery_ms"]),
                "normalize_ms": normalize_ms,
                "rectify_ms": rectify_ms,
                "segmentation_wall_ms_instrumented": segmentation_ms,
                **segmenter.last_profile,
                "mask_sha256": mask_sha256,
                "ordered_components_sha256": ordered_components_sha256,
                **{f"components_{role}": count for role, count in Counter(c.role for c in result.components).items()},
                "components_total": len(result.components),
            })
    finally:
        cap.release()

    if len(rows) != len(selected):
        raise RuntimeError(f"selected {len(selected)} frames but profiled {len(rows)}")
    write_rows(out / "selected_frame_profile.csv", rows)
    pass_summary = {}
    for pass_name in ("yellow", "cyan_global", "cyan_tiled"):
        prefix = f"tap_recovery_{pass_name}"
        times = sorted(float(row[f"{prefix}_ms"]) for row in rows)
        pass_summary[pass_name] = {
            "mean_ms": statistics.mean(times) if times else None,
            "p90_ms": times[min(len(times)-1, int(.9*(len(times)-1)))] if times else None,
            "connected_component_proposals": sum(int(row[f"{prefix}_connected_component_proposals"]) for row in rows),
            "geometry_qualified_proposals": sum(int(row[f"{prefix}_geometry_qualified_proposals"]) for row in rows),
            "accepted_faces": sum(int(row[f"{prefix}_accepted_faces"]) for row in rows),
            "duplicate_rejections": sum(int(row[f"{prefix}_duplicate_rejections"]) for row in rows),
        }
    (out / "tap_recovery_pass_summary.json").write_text(
        json.dumps(pass_summary, indent=2), encoding="utf-8")
    report_lines = [
        "# Iteration 0067 — Tap recovery diagnostic profile",
        "",
        "This is an offline diagnostic on the existing 24 high-cost and 8 control frames. Tap pass timers and counters are opt-in; `cProfile` is enabled, so these measurements are not performance-A/B eligible.",
        "",
        f"- Source run: `{run_dir.name}`; sequentially decoded frames: {decoded}; profiled frames: {len(rows)} (24 hot / 8 control expected).",
        "- Normalization and rectification are timed separately; no rendering or video encoding is included.",
        "",
        "| Tap pass | Mean ms | P90 ms | CC proposals | Geometry qualified | Accepted faces | Duplicate rejections |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for pass_name, stats in pass_summary.items():
        report_lines.append(
            f"| {pass_name} | {stats['mean_ms']:.3f} | {stats['p90_ms']:.3f} | "
            f"{stats['connected_component_proposals']} | {stats['geometry_qualified_proposals']} | "
            f"{stats['accepted_faces']} | {stats['duplicate_rejections']} |"
        )
    report_lines.extend([
        "",
        "Per-frame fields are in `selected_frame_profile.csv`; proposal counters describe source connected components, post-panel-gate proposals, accepted recovered faces, and duplicate rejections respectively.",
        "",
        "Diagnostics add measurement overhead but do not alter thresholds, masks, component order/IDs, evidence, or ownership decisions. Treat timings as diagnostic only.",
    ])
    (out / "iteration_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    report = io.StringIO()
    pstats.Stats(profiler, stream=report).strip_dirs().sort_stats("cumtime").print_stats(45)
    (out / "cprofile_top_functions.txt").write_text(report.getvalue(), encoding="utf-8")
    manifest = {
        "iteration": "0067",
        "source_run": run_dir.name,
        "source_index_sha256": sha256(run_dir / "live_video_index.csv"),
        "source_index_rows": len(index),
        "decoded_video_frames_sequentially": decoded,
        "profiled_frames": len(rows),
        "hot_video_frames": hot,
        "control_video_frames": controls,
        "selection_metric": "mean class_component_loop_ms across the two iteration 0058 V85 measured repeats",
        "prior_profile_files": [str(path.relative_to(ROOT)) for path in profile_files],
        "geometry_sha256": geometry.sha256,
        "profile_scope": "LanePixelSegmenter.segment only; opt-in Tap pass timers and counters; normalization and rectification timed separately; no encoding",
        "tap_recovery_diagnostics_enabled": True,
        "tap_recovery_passes": ["yellow", "cyan_global", "cyan_tiled"],
        "cprofile_instrumented": True,
        "performance_a_b_eligible": False,
        "OS_keyboard_injection": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
