"""Named, auditable Tap profiles."""
from __future__ import annotations

from copy import deepcopy

from .assist_defaults import builtin_defaults


PROFILES = {
    "stable": {"allow_earlier_amend": True, "description": "60ms lead; bounded deadline corrections in both directions"},
    "tap-earlier": {"allow_earlier_amend": True, "description": "compatibility alias for stable bounded corrections"},
    "stable-global-rescue": {"allow_earlier_amend": False,
                              "guarded_reuse_enabled": True,
                              "description": "stable timing with guarded last-good Global profile reuse"},
    "timing-balance": {"allow_earlier_amend": True,
                       "hold_start_delay_ms": 15.0,
                       "description": "bounded earlier Tap amendments and 15ms later Hold start"},
    "reference-yellow-rail": {"allow_earlier_amend": True,
                              "description": "stable timing with bounded yellow head recovery at the judgment rail"},
}


def profile_names():
    return tuple(PROFILES)


def apply_profile(config: dict, name: str) -> dict:
    if name not in PROFILES:
        raise ValueError(f"unknown Assist profile: {name}; choose {', '.join(PROFILES)}")
    result = deepcopy(config)
    amend = result.setdefault("live", {}).setdefault("tap_deadline_amend", {})
    amend["allow_earlier_amend"] = bool(PROFILES[name]["allow_earlier_amend"])
    global_cfg = result.setdefault("live", {}).setdefault("global_tap_timing", {})
    global_cfg["input_lead_ms"] = 60.0
    global_cfg["guarded_reuse_enabled"] = bool(PROFILES[name].get("guarded_reuse_enabled", False))
    global_cfg["guarded_reuse_max_age_ms"] = 80.0
    hold_cfg = result.setdefault("live", {}).setdefault("hold_visual", {})
    hold_cfg["start_delay_ms"] = float(PROFILES[name].get("hold_start_delay_ms", 0.0))
    if name == "timing-balance":
        result["live"].setdefault("experiment", {})["experiment_id"] = "hud_combo_timing_balance_20261103"
    result.setdefault("detector", {})["yellow_rail_recovery"] = name == "reference-yellow-rail"
    return result


def profile_config(name: str) -> dict:
    return apply_profile(builtin_defaults(), name)
