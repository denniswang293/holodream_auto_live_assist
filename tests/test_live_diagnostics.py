import csv
from contextlib import ExitStack

from src.live import (ACTION_FIELDS, DECISION_FIELDS, EVENT_FIELDS, INTENT_FIELDS,
                      CsvLog, _render_overlay_if_recording, actual_timing_ab_label)


def test_timing_label_is_derived_from_numeric_lead():
    assert actual_timing_ab_label(60) == "timing-lead-60ms"
    assert actual_timing_ab_label("10.0") == "timing-lead-10ms"
    assert actual_timing_ab_label(float("nan")) == "timing-lead-0ms"


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
    assert {"action", "reason", "timestamp", "event_id", "key", "lifecycle_state", "revision"}.issubset(ACTION_FIELDS)
    assert {"note_uid", "state", "reason"}.issubset(INTENT_FIELDS)


def test_batched_csv_flushes_short_tail_and_preserves_order(tmp_path):
    path = tmp_path / "batched.csv"
    log = CsvLog(path, ["n"], batch_size=64, batch_interval_s=60)
    log.write({"n": 1})
    log.write({"n": 2})
    log.close()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        assert [row["n"] for row in csv.DictReader(stream)] == ["1", "2"]


def test_batched_csv_flushes_when_exitstack_unwinds_after_error(tmp_path):
    path = tmp_path / "exception.csv"
    try:
        with ExitStack() as stack:
            log = CsvLog(path, ["n"], batch_size=64, batch_interval_s=60)
            stack.callback(log.close)
            log.write({"n": 7})
            raise RuntimeError("fixture failure")
    except RuntimeError:
        pass
    with path.open(newline="", encoding="utf-8-sig") as stream:
        assert [row["n"] for row in csv.DictReader(stream)] == ["7"]


def test_critical_action_log_remains_immediate(tmp_path):
    path = tmp_path / "actions.csv"
    log = CsvLog(path, ["action"], batch_size=1)
    log.write({"action": "armed"})
    log.close()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        assert next(csv.DictReader(stream))["action"] == "armed"


def test_overlay_is_not_rendered_without_recorder(monkeypatch):
    calls = []
    monkeypatch.setattr("src.live.draw_live_overlay",
                        lambda *args: calls.append(args) or "overlay")
    assert _render_overlay_if_recording(None, None, None, {}, None, 0) is None
    assert calls == []
    assert _render_overlay_if_recording(object(), None, None, {}, None, 0) == "overlay"
    assert len(calls) == 1
