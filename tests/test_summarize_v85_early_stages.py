import csv
import math
import subprocess
import sys

from tools.summarize_v85_early_stages import FIELDS, summarize


def row(**updates):
    base = {
        "run_id": "run_test",
        "color": "cyan",
        "type_hint": "pending",
        "provider_local_replay_uid": "note:1",
        "first_candidate_at": "10",
        "confirmed_at": "12",
        "birth_motion_y": "20",
        "confirmed_y": "25",
        "commit_at": "13",
    }
    base.update(updates)
    return base


def test_summarize_groups_counts_joins_and_stage_metrics():
    rows = [
        row(provider_local_replay_uid="note:1", confirmed_at="12", confirmed_y="25",
            birth_motion_y="20", commit_at="13"),
        row(provider_local_replay_uid="UNJOINED", confirmed_at="14", confirmed_y="32",
            birth_motion_y="30", commit_at="17"),
        row(provider_local_replay_uid="", confirmed_at="", confirmed_y="", commit_at=""),
        row(provider_local_replay_uid="NOT_REPLAYED", run_id="run_other", color="yellow",
            confirmed_at="", confirmed_y="", commit_at=""),
    ]

    result = summarize(rows)
    assert len(result) == 2
    by_run = {item["run_id"]: item for item in result}
    first, second = by_run["run_test"], by_run["run_other"]
    assert first["run_id"] == "run_test"
    assert first["candidate_count"] == 3
    assert first["exact_replay_uid_join_count"] == 1
    assert first["confirmed_candidate_count"] == 2
    assert first["rows_with_commit_at"] == 2
    assert first["candidate_to_confirmation_seconds_p10"] == 2.2
    assert first["candidate_to_confirmation_seconds_p50"] == 3.0
    assert first["candidate_to_confirmation_seconds_p90"] == 3.8
    # confirmed_y - birth_motion_y (5 and 2), not birth_y.
    assert first["candidate_to_confirmation_y_delta_p10"] == 2.3
    assert first["candidate_to_confirmation_y_delta_p50"] == 3.5
    assert first["candidate_to_confirmation_y_delta_p90"] == 4.7
    assert first["candidate_to_first_commit_seconds_p10"] == 3.4
    assert first["candidate_to_first_commit_seconds_p50"] == 5.0
    assert first["candidate_to_first_commit_seconds_p90"] == 6.6
    assert first["confirmed_to_first_commit_seconds_p10"] == 1.2
    assert first["confirmed_to_first_commit_seconds_p50"] == 2.0
    assert first["confirmed_to_first_commit_seconds_p90"] == 2.8
    assert second["exact_replay_uid_join_count"] == 0
    assert second["confirmed_candidate_count"] == 0
    assert second["candidate_to_confirmation_seconds_p50"] == ""
    assert first["schedule_commit_spatial_delta_status"] == "NOT_AVAILABLE_IN_METRICS"
    assert first["ground_truth_status"] == "NOT_EVALUABLE_AUTOMATIC_TRACKS_ONLY"
    assert "replay-log timestamp only" in first["first_commit_timestamp_semantics"]


def test_missing_and_nonfinite_samples_are_blank():
    result = summarize([
        row(confirmed_at="NaN", confirmed_y="inf", birth_motion_y="20",
            commit_at="NaN", first_candidate_at="10"),
    ])[0]
    for field in FIELDS:
        if "_p" in field:
            assert result[field] == ""


def test_cli_writes_schema_from_synthetic_csv(tmp_path):
    source = tmp_path / "input.csv"
    output = tmp_path / "nested" / "output.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row()))
        writer.writeheader()
        writer.writerow(row())

    proc = subprocess.run(
        [sys.executable, "tools/summarize_v85_early_stages.py",
         "--input", str(source), "--output", str(output)],
        check=True, capture_output=True, text=True,
    )
    assert "(1 groups)" in proc.stdout
    with output.open(encoding="utf-8-sig", newline="") as handle:
        result = list(csv.DictReader(handle))
    assert len(result) == 1
    assert list(result[0]) == FIELDS
    assert math.isclose(float(result[0]["candidate_to_confirmation_y_delta_p50"]), 5.0)
