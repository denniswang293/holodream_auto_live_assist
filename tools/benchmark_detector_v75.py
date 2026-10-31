"""Replay one source video for V7.5 detector A/B measurements.

This benchmark measures detector work only; video decode time is excluded from
the per-frame samples. It is intentionally offline and never sends input.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import cv2

from src.detector import detect
from src.geometry import Playfield


def percentile(values, p):
    values = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not values:
        return ""
    k = (len(values) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] if lo == hi else values[lo] + (values[hi] - values[lo]) * (k - lo)


def git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "UNKNOWN"


def run_once(source, config, *, cache_enabled, repeat):
    cfg = json.loads(config.read_text(encoding="utf-8-sig"))
    detector_cfg = {**cfg["detector"], "reference_resolution": cfg["reference_resolution"],
                    "cache_enabled": cache_enabled}
    playfield = Playfield.from_config(cfg["playfield"], cfg["reference_resolution"])
    cap = cv2.VideoCapture(str(source))
    frame_rows, profile = [], {}
    candidate_rows = []
    pink_counts = {}
    decoded = 0
    started = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_index = decoded
        decoded += 1
        diagnostics = {}
        detector_started = time.perf_counter()
        candidates = detect(frame, playfield, cfg["key_map"], detector_cfg,
                            diagnostics, profile=profile, frame_index=frame_index)
        detector_ms = (time.perf_counter() - detector_started) * 1000
        frame_rows.append({"repeat": repeat, "frame": frame_index,
                           "detector_ms": detector_ms,
                           "candidate_count": len(candidates),
                           "pink_candidate_count": sum(c.appearance == "pink_candidate" for c in candidates),
                           "pink_tap_count": sum(c.appearance == "pink_candidate" and c.note_type == "tap"
                                                  for c in candidates),
                           "pink_core_trimmed": diagnostics.get("pink_core_trimmed", 0)})
        for c in candidates:
            candidate_rows.append({"repeat": repeat, "frame": frame_index,
                                   "appearance": c.appearance, "note_type": c.note_type,
                                   "x": c.bbox[0], "y": c.bbox[1], "w": c.bbox[2], "h": c.bbox[3],
                                   "score": c.score, "candidate_keys": "|".join(c.candidate_keys),
                                   "u_min": c.u_min, "u_max": c.u_max})
        for reason, count in diagnostics.get("pink_rejection_counts", {}).items():
            pink_counts[reason] = pink_counts.get(reason, 0) + count
    cap.release()
    elapsed = time.perf_counter() - started
    return frame_rows, profile, candidate_rows, pink_counts, elapsed, decoded


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--cache", choices=("on", "off"), default="on")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    all_frames, all_profile, all_candidates, pink_counts = [], {}, [], {}
    elapsed, decoded = 0., 0
    for repeat in range(args.repeats):
        rows, profile, candidates, counts, took, decoded = run_once(
            args.source, args.config, cache_enabled=args.cache == "on", repeat=repeat)
        all_frames.extend(rows)
        all_candidates.extend(candidates)
        elapsed += took
        for name, values in profile.items():
            all_profile.setdefault(name, []).extend(values)
        for reason, count in counts.items():
            pink_counts[reason] = pink_counts.get(reason, 0) + count
    warm = [row for row in all_frames if row["frame"] >= 30]
    stage_rows = []
    for stage, values in sorted(all_profile.items()):
        stage_rows.append({"stage": stage, "samples": len(values),
                           "p50_ms": percentile(values, 50), "p95_ms": percentile(values, 95),
                           "p99_ms": percentile(values, 99),
                           "mean_ms": statistics.mean(values) if values else ""})
    with (args.out / "detector_stage_perf.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(stage_rows[0]) if stage_rows else ["status"])
        writer.writeheader(); writer.writerows(stage_rows)
    with (args.out / "detector_frame_perf.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = list(all_frames[0]) if all_frames else ["status"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(all_frames)
    with (args.out / "candidate_replay.csv").open("w", newline="", encoding="utf-8-sig") as f:
        fields = list(all_candidates[0]) if all_candidates else ["status"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(all_candidates)
    summary = {
        "git_sha": git_sha(), "python": sys.version, "platform": platform.platform(),
        "opencv": cv2.__version__, "source": str(args.source), "config": str(args.config),
        "repeats": args.repeats, "cache_enabled": args.cache == "on", "decoded_frames": decoded,
        "detector_wall_seconds_excluding_decode": elapsed,
        "detector_ms_p50": percentile([r["detector_ms"] for r in warm], 50),
        "detector_ms_p95": percentile([r["detector_ms"] for r in warm], 95),
        "detector_ms_p99": percentile([r["detector_ms"] for r in warm], 99),
        "candidate_count": len(all_candidates),
        "pink_candidate_count": sum(r["pink_candidate_count"] for r in all_frames),
        "pink_tap_count": sum(r["pink_tap_count"] for r in all_frames),
        "pink_rejection_counts": pink_counts,
        "warmup_frames_excluded_from_percentiles": 30,
    }
    (args.out / "detector_perf_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
