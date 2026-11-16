"""Run measured providers in fresh, counterbalanced processes.

The legacy ``--mode compare`` command runs providers sequentially in one Python
process and retains prior providers' result rows. This wrapper isolates each
provider process and reverses order on alternating repeats so that runtime
outliers from one provider cannot be silently treated as a perception delta.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ("baseline", "segmented", "v85")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def summarize_run(run_output: Path, provider: str, repeat: int) -> tuple[dict, dict]:
    manifest = json.loads((run_output / "replay_manifest.json").read_text(encoding="utf-8"))
    decision_csv = run_output / "physical_note_decisions.csv"
    if (bool(manifest.get("performance_only")) and decision_csv.exists()) or (
            not bool(manifest.get("performance_only")) and int(aggregate["decision_rows"]) > 0
            and not decision_csv.exists()):
        raise RuntimeError(f"per-note decision output presence contradicts recording mode: {run_output}")
    aggregates = read_csv(run_output / "baseline_vs_candidate.csv")
    aggregate = next((row for row in aggregates if row["provider"] == provider), None)
    if aggregate is None:
        raise RuntimeError(f"missing aggregate for {provider}: {run_output}")
    frames = [row for row in read_csv(run_output / "frame_summary.csv")
              if row["provider"] == provider]
    if not frames:
        raise RuntimeError(f"missing frame summary for {provider}: {run_output}")
    processing = [float(row["processing_ms"]) for row in frames]
    capture_age = [float(row["capture_age_ms"]) for row in frames]
    summary = {
        "repeat": repeat,
        "provider": provider,
        "run_dir": run_output.as_posix(),
        "decoded_frames": int(aggregate["decoded_frames"]),
        "processed_frames": int(aggregate["processed_frames"]),
        "dropped_frames": int(aggregate["dropped_frames"]),
        "decision_rows": int(aggregate["decision_rows"]),
        "recording_mode": manifest.get("recording_mode", "detailed"),
        "performance_only": bool(manifest.get("performance_only", False)),
        "per_note_output_history_retained": bool(manifest.get("per_note_output_history_retained", True)),
        "physical_note_attribution_available": bool(manifest.get("physical_note_attribution_available", True)),
        "processing_mean_ms": float(aggregate["compute_ms_mean"]),
        "processing_p90_ms": percentile(processing, 90),
        "processing_p99_ms": percentile(processing, 99),
        "capture_age_p90_ms": percentile(capture_age, 90),
        "capture_age_p99_ms": percentile(capture_age, 99),
        "stale_pause_events": int(aggregate["stale_pause_events"]),
        "stale_timeout_disarms": int(aggregate["stale_timeout_disarms"]),
        "scheduler_accepts": int(aggregate["scheduler_accepts"]),
        "mock_pressed": int(aggregate["mock_pressed"]),
        "mock_key_up_events": int(aggregate["mock_key_up_events"]),
        "mock_key_up_failures": int(aggregate["mock_key_up_failures"]),
        "duplicate_mock_press_uids": int(aggregate["duplicate_mock_press_uids"]),
        "presses_without_release_uid_count": int(aggregate["presses_without_release_uid_count"]),
        "illegal_mock_keys": int(aggregate["illegal_mock_keys"]),
        "geometry_config_sha256": manifest["geometry_config_sha256"],
        "timing_calibration_sha256": manifest["timing_calibration_sha256"],
        "arm_window_s": manifest["simulated_arm_window_s"],
        "birth_zone_end_y": manifest["v85_birth_zone_end_y"],
    }
    return summary, manifest


def source_index_signature(index_path: Path) -> tuple[str, int, float, float, float]:
    rows = read_csv(index_path)
    captures = [float(row["capture_timestamp"]) for row in rows]
    intervals = np.diff(captures)
    return (
        sha256_file(index_path), len(rows),
        float(np.percentile(intervals, 50)) * 1000,
        float(np.percentile(intervals, 90)) * 1000,
        float(np.percentile(intervals, 99)) * 1000,
    )


def validate_frame_timestamps(run_dir: Path, output_dir: Path, provider: str) -> int:
    index = {int(row["video_frame"]): row for row in read_csv(run_dir / "live_video_index.csv")}
    frames = [row for row in read_csv(output_dir / "frame_summary.csv")
              if row["provider"] == provider]
    for row in frames:
        source = index.get(int(row["video_frame"]))
        if source is None:
            raise RuntimeError(f"output frame {row['video_frame']} missing from source index")
        for output_key, source_key in (("captured_at", "capture_timestamp"),
                                       ("acquired_at", "acquired_timestamp")):
            if abs(float(row[output_key]) - float(source[source_key])) > 1e-9:
                raise RuntimeError(
                    f"timestamp mismatch provider={provider} frame={row['video_frame']} "
                    f"field={output_key}")
    return len(frames)


def write_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--simulated-arm-window", type=float, nargs=2,
                        default=(1.0, 124.0), metavar=("START_S", "END_S"))
    parser.add_argument("--birth-zone-end-y", type=float, default=176.75)
    parser.add_argument("--reference-tolerance-ms", type=float, default=80.0)
    parser.add_argument("--limit-frames", type=int, default=None,
                        help="Use only for a short smoke run; omit for full replay.")
    parser.add_argument("--performance-only", action="store_true",
                        help="compact measured recording; omit per-note decision history and attribution output")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    run_dir = args.run_dir.resolve()
    if not (run_dir / "live_video_index.csv").is_file():
        parser.error(f"missing live_video_index.csv in {run_dir}")
    if not (run_dir / "live_source.mp4").is_file():
        parser.error(f"missing live_source.mp4 in {run_dir}")
    output_root = args.out.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    index_sha, source_rows, interval_p50, interval_p90, interval_p99 = source_index_signature(
        run_dir / "live_video_index.csv")

    summaries: list[dict] = []
    manifests: list[dict] = []
    replay_script = ROOT / "tools" / "replay_lane_filter_measured.py"
    for repeat in range(1, args.repeats + 1):
        order = PROVIDERS if repeat % 2 else tuple(reversed(PROVIDERS))
        for provider in order:
            provider_root = output_root / f"repeat_{repeat}" / provider
            command = [
                sys.executable, "-B", str(replay_script),
                "--run-dir", str(run_dir), "--out", str(provider_root),
                "--mode", provider,
                "--simulated-arm-window", str(args.simulated_arm_window[0]),
                str(args.simulated_arm_window[1]),
                "--reference-tolerance-ms", str(args.reference_tolerance_ms),
                "--birth-zone-end-y", str(args.birth_zone_end_y),
            ]
            if args.performance_only:
                command.append("--performance-only")
            if args.limit_frames is not None:
                command.extend(("--limit-frames", str(args.limit_frames)))
            print(f"[repeat {repeat}/{args.repeats}] provider={provider}; launching fresh process",
                  flush=True)
            subprocess.run(command, cwd=ROOT, check=True)
            run_output = provider_root / run_dir.name
            timed_frames = validate_frame_timestamps(run_dir, run_output, provider)
            row, manifest = summarize_run(run_output, provider, repeat)
            row["source_index_rows"] = source_rows
            row["timestamp_verified_frames"] = timed_frames
            row["source_interval_p50_ms"] = interval_p50
            row["source_interval_p90_ms"] = interval_p90
            row["source_interval_p99_ms"] = interval_p99
            summaries.append(row)
            manifests.append(manifest)
            print(f"[repeat {repeat}/{args.repeats}] {provider}: "
                  f"processed={row['processed_frames']} drops={row['dropped_frames']} "
                  f"P90={row['processing_p90_ms']:.2f}ms "
                  f"stale_timeout={row['stale_timeout_disarms']} "
                  f"mock_down={row['mock_pressed']}", flush=True)

    shared = ("geometry_config_sha256", "timing_calibration_sha256", "arm_window_s",
              "birth_zone_end_y", "recording_mode", "performance_only",
              "per_note_output_history_retained", "physical_note_attribution_available")
    for key in shared:
        values = {json.dumps(manifest.get(key), sort_keys=True) for manifest in manifests}
        if len(values) != 1:
            raise RuntimeError(f"provider runs did not share {key}: {sorted(values)}")
    summary_path = output_root / "matrix_summary.csv"
    write_rows(summary_path, summaries)
    matrix_manifest = {
        "source_run": run_dir.name,
        "source_run_path": run_dir.as_posix(),
        "source_index_sha256": index_sha,
        "source_index_rows": source_rows,
        "source_capture_interval_p50_p90_p99_ms": [interval_p50, interval_p90, interval_p99],
        "repeat_count": args.repeats,
        "provider_order_by_repeat": [
            list(PROVIDERS if repeat % 2 else tuple(reversed(PROVIDERS)))
            for repeat in range(1, args.repeats + 1)
        ],
        "process_isolation": "one fresh Python process per provider per repeat",
        "simulated_arm_window_s": list(args.simulated_arm_window),
        "birth_zone_end_y": args.birth_zone_end_y,
        "recording_mode":"performance_only" if args.performance_only else "detailed",
        "performance_only":args.performance_only,
        "per_note_output_history_retained":not args.performance_only,
        "physical_note_attribution_available":not args.performance_only,
        "note":"Performance-only mode still computes every Engine decision and records the scalar row total, but omits per-note output/history; do not use it for per-note attribution.",
        "reference_tolerance_ms": args.reference_tolerance_ms,
        "limit_frames": args.limit_frames,
        "geometry_config_sha256": manifests[0]["geometry_config_sha256"],
        "timing_calibration_sha256": manifests[0]["timing_calibration_sha256"],
        "python": sys.version,
        "platform": platform.platform(),
        "cpu_count": __import__("os").cpu_count(),
        "video_encoding_included": False,
        "OS_keyboard_injection": False,
        "scheduler_safety_bounds_changed": False,
        "matrix_summary": summary_path.as_posix(),
    }
    (output_root / "matrix_manifest.json").write_text(
        json.dumps(matrix_manifest, indent=2), encoding="utf-8")
    print(f"matrix: {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
