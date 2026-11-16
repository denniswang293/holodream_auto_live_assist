"""Diagnostic-only V8.5 per-note decision section profile.

This wraps the measured replay's opt-in per-note timers and writes only compact
frame profile rows plus a manifest. Instrumented wall times are not suitable
for the official measured A/B matrix.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.replay_lane_filter_measured import simulate_provider  # noqa: E402
from tools.replay_lane_filter import read_index  # noqa: E402
from src.model import Geometry  # noqa: E402


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path,
                        default=ROOT / "output/recording/run_20261106T164049_800126Z")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "output/analysis_v86_autoloop/iteration_0057/diagnostic_note_sections")
    parser.add_argument("--arm-window", type=float, nargs=2, default=(1.0, 124.0))
    parser.add_argument("--birth-zone-end-y", type=float, default=176.75)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)

    state, counts = simulate_provider(
        run_dir, "v85", tuple(args.arm_window), limit=None,
        birth_zone_end_y=args.birth_zone_end_y,
        profile_v85_decision_notes=True,
    )
    profiles = [{"provider": "v85", **row} for row in state["profile"]]
    write_rows(out / "stage_profile_by_frame.csv", profiles)
    actions = state["actions"]
    summary = {
        "provider": "v85",
        **counts,
        "decision_rows": len(state["decisions"]),
        "mock_pressed": sum(row.get("event") == "pressed" for row in actions),
        "scheduler_accepted": sum(row.get("event") == "accepted" for row in actions),
        "instrumented_processing_mean_ms": statistics.mean(state["wall_ms"]) if state["wall_ms"] else None,
        "instrumented_processing_p90_ms": __import__("numpy").percentile(state["wall_ms"], 90) if state["wall_ms"] else None,
        "warning": "Diagnostic-only per-note timers perturb inference time; do not use these costs as measured A/B results.",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    index = read_index(run_dir / "live_video_index.csv")
    geometry = Geometry(ROOT / "config/geometry_live_assist.json")
    timing_path = ROOT / "config/reference_timing.json"
    manifest = {
        "source_run": run_dir.name,
        "source_index_rows": len(index),
        "source_index_sha256": sha256(run_dir / "live_video_index.csv"),
        "geometry_config_sha256": geometry.sha256,
        "timing_calibration_sha256": sha256(timing_path),
        "simulated_arm_window_s": list(args.arm_window),
        "birth_zone_end_y": args.birth_zone_end_y,
        "profile_v85_decision_notes": True,
        "performance_a_b_eligible": False,
        "video_encoding_included": False,
        "OS_keyboard_injection": False,
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": __import__("os").cpu_count(),
    }
    (out / "replay_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
