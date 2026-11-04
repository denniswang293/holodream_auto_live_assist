from collections import Counter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import live


def test_no_logs_does_not_create_output_directory(monkeypatch, tmp_path):
    create = Mock(side_effect=AssertionError("must not create output"))
    monkeypatch.setattr(live, "new_run_directory", create)
    assert live._output_directory(SimpleNamespace(out=tmp_path / "unused"), True) is None
    create.assert_not_called()
    assert not (tmp_path / "unused").exists()


def test_no_log_sink_preserves_scheduler_action_callback_behavior(capsys):
    key_log, input_log = live._NoLog(), live._NoLog()
    engine = Mock()
    counters = Counter()
    callback = live._make_action_logger(key_log, input_log, counters, {"engine": engine})

    callback({"action": "armed", "reason": "manual_toggle"})
    callback({"action": "key_down", "note_type": "tap", "key": "S"})

    engine.record_scheduler_action.assert_any_call({"action": "armed", "reason": "manual_toggle"})
    engine.record_scheduler_action.assert_any_call({"action": "key_down", "note_type": "tap", "key": "S"})
    assert counters == {"armed": 1, "key_down": 1}
    output = capsys.readouterr().out
    assert "INPUT armed: manual_toggle" in output
    assert "TAP sent: S" in output


def test_recording_and_no_logs_are_rejected():
    with pytest.raises(ValueError, match="cannot be used with --no-logs"):
        live.run(SimpleNamespace(no_logs=True, record_overlay=True))
