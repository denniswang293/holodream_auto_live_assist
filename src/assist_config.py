"""Resolve source-first Assist configuration with explicit override provenance."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from .assist_defaults import DEFAULTS_VERSION, builtin_defaults
from .assist_profiles import apply_profile


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


def resolve_config(*, profile="stable", config_path: Path | None = None,
                   live_config_path: Path | None = None) -> EffectiveConfig:
    config = apply_profile(builtin_defaults(), profile)
    source_map = {key: "builtin" for key in config}
    source_map["profile"] = "profile"
    legacy_override = False
    if config_path is not None:
        config_override = _load(config_path)
        config = _deep_merge(config, config_override)
        legacy_override = True
        for key in config_override:
            source_map[key] = "explicit_override"
    if live_config_path is not None:
        live_override = _load(live_config_path)
        config["live"] = _deep_merge(config.get("live", {}), live_override)
        legacy_override = True
        source_map["live"] = "explicit_override"
    validate_effective_config(config)
    live = config["live"]
    experiment = live.get("experiment", {}) or {}
    label = f"timing-lead-{float(live['global_tap_timing']['input_lead_ms']):g}ms"
    live["global_tap_timing"]["ab_label"] = label
    live.setdefault("diagnostics", {})["timing_ab_label"] = label
    config.setdefault("diagnostics", {})["timing_ab_label"] = label
    metadata = {
        "profile_name": experiment.get("profile_name", profile),
        "defaults_version": DEFAULTS_VERSION,
        "source_mode": "legacy_override" if legacy_override else "source_first",
        "source_map": source_map,
        "effective_config_sha256": effective_fingerprint(config),
        "experiment_id": experiment.get("experiment_id", "v7148_tap_earlier_amend_ab"),
        "variant": experiment.get("variant", profile),
        "input_lead_ms": live["global_tap_timing"]["input_lead_ms"],
        "allow_earlier_amend": live["tap_deadline_amend"]["allow_earlier_amend"],
        "hold_start_delay_ms": live.get("hold_visual", {}).get("start_delay_ms", 0.0),
    }
    return EffectiveConfig(config=deepcopy(config), metadata=metadata)
