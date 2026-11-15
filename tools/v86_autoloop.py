"""Run repeatable offline V8.6 checks around the existing replay tools.

This orchestration layer only launches offline tools and writes inside a new
iteration directory. It never invokes Git, Live input, or cleanup operations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "output" / "analysis_v86_autoloop"
BASELINE_SNAPSHOT = DEFAULT_OUT / "iteration_0000" / "baseline" / "asset_baseline.json"
QUICK_LIMIT_FRAMES = 300
DEFAULT_BIRTH_ZONE_END_Y = "176.75"
SOURCE_INPUT_NAMES = (
    "live_source.mp4", "live_video_index.csv", "player_key_events.csv",
    "markers.csv", "session.json",
)
CONFIG_NAMES = ("config/geometry_live_assist.json", "config/reference_timing.json")
ORCHESTRATED_TOOLS = (
    "tools/replay_lane_filter.py", "tools/replay_lane_filter_measured.py",
    "tools/attribute_lane_action_losses.py", "tools/profile_v85_birth.py",
    "tools/render_v85_review_set.py", "tools/summarize_v85_replay.py",
    "tools/v86_autoloop.py", "tools/v86_case_windows.py",
)


def discover_runs(root: Path = ROOT) -> list[Path]:
    """Return complete indexed runs in stable, recording-first order."""
    candidates: list[Path] = []
    for family in ("recording", "assist"):
        parent = root / "output" / family
        if not parent.is_dir():
            continue
        for run_dir in parent.glob("run_*"):
            if (run_dir.is_dir() and (run_dir / "live_source.mp4").is_file()
                    and (run_dir / "live_video_index.csv").is_file()):
                candidates.append(run_dir.resolve())
    candidates.sort(key=lambda p: (0 if p.parent.name == "recording" else 1, p.name))
    preferred = root / "output" / "recording" / "run_20261106T164049_800126Z"
    if preferred.resolve() in candidates:
        candidates.remove(preferred.resolve())
        candidates.insert(0, preferred.resolve())
    return candidates


def select_runs(requested: list[Path] | None, root: Path = ROOT) -> list[Path]:
    runs = [p.resolve() for p in (requested or [])]
    if not runs:
        discovered = discover_runs(root)
        runs = discovered[:1]
    missing = [p for p in runs if not p.is_dir()]
    invalid = [p for p in runs if p.is_dir() and not (p / "live_source.mp4").is_file()]
    invalid += [p for p in runs if p.is_dir() and not (p / "live_video_index.csv").is_file()]
    if missing or invalid:
        details = ", ".join(str(p) for p in dict.fromkeys(missing + invalid))
        raise ValueError(f"run directories must include live_source.mp4 and live_video_index.csv: {details}")
    if not runs:
        raise ValueError("no complete recording/assist runs found; pass --run-dir")
    return list(dict.fromkeys(runs))


def all_scan_runs(selected: list[Path], root: Path = ROOT) -> list[Path]:
    """Use selected inputs first, then other complete local runs for full scans."""
    return list(dict.fromkeys(selected + discover_runs(root)))


def choose_iteration(out_root: Path, requested: int | None) -> tuple[int, Path]:
    if requested is not None:
        if requested < 0:
            raise ValueError("--iteration must be zero or greater")
        number = requested
    else:
        present = []
        if out_root.is_dir():
            for path in out_root.glob("iteration_[0-9][0-9][0-9][0-9]"):
                try:
                    present.append(int(path.name.rsplit("_", 1)[1]))
                except ValueError:
                    continue
        number = max(present, default=-1) + 1
    path = out_root / f"iteration_{number:04d}"
    if path.exists():
        raise FileExistsError(f"iteration already exists; choose another --iteration: {path}")
    return number, path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_manifest(runs: list[Path], root: Path = ROOT) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    for run_dir in runs:
        for name in SOURCE_INPUT_NAMES:
            path = run_dir / name
            try:
                display_path = str(path.relative_to(root))
            except ValueError:
                display_path = str(path)
            row: dict[str, Any] = {"path": display_path, "status": "UNAVAILABLE"}
            if path.is_file():
                row.update(status="AVAILABLE", size_bytes=path.stat().st_size,
                           sha256=sha256_file(path))
            assets.append(row)

    source_files = sorted((root / "src").rglob("*.py"))
    source_files += [root / name for name in ORCHESTRATED_TOOLS if (root / name).is_file()]
    source_files += [root / name for name in CONFIG_NAMES if (root / name).is_file()]
    code = [{"path": str(path.relative_to(root)), "size_bytes": path.stat().st_size,
             "sha256": sha256_file(path)} for path in dict.fromkeys(source_files)]

    baseline: dict[str, str] = {}
    if BASELINE_SNAPSHOT.is_file():
        try:
            snapshot = json.loads(BASELINE_SNAPSHOT.read_text(encoding="utf-8"))
            baseline = {item["path"]: item["sha256"]
                        for item in snapshot.get("source_and_config_sha256", [])}
        except (OSError, ValueError, KeyError, TypeError):
            baseline = {}
    for row in code:
        old = baseline.get(row["path"])
        row["baseline_sha256"] = old
        row["baseline_match"] = (row["sha256"] == old) if old else None
    return {"runs": assets, "source_config_tool_hashes": code,
            "baseline_snapshot": str(BASELINE_SNAPSHOT.relative_to(root)) if BASELINE_SNAPSHOT.is_file() else None}


def command_steps(mode: str, runs: list[Path], scan_runs: list[Path], iteration_dir: Path,
                  root: Path = ROOT) -> list[dict[str, Any]]:
    primary = runs[0]
    py = sys.executable
    common_replay = ["--run-dir", str(primary), "--mode", "compare",
                     "--simulated-arm-window", "1", "124",
                     "--birth-zone-end-y", DEFAULT_BIRTH_ZONE_END_Y]
    fixed_out = iteration_dir / "fixed"
    fixed_dir = fixed_out / primary.name
    syntax_check = (
        "from pathlib import Path; "
        "files=[*Path('src').rglob('*.py'),*Path('tools').rglob('*.py'),*Path('tests').rglob('*.py')]; "
        "[compile(p.read_text(encoding='utf-8-sig'),str(p),'exec') for p in files]"
    )
    steps: list[dict[str, Any]] = [
        {"name": "unit_tests", "command": [py, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"]},
        {"name": "compile", "command": [py, "-B", "-c", syntax_check]},
    ]
    fixed_cmd = [py, "tools/replay_lane_filter.py", *common_replay, "--out", str(fixed_out),
                 "--latency-ms", "14"]
    measured_root = iteration_dir / "measured"
    repeats = 1 if mode == "quick" else 2
    if mode == "quick":
        fixed_cmd += ["--limit-frames", str(QUICK_LIMIT_FRAMES)]
    steps.append({"name": "fixed_compare", "command": fixed_cmd})
    measured_dirs = []
    for repeat in range(1, repeats + 1):
        measured_out = measured_root / f"repeat_{repeat}"
        measured_dir = measured_out / primary.name
        measured_dirs.append(measured_dir)
        measured_cmd = [py, "tools/replay_lane_filter_measured.py", *common_replay,
                        "--out", str(measured_out)]
        if mode == "quick":
            measured_cmd += ["--limit-frames", str(QUICK_LIMIT_FRAMES)]
        steps.append({"name": f"measured_repeat_{repeat}", "command": measured_cmd})

    if mode == "quick":
        steps.append({"name": "quick_preview", "command": [
            py, "tools/v86_case_windows.py", "--quick-preview", "--run-dir", str(primary),
            "--fixed-dir", str(fixed_dir), "--measured-dir", str(measured_dirs[0]),
            "--out", str(iteration_dir / "quick_preview")]})
        steps.append({"name": "compact_report", "internal": "quick_report",
                      "fixed_dir": str(fixed_dir), "measured_dir": str(measured_dirs[0]),
                      "preview_dir": str(iteration_dir / "quick_preview"),
                      "out": str(iteration_dir / "reports" / "quick_summary.json")})
    else:
        attribution_dir = iteration_dir / "action_attribution"
        steps.append({"name": "action_attribution", "command": [
            py, "tools/attribute_lane_action_losses.py", "--run-dir", str(primary),
            "--replay-dir", str(fixed_dir), "--candidate-provider", "v85",
            "--out", str(attribution_dir)]})
        scan_dir = iteration_dir / "candidate_scan"
        scan_cmd = [py, "tools/profile_v85_birth.py"]
        for run_dir in scan_runs:
            scan_cmd += ["--run-dir", str(run_dir)]
        steps.append({"name": "candidate_scan", "command": scan_cmd + ["--out", str(scan_dir)]})
        steps.append({"name": "full_report", "command": [
            py, "tools/summarize_v85_replay.py", "--run-id", primary.name,
            "--fixed-dir", str(fixed_dir), "--measured-dir", str(measured_dirs[0]),
            "--profile-csv", str(measured_dirs[0] / "stage_profile_by_frame.csv"),
            "--candidate-tracks", str(scan_dir / "early_candidate_tracks.csv"),
            "--out", str(iteration_dir / "reports" / "repeat_1")]})
        steps.append({"name": "full_report_repeat_2", "command": [
            py, "tools/summarize_v85_replay.py", "--run-id", primary.name,
            "--fixed-dir", str(fixed_dir), "--measured-dir", str(measured_dirs[1]),
            "--profile-csv", str(measured_dirs[1] / "stage_profile_by_frame.csv"),
            "--candidate-tracks", str(scan_dir / "early_candidate_tracks.csv"),
            "--out", str(iteration_dir / "reports" / "repeat_2")]})
        steps.append({"name": "repeat_variance_report", "internal": "repeat_variance",
                      "repeat_1": str(measured_dirs[0]), "repeat_2": str(measured_dirs[1]),
                      "out": str(iteration_dir / "reports" / "repeat_comparison")})
        cases_cmd = [py, "tools/v86_case_windows.py", "--run-dir", str(primary),
                     "--fixed-dir", str(fixed_dir), "--measured-dir", str(measured_dirs[0]),
                     "--attribution-csv", str(attribution_dir / "action_loss_attribution.csv")]
        assist_run = next((p for p in scan_runs if p.name == "run_20261109T143554_007912Z"), None)
        if assist_run is not None:
            cases_cmd += ["--assist-run-dir", str(assist_run)]
        steps.append({"name": "source_aligned_case_windows",
                      "command": cases_cmd + ["--out", str(iteration_dir / "case_windows")]})
    return steps


def quick_report(fixed_dir: Path, measured_dir: Path, preview_dir: Path, output: Path) -> None:
    """Write a compact report from the existing replay summary CSVs."""
    def read_rows(path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    fixed_rows = read_rows(fixed_dir / "baseline_vs_candidate.csv")
    measured_rows = read_rows(measured_dir / "baseline_vs_candidate.csv")
    preview_summary = preview_dir / "quick_event_summary.json"
    preview = json.loads(preview_summary.read_text(encoding="utf-8")) if preview_summary.is_file() else None
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PARTIAL_QUICK_REPLAY_WITH_SOURCE_PREVIEW",
        "ground_truth_status": "UNVERIFIED; replay and Legacy actions are not physical-note ground truth",
        "fixed_compare": fixed_rows,
        "measured_compare": measured_rows,
        "fixed_profile_rows": len(read_rows(fixed_dir / "stage_profile_by_frame.csv")),
        "measured_profile_rows": len(read_rows(measured_dir / "stage_profile_by_frame.csv")),
        "source_preview_image": str(preview_dir / "quick_preview.png"),
        "source_event_summary": preview,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def repeat_variance_report(repeat_1: Path, repeat_2: Path, output_dir: Path) -> None:
    """Compare matching provider metrics across measured-time repetitions."""
    def read_rows(path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    left = {row.get("provider", ""): row for row in read_rows(repeat_1 / "baseline_vs_candidate.csv")}
    right = {row.get("provider", ""): row for row in read_rows(repeat_2 / "baseline_vs_candidate.csv")}
    metrics = ("decoded_frames", "processed_frames", "dropped_frames", "decision_rows",
               "compute_ms_mean", "compute_ms_p90", "scheduler_accepts", "mock_pressed",
               "matched_reference_actions", "wrong_key_or_extra_mock_presses",
               "unique_mock_press_uids", "mock_key_up_failures", "presses_without_release_uid_count")
    rows = []
    by_provider = {}
    for provider in sorted(set(left) | set(right)):
        comparisons = []
        for metric in metrics:
            try:
                a = float(left[provider][metric])
                b = float(right[provider][metric])
            except (KeyError, ValueError, TypeError):
                continue
            row = {"provider": provider, "metric": metric, "repeat_1": a, "repeat_2": b,
                   "repeat_2_minus_repeat_1": b-a,
                   "relative_delta_percent": ((b-a)/abs(a)*100 if a else None)}
            rows.append(row)
            comparisons.append(row)
        by_provider[provider] = comparisons
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "measured_repeat_comparison.json"
    json_path.write_text(json.dumps({"status": "MEASURED_REPEAT_VARIANCE",
        "repeat_1_dir": str(repeat_1), "repeat_2_dir": str(repeat_2),
        "comparison_basis": "same run, provider, metric; host variation is descriptive",
        "providers": by_provider}, indent=2), encoding="utf-8")
    csv_path = output_dir / "measured_repeat_comparison.csv"
    fields = ["provider", "metric", "repeat_1", "repeat_2", "repeat_2_minus_repeat_1",
              "relative_delta_percent"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def execute_steps(steps: list[dict[str, Any]], iteration_dir: Path, manifest: dict[str, Any]) -> int:
    logs_dir = iteration_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = iteration_dir / "manifest.json"
    for step in steps:
        name = step["name"]
        entry = {"name": name, "status": "RUNNING", "started_utc": datetime.now(timezone.utc).isoformat()}
        manifest["steps"].append(entry)
        write_json(manifest_path, manifest)
        try:
            if step.get("internal") == "quick_report":
                quick_report(Path(step["fixed_dir"]), Path(step["measured_dir"]),
                             Path(step["preview_dir"]), Path(step["out"]))
                return_code = 0
                entry["command"] = "internal:quick_report"
                entry["stdout_log"] = None
                entry["stderr_log"] = None
            elif step.get("internal") == "repeat_variance":
                repeat_variance_report(Path(step["repeat_1"]), Path(step["repeat_2"]),
                                       Path(step["out"]))
                return_code = 0
                entry["command"] = "internal:repeat_variance_report"
                entry["stdout_log"] = None
                entry["stderr_log"] = None
            else:
                command = step["command"]
                entry["command"] = command
                out_log = logs_dir / f"{name}.stdout.log"
                err_log = logs_dir / f"{name}.stderr.log"
                result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8",
                                        errors="replace", stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, shell=False)
                out_log.write_text(result.stdout, encoding="utf-8")
                err_log.write_text(result.stderr, encoding="utf-8")
                return_code = result.returncode
                entry.update(return_code=return_code, stdout_log=str(out_log.relative_to(iteration_dir)),
                             stderr_log=str(err_log.relative_to(iteration_dir)))
            entry["finished_utc"] = datetime.now(timezone.utc).isoformat()
            entry["status"] = "PASSED" if return_code == 0 else "FAILED"
            if return_code:
                manifest.update(status="FAILED", failed_step=name, finished_utc=entry["finished_utc"])
                write_json(manifest_path, manifest)
                return return_code
        except Exception as exc:  # Preserve launch/report failure in the manifest.
            entry.update(status="FAILED", error=f"{type(exc).__name__}: {exc}",
                         finished_utc=datetime.now(timezone.utc).isoformat())
            manifest.update(status="FAILED", failed_step=name, finished_utc=entry["finished_utc"])
            write_json(manifest_path, manifest)
            return 1
        write_json(manifest_path, manifest)
    manifest.update(status="COMPLETED", finished_utc=datetime.now(timezone.utc).isoformat())
    write_json(manifest_path, manifest)
    return 0


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true", help=f"limited replay ({QUICK_LIMIT_FRAMES} frames), one measured pass")
    mode.add_argument("--full", action="store_true", help="full fixed replay, two measured repeats, attribution, scan, review clips, report")
    parser.add_argument("--run-dir", type=Path, action="append",
                        help="primary input run (repeatable; first is the replay source); auto-select when omitted")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="iteration parent directory (default: output/analysis_v86_autoloop)")
    parser.add_argument("--iteration", type=int,
                        help="iteration number; default is next available without overwriting")
    parser.add_argument("--dry-run", "--plan", action="store_true", dest="dry_run",
                        help="print selected runs and commands without creating files or running tools")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        runs = select_runs(args.run_dir)
        scan_runs = all_scan_runs(runs) if args.full else runs
        mode = "full" if args.full else "quick"
        iteration_number, iteration_dir = choose_iteration(args.out.resolve(), args.iteration)
        steps = command_steps(mode, runs, scan_runs, iteration_dir)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    plan = {"mode": mode, "iteration": iteration_number,
            "iteration_dir": str(iteration_dir), "primary_run": str(runs[0]),
            "runs": [str(path) for path in runs],
            "candidate_scan_runs": [str(path) for path in scan_runs],
            "steps": [{k: v for k, v in step.items()} for step in steps]}
    if args.dry_run:
        print(json.dumps(plan, indent=2, default=str))
        return 0

    iteration_dir.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "tool": "tools/v86_autoloop.py", "mode": mode,
        "iteration": iteration_number, "iteration_dir": str(iteration_dir),
        "started_utc": datetime.now(timezone.utc).isoformat(), "status": "RUNNING",
        "fail_fast": True, "git_commands_run": False,
        "live_or_keyboard_input_used": False,
        "primary_run": str(runs[0]), "runs": [str(p) for p in runs],
        "candidate_scan_runs": [str(p) for p in scan_runs],
        "asset_manifest": asset_manifest(scan_runs, ROOT), "steps": [],
        "plan": plan,
    }
    write_json(iteration_dir / "manifest.json", manifest)
    return execute_steps(steps, iteration_dir, manifest)


if __name__ == "__main__":
    raise SystemExit(main())
