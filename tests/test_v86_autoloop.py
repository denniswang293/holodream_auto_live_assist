from pathlib import Path
import json
import sys

import pytest

from tools.v86_autoloop import (
    all_scan_runs,
    choose_iteration,
    command_steps,
    discover_runs,
    execute_steps,
    repeat_variance_report,
    select_runs,
)


def _make_run(root: Path, family: str, name: str) -> Path:
    run = root / "output" / family / name
    run.mkdir(parents=True)
    (run / "live_source.mp4").write_bytes(b"fixture")
    (run / "live_video_index.csv").write_text("video_frame,capture_timestamp\n0,0\n")
    return run


def test_discovery_is_complete_run_only_and_recordings_first(tmp_path):
    assist = _make_run(tmp_path, "assist", "run_assist")
    recording = _make_run(tmp_path, "recording", "run_recording")
    incomplete = tmp_path / "output" / "recording" / "run_incomplete"
    incomplete.mkdir()
    (incomplete / "live_source.mp4").write_bytes(b"fixture")

    found = discover_runs(tmp_path)
    assert found == [recording.resolve(), assist.resolve()]
    assert select_runs(None, tmp_path) == [recording.resolve()]
    assert all_scan_runs([assist.resolve()], tmp_path) == [assist.resolve(), recording.resolve()]


def test_iteration_selection_never_reuses_existing_number(tmp_path):
    (tmp_path / "iteration_0002").mkdir()
    number, path = choose_iteration(tmp_path, None)
    assert number == 3
    assert path == tmp_path / "iteration_0003"
    with pytest.raises(FileExistsError):
        choose_iteration(tmp_path, 2)


def test_quick_and_full_plans_preserve_existing_tool_interfaces(tmp_path):
    run = _make_run(tmp_path, "recording", "run_fixture").resolve()
    quick = command_steps("quick", [run], [run], tmp_path / "iteration_0001")
    quick_by_name = {step["name"]: step for step in quick}
    assert [step["name"] for step in quick] == [
        "unit_tests", "compile", "fixed_compare", "measured_repeat_1", "quick_preview", "compact_report"
    ]
    assert quick_by_name["compile"]["command"][2] == "-c"
    assert "utf-8-sig" in quick_by_name["compile"]["command"][3]
    for name in ("fixed_compare", "measured_repeat_1"):
        assert "--run-dir" in quick_by_name[name]["command"]
        assert "--mode" in quick_by_name[name]["command"]
        assert "--limit-frames" in quick_by_name[name]["command"]
    assert "--quick-preview" in quick_by_name["quick_preview"]["command"]
    assert quick_by_name["quick_preview"]["command"][-2:] == [
        "--out", str(tmp_path / "iteration_0001" / "quick_preview")
    ]

    full = command_steps("full", [run], [run], tmp_path / "iteration_0002")
    full_names = [step["name"] for step in full]
    assert full_names.count("measured_repeat_1") == 1
    assert full_names.count("measured_repeat_2") == 1
    assert full_names[-4:] == [
        "full_report", "full_report_repeat_2", "repeat_variance_report",
        "source_aligned_case_windows"
    ]
    assert "--limit-frames" not in full[2]["command"]
    assert "--limit-frames" not in full[3]["command"]
    assert "--profile-v85-decision-notes" not in full[3]["command"]
    attribution = next(step for step in full if step["name"] == "action_attribution")
    assert str(tmp_path / "iteration_0002" / "fixed" / run.name) in attribution["command"]
    case_windows = next(step for step in full if step["name"] == "source_aligned_case_windows")
    assert "--attribution-csv" in case_windows["command"]
    assert "--tracks" not in case_windows["command"]


def test_subprocess_logs_and_fail_fast_manifest(tmp_path):
    iteration = tmp_path / "iteration_0001"
    iteration.mkdir()
    manifest = {"status": "RUNNING", "steps": []}
    steps = [
        {"name": "first", "command": [sys.executable, "-c",
         "import sys; print('stdout evidence'); print('stderr evidence', file=sys.stderr)"]},
        {"name": "stop_here", "command": [sys.executable, "-c", "raise SystemExit(7)"]},
        {"name": "must_not_run", "command": [sys.executable, "-c", "raise SystemExit(0)"]},
    ]
    assert execute_steps(steps, iteration, manifest) == 7
    recorded = json.loads((iteration / "manifest.json").read_text(encoding="utf-8"))
    assert recorded["status"] == "FAILED"
    assert recorded["failed_step"] == "stop_here"
    assert [step["status"] for step in recorded["steps"]] == ["PASSED", "FAILED"]
    assert "stdout evidence" in (iteration / "logs" / "first.stdout.log").read_text(encoding="utf-8")
    assert "stderr evidence" in (iteration / "logs" / "first.stderr.log").read_text(encoding="utf-8")


def test_repeat_variance_writes_json_and_csv_comparison(tmp_path):
    repeat_1 = tmp_path / "repeat_1"
    repeat_2 = tmp_path / "repeat_2"
    repeat_1.mkdir()
    repeat_2.mkdir()
    (repeat_1 / "baseline_vs_candidate.csv").write_text(
        "provider,mock_pressed,compute_ms_mean\nv85,10,20.0\n", encoding="utf-8")
    (repeat_2 / "baseline_vs_candidate.csv").write_text(
        "provider,mock_pressed,compute_ms_mean\nv85,8,22.0\n", encoding="utf-8")

    output = tmp_path / "comparison"
    repeat_variance_report(repeat_1, repeat_2, output)
    report = json.loads((output / "measured_repeat_comparison.json").read_text(encoding="utf-8"))
    metrics = {row["metric"]: row for row in report["providers"]["v85"]}
    assert metrics["mock_pressed"]["repeat_2_minus_repeat_1"] == -2
    assert metrics["compute_ms_mean"]["relative_delta_percent"] == 10
    assert (output / "measured_repeat_comparison.csv").is_file()

