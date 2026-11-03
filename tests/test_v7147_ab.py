import json
import pytest

from tools.compare_v7147_ab import compare
from tools.prepare_v7147_ab import _variant
from src.assist_config import resolve_config


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


def test_source_first_profiles_differ_only_in_earlier_flag():
    stable = resolve_config(profile="stable").config
    earlier = resolve_config(profile="tap-earlier").config
    stable["live"].pop("experiment", None)
    earlier["live"].pop("experiment", None)
    stable["live"]["tap_deadline_amend"]["allow_earlier_amend"] = None
    earlier["live"]["tap_deadline_amend"]["allow_earlier_amend"] = None
    assert stable == earlier


def test_explicit_nested_override_preserves_safety_limits(tmp_path):
    live = tmp_path / "override.json"
    live.write_text(json.dumps({"tap_deadline_amend": {"allow_earlier_amend": False}}), encoding="utf-8")
    resolved = resolve_config(profile="tap-earlier", live_config_path=live)
    amend = resolved.config["live"]["tap_deadline_amend"]
    assert resolved.metadata["source_mode"] == "legacy_override"
    assert amend["allow_earlier_amend"] is False
    assert amend["freeze_window_ms"] == 30
    assert amend["max_amend_step_ms"] == 40
    assert amend["max_total_amend_ms"] == 80


def test_unsafe_override_fails_closed(tmp_path):
    live = tmp_path / "unsafe.json"
    live.write_text(json.dumps({"max_input_lateness_ms": 100}), encoding="utf-8")
    with pytest.raises(ValueError, match="max_input_lateness_ms"):
        resolve_config(profile="stable", live_config_path=live)
