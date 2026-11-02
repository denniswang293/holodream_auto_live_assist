"""Create an explicit, non-active live config for one Tap lead A/B run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lead-ms", type=float, required=True, choices=(0.0, 10.0, 20.0, 30.0))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base", type=Path, default=Path("config/live_assist.json"))
    args = parser.parse_args()
    config = json.loads(args.base.read_text(encoding="utf-8-sig"))
    config["global_tap_timing"]["input_lead_ms"] = args.lead_ms
    config["global_tap_timing"]["ab_label"] = f"V7.14.3-lead-{args.lead_ms:g}ms"
    config.setdefault("diagnostics", {})["timing_ab_label"] = config["global_tap_timing"]["ab_label"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
