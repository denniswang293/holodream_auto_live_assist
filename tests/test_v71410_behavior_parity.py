from types import SimpleNamespace

import pytest

from src.global_tap_timing import GlobalTapTimingEstimator
from src.simple_core import SimpleAssistCore


def _track(track_id, history):
    return SimpleNamespace(track_id=track_id, history=history, status="confirmed",
                           confirmed_note_type="tap", missed=0)


def test_stable_and_tap_earlier_policies_share_all_non_strategy_values():
    from src.assist_config import resolve_config
    stable = resolve_config(profile="stable").config
    earlier = resolve_config(profile="tap-earlier").config
    for config in (stable, earlier):
        config["live"]["tap_deadline_amend"]["allow_earlier_amend"] = None
    assert stable == earlier


def test_global_estimator_uses_last_observation_timestamp_for_hit_at():
    estimator = GlobalTapTimingEstimator({
        "enabled": True, "mode": "shadow", "min_tracks": 2,
        "min_samples": 3, "max_observation_age_ms": 180,
        "max_eta_s": .45,
    })
    first = _track(1, [(1.00, 100), (1.10, 110), (1.20, 120)])
    second = _track(2, [(1.00, 80), (1.10, 90), (1.20, 100)])
    assert estimator.update([first, second], trigger_y=130,
                            capture_timestamp=1.25, now=1.30).ready
    eta = estimator.estimate(first, trigger_y=130, now=1.35)
    assert eta.hit_at == pytest.approx(1.30)
    assert eta.observed_at == pytest.approx(1.20)


def test_source_first_resolves_without_reading_user_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    resolved = __import__("src.assist_config", fromlist=["resolve_config"]).resolve_config(
        profile="tap-earlier")
    assert resolved.metadata["source_mode"] == "source_first"
    assert resolved.config["key_map"] == ["S", "D", "F", "J", "K", "L"]
