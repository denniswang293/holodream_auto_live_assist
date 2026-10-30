import csv
import json
from pathlib import Path

from tools.analyze_run import analyze, write_outputs


def _csv(path: Path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_analyze_run_counts_note_uids_not_transition_rows(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    _csv(run / "tap_intents.csv",
         ["event_id", "note_uid", "state", "reason", "timestamp", "key", "predicted_hit_time"],
         [{"event_id": "s:1", "note_uid": "s:1", "state": "CONFIRMED", "reason": "", "timestamp": "1", "key": "", "predicted_hit_time": ""},
          {"event_id": "s:1", "note_uid": "s:1", "state": "NOT_SCHEDULED", "reason": "eta_unavailable", "timestamp": "2", "key": "", "predicted_hit_time": ""},
          {"event_id": "s:1", "note_uid": "s:1", "state": "SCHEDULED", "reason": "accepted", "timestamp": "3", "key": "F", "predicted_hit_time": "4"}])
    _csv(run / "live_key_actions.csv",
         ["action", "reason", "timestamp", "event_id", "key", "scheduled_hit", "note_type"],
         [{"action": "key_down", "reason": "", "timestamp": "4.01", "event_id": "s:1", "key": "F", "scheduled_hit": "4", "note_type": "tap"}])
    (run / "run_metrics.json").write_text(json.dumps({"tap_lifecycle_transitions": {"NOT_SCHEDULED": 1}}), encoding="utf-8")
    events, actions, _ = analyze(run)
    assert len(events) == 1
    assert events["s:1"]["verdict"] == "FIRED"
    out = tmp_path / "reports"
    total, cases = write_outputs(run, out)
    assert (total, cases) == (1, 0)
    assert (out / "v7_1_note_cases.csv").exists()
