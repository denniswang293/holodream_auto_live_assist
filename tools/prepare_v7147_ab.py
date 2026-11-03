"""Create opt-in V7.14.7 Tap amendment A/B configs.

Both variants keep the 60 ms lead and every existing safety limit.  Only
``allow_earlier_amend`` differs.  The generated files are live-config
documents for ``--live-config``; the formal config/live_assist.json remains
the baseline.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _variant(base, *, variant, allow_earlier):
    config = json.loads(base.read_text(encoding="utf-8-sig"))
    global_cfg = config.setdefault("global_tap_timing", {})
    amend_cfg = config.setdefault("tap_deadline_amend", {})
    # The experiment is deliberately one variable: preserve the active 60 ms
    # numeric lead and all existing gates/limits.
    global_cfg["input_lead_ms"] = 60.0
    amend_cfg["allow_earlier_amend"] = bool(allow_earlier)
    experiment_id = "v7147_tap_earlier_amend_ab"
    label = f"{experiment_id}:{variant}:lead-60ms"
    config["experiment"] = {
        "experiment_id": experiment_id,
        "variant": variant,
        "input_lead_ms": 60.0,
        "allow_earlier_amend": bool(allow_earlier),
        "geometry_sha256": config.get("tap_rule", {}).get("geometry_sha256", "UNKNOWN"),
        "ab_label": label,
    }
    config.setdefault("diagnostics", {})["timing_ab_label"] = label
    global_cfg["ab_label"] = label
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path("config/live_assist.json"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "baseline_60ms_no_earlier.json": _variant(args.base, variant="baseline", allow_earlier=False),
        "experiment_60ms_earlier.json": _variant(args.base, variant="experiment", allow_earlier=True),
    }
    for name, data in outputs.items():
        path = args.out_dir / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
