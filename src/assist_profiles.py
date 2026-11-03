"""Named, auditable Tap profiles."""
from __future__ import annotations

from copy import deepcopy

from .assist_defaults import builtin_defaults


PROFILES = {
    "stable": {"allow_earlier_amend": False, "description": "60ms baseline; conservative deadline amendments"},
    "tap-earlier": {"allow_earlier_amend": True, "description": "60ms candidate; earlier amendments are opt-in"},
}


def profile_names():
    return tuple(PROFILES)


def apply_profile(config: dict, name: str) -> dict:
    if name not in PROFILES:
        raise ValueError(f"unknown Assist profile: {name}; choose stable or tap-earlier")
    result = deepcopy(config)
    amend = result.setdefault("live", {}).setdefault("tap_deadline_amend", {})
    amend["allow_earlier_amend"] = bool(PROFILES[name]["allow_earlier_amend"])
    result.setdefault("live", {}).setdefault("global_tap_timing", {})["input_lead_ms"] = 60.0
    return result


def profile_config(name: str) -> dict:
    return apply_profile(builtin_defaults(), name)
