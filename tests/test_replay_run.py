import csv
import json

from tools.replay_run import replay


def test_replay_run_writes_note_fates_without_input(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    fields = ["event_id", "note_uid", "state", "reason", "timestamp", "key",
              "predicted_hit_time", "uncertainty_s", "gameplay_state"]
    with (run / "tap_intents.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"event_id": "s:1", "note_uid": "s:1", "state": "CONFIRMED",
                         "timestamp": "1"})
        writer.writerow({"event_id": "s:1", "note_uid": "s:1", "state": "SCHEDULED",
                         "timestamp": "2", "key": "F", "predicted_hit_time": "3"})
    action_fields = ["action", "reason", "timestamp", "event_id", "key", "scheduled_hit", "note_type"]
    with (run / "live_key_actions.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=action_fields)
        writer.writeheader()
        writer.writerow({"action": "key_down", "timestamp": "3.01", "event_id": "s:1", "key": "F"})
    (run / "run_metrics.json").write_text(json.dumps({}), encoding="utf-8")
    out = tmp_path / "out"
    replay(run, out)
    with (out / "note_fates.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["note_uid"] == "s:1"
    assert rows[0]["fired"] == "True"
    assert rows[0]["game_judgment"] == "UNVERIFIED"
