import csv

from src.live import (ACTION_FIELDS, DECISION_FIELDS, EVENT_FIELDS, INTENT_FIELDS,
                      CsvLog)


def test_tap_decision_csv_preserves_per_gate_and_key_conflict_trace(tmp_path):
    path = tmp_path / "tap_decisions.csv"
    row = {"timestamp": 1.0, "note_uid": "session:simple:4", "track_id": 4,
           "lifecycle_state": "ELIGIBLE", "reason": "", "key": "F",
           "eta_s": .2, "hit_at": 1.2, "uncertainty_s": .01,
           "gates_json": '{"track_confirmed_current":true}',
           "key_conflicts_json": '{"F":""}'}
    log = CsvLog(path, DECISION_FIELDS)
    try:
        log.write(row)
    finally:
        log.close()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        saved = next(csv.DictReader(stream))
    assert saved["note_uid"] == "session:simple:4"
    assert "track_confirmed_current" in saved["gates_json"]
    assert saved["key_conflicts_json"] == '{"F":""}'


def test_live_csv_schemas_keep_legacy_event_and_action_columns():
    assert {"event_id", "predicted_hit_time", "resolved_keys"}.issubset(EVENT_FIELDS)
    assert {"action", "reason", "timestamp", "event_id", "key"}.issubset(ACTION_FIELDS)
    assert {"note_uid", "state", "reason"}.issubset(INTENT_FIELDS)
