import json

from tools.compare_v7147_ab import compare
from tools.prepare_v7147_ab import _variant


def test_v7147_variants_change_only_earlier_amend_flag(tmp_path):
    base = tmp_path / "live.json"
    base.write_text(json.dumps({
        "global_tap_timing": {"input_lead_ms": 60.0},
        "tap_deadline_amend": {"enabled": True, "freeze_window_ms": 30,
                                "max_amend_step_ms": 40, "max_total_amend_ms": 80,
                                "allow_earlier_amend": False},
        "tap_rule": {"geometry_sha256": "g"},
    }), encoding="utf-8")
    baseline = _variant(base, variant="baseline", allow_earlier=False)
    experiment = _variant(base, variant="experiment", allow_earlier=True)
    assert baseline["global_tap_timing"]["input_lead_ms"] == 60.0
    assert experiment["global_tap_timing"]["input_lead_ms"] == 60.0
    assert baseline["tap_deadline_amend"]["allow_earlier_amend"] is False
    assert experiment["tap_deadline_amend"]["allow_earlier_amend"] is True
    assert experiment["tap_deadline_amend"]["freeze_window_ms"] == 30
    assert experiment["tap_deadline_amend"]["max_amend_step_ms"] == 40
    assert experiment["tap_deadline_amend"]["max_total_amend_ms"] == 80


def test_v7147_compare_without_runs_is_explicitly_awaiting_user_runs(tmp_path):
    result = compare([], [], tmp_path)
    assert result["status"] == "AWAITING_USER_RUNS"
    text = (tmp_path / "v7147_ab_comparison.md").read_text(encoding="utf-8")
    assert "AWAITING_USER_RUNS" in text
