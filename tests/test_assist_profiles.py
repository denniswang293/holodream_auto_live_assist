import json

import pytest

from src.assist_config import resolve_config


def test_default_profile_is_stable():
    resolved = resolve_config()
    assert resolved.metadata['profile_name'] == 'stable'
    amend = resolved.config['live']['tap_deadline_amend']
    assert amend['allow_earlier_amend'] is True
    assert (amend['freeze_window_ms'], amend['max_amend_step_ms'], amend['max_total_amend_ms']) == (30,40,80)
    assert resolved.config['live']['hold_visual']['start_delay_ms'] == 0


def test_stable_and_tap_earlier_share_bounded_timing():
    stable = resolve_config(profile='stable').config
    earlier = resolve_config(profile='tap-earlier').config
    stable['live'].pop('experiment', None)
    earlier['live'].pop('experiment', None)
    assert stable == earlier


def test_explicit_nested_override_preserves_safety_limits(tmp_path):
    live = tmp_path / 'override.json'
    live.write_text(json.dumps({'tap_deadline_amend': {'allow_earlier_amend': False}}),
                    encoding='utf-8')
    resolved = resolve_config(profile='tap-earlier', live_config_path=live)
    amend = resolved.config['live']['tap_deadline_amend']
    assert resolved.metadata['source_mode'] == 'legacy_override'
    assert amend['allow_earlier_amend'] is False
    assert amend['freeze_window_ms'] == 30
    assert amend['max_amend_step_ms'] == 40
    assert amend['max_total_amend_ms'] == 80


def test_unsafe_override_fails_closed(tmp_path):
    live = tmp_path / 'unsafe.json'
    live.write_text(json.dumps({'max_input_lateness_ms': 100}), encoding='utf-8')
    with pytest.raises(ValueError, match='max_input_lateness_ms'):
        resolve_config(profile='stable', live_config_path=live)


def test_reference_yellow_rail_profile_changes_only_detector_flag():
    stable = resolve_config(profile='stable').config
    experimental = resolve_config(profile='reference-yellow-rail').config
    assert stable['detector']['yellow_rail_recovery'] is False
    assert experimental['detector']['yellow_rail_recovery'] is True
    stable['detector'].pop('yellow_rail_recovery')
    experimental['detector'].pop('yellow_rail_recovery')
    assert stable == experimental


def test_yellow_rail_detector_flag_must_be_boolean(tmp_path):
    live = tmp_path / 'override.json'
    live.write_text(json.dumps({'detector': {'yellow_rail_recovery': 'true'}}), encoding='utf-8')
    with pytest.raises(ValueError, match='yellow_rail_recovery must be a boolean'):
        resolve_config(profile='stable', config_path=live)
