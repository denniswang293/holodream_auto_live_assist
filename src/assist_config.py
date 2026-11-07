"""Resolve the Assist settings with validated optional JSON overrides."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from .assist_defaults import DEFAULTS_VERSION, builtin_defaults


@dataclass(frozen=True)
class EffectiveConfig:
    config: dict
    metadata: dict


def _deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _load(path: Path | None) -> dict:
    if path is None:
        return {}
    if not path.exists():
        raise ValueError(f"explicit config override does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid config override {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"config override must be a JSON object: {path}")
    return value


def _number(value, name, *, minimum=None, maximum=None):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error
    if not math.isfinite(number) or (minimum is not None and number < minimum) or (maximum is not None and number > maximum):
        raise ValueError(f"{name} is outside the fail-closed range")
    return number


def validate_effective_config(config: dict) -> None:
    if config.get("key_map") != ["S", "D", "F", "J", "K", "L"]:
        raise ValueError("key_map must remain the verified S,D,F,J,K,L mapping")
    detector = config.get("detector")
    if not isinstance(detector, dict) or not isinstance(detector.get("yellow_rail_recovery", False), bool):
        raise ValueError("detector.yellow_rail_recovery must be a boolean")
    live = config.get("live")
    if not isinstance(live, dict):
        raise ValueError("live Assist configuration is missing")
    amend = live.get("tap_deadline_amend")
    global_timing = live.get("global_tap_timing")
    if not isinstance(amend, dict) or not isinstance(global_timing, dict):
        raise ValueError("tap amendment and global timing settings are required")
    for path in (("tap_deadline_amend", "enabled"), ("tap_deadline_amend", "allow_earlier_amend"),
                 ("global_tap_timing", "enabled"), ("global_tap_timing", "allow_active")):
        value = live[path[0]].get(path[1])
        if not isinstance(value, bool):
            raise ValueError(f"live.{path[0]}.{path[1]} must be a boolean")
    guarded_enabled = global_timing.get("guarded_reuse_enabled", False)
    if not isinstance(guarded_enabled, bool):
        raise ValueError("live.global_tap_timing.guarded_reuse_enabled must be a boolean")
    _number(global_timing.get("guarded_reuse_max_age_ms", 80),
            "live.global_tap_timing.guarded_reuse_max_age_ms", minimum=0, maximum=80)
    _number(live.get("max_frame_age_ms"), "live.max_frame_age_ms", maximum=60)
    _number(live.get("max_input_lateness_ms"), "live.max_input_lateness_ms", maximum=15)
    _number(live.get("input_advance_px"), "live.input_advance_px", minimum=0, maximum=30)
    _number(live.get("hold_visual", {}).get("start_delay_ms", 0),
            "live.hold_visual.start_delay_ms", minimum=0, maximum=20)
    if not isinstance(live.get("hold_visual", {}).get("tail_identity_guard", True), bool):
        raise ValueError("live.hold_visual.tail_identity_guard must be a boolean")
    if not isinstance(live.get("hold_visual", {}).get("head_measurement_guard", True), bool):
        raise ValueError("live.hold_visual.head_measurement_guard must be a boolean")
    hold_visual = live.get("hold_visual", {})
    if not isinstance(hold_visual.get("linked_tail_caps", True), bool):
        raise ValueError("live.hold_visual.linked_tail_caps must be a boolean")
    if not isinstance(hold_visual.get("robust_tail_timing", True), bool):
        raise ValueError("live.hold_visual.robust_tail_timing must be a boolean")
    if not isinstance(hold_visual.get("use_tail_path_evidence", True), bool):
        raise ValueError("live.hold_visual.use_tail_path_evidence must be a boolean")
    if not isinstance(hold_visual.get("tail_component_ownership", True), bool):
        raise ValueError("live.hold_visual.tail_component_ownership must be a boolean")
    if not isinstance(hold_visual.get("release_on_tail_only", False), bool):
        raise ValueError("live.hold_visual.release_on_tail_only must be a boolean")
    if (hold_visual.get("release_on_tail_only", False) and
            not hold_visual.get("tail_identity_guard", True)):
        raise ValueError("release_on_tail_only requires tail_identity_guard")
    _number(amend.get("freeze_window_ms"), "live.tap_deadline_amend.freeze_window_ms", minimum=30)
    _number(amend.get("max_amend_step_ms"), "live.tap_deadline_amend.max_amend_step_ms", minimum=0, maximum=40)
    _number(amend.get("max_total_amend_ms"), "live.tap_deadline_amend.max_total_amend_ms", minimum=0, maximum=80)
    _number(global_timing.get("input_lead_ms"), "live.global_tap_timing.input_lead_ms", minimum=0, maximum=200)
    _number(global_timing.get("max_uncertainty_s"), "live.global_tap_timing.max_uncertainty_s", maximum=0.04)
    _number(global_timing.get("max_eta_s"), "live.global_tap_timing.max_eta_s", maximum=0.45)
    if live.get("keyboard_input_mode") not in {"scan_code", "virtual_key"}:
        raise ValueError("live.keyboard_input_mode is invalid")


def effective_fingerprint(config: dict) -> str:
    encoded = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_config(*, config_path: Path | None = None) -> EffectiveConfig:
    config = builtin_defaults()
    source_map = {key: "builtin" for key in config}
    has_override = False
    if config_path is not None:
        config_override = _load(config_path)
        config = _deep_merge(config, config_override)
        has_override = True
        for key in config_override:
            source_map[key] = "explicit_override"
    validate_effective_config(config)
    live = config["live"]
    label = f"timing-lead-{float(live['global_tap_timing']['input_lead_ms']):g}ms"
    live["global_tap_timing"]["ab_label"] = label
    live.setdefault("diagnostics", {})["timing_ab_label"] = label
    config.setdefault("diagnostics", {})["timing_ab_label"] = label
    metadata = {
        "profile_name": "assist",
        "defaults_version": DEFAULTS_VERSION,
        "source_mode": "override" if has_override else "builtin",
        "source_map": source_map,
        "effective_config_sha256": effective_fingerprint(config),
        "experiment_id": "assist",
        "variant": "assist",
        "input_lead_ms": live["global_tap_timing"]["input_lead_ms"],
        "allow_earlier_amend": live["tap_deadline_amend"]["allow_earlier_amend"],
        "hold_start_delay_ms": live.get("hold_visual", {}).get("start_delay_ms", 0.0),
    }
    return EffectiveConfig(config=deepcopy(config), metadata=metadata)
