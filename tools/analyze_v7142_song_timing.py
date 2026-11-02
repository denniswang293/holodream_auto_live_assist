"""Create a conservative V7.14.2 paired run summary.

The comparison is lifecycle/geometry evidence only.  It deliberately labels
game accuracy UNKNOWN because the Assist logs do not contain independent game
judgement labels.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def read_rows(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def summarize(run_dir):
    intents = read_rows(run_dir / "tap_intents.csv")
    actions = read_rows(run_dir / "input_actions.csv")
    global_rows = read_rows(run_dir / "global_tap_timing_shadow.csv")
    states = Counter(row.get("state", "") for row in intents)
    action_counts = Counter(row.get("action", "") for row in actions)
    eta_status = Counter(row.get("eta_status", "") for row in global_rows)
    source = Counter(row.get("model_source", "") for row in global_rows)
    groups = {row.get("timing_group_id") for row in global_rows
              if row.get("timing_group_id")}
    return {
        "run_dir": str(run_dir),
        "confirmed_uids": states.get("CONFIRMED", 0),
        "scheduled_uids": states.get("SCHEDULED", 0),
        "fired_uids": states.get("FIRED", 0),
        "not_scheduled_rows": states.get("NOT_SCHEDULED", 0),
        "key_down_rows": action_counts.get("key_down", 0),
        "amend_rows": action_counts.get("amended", 0),
        "global_available_rows": eta_status.get("AVAILABLE", 0),
        "global_not_ready_rows": eta_status.get("NOT_READY", 0),
        "global_rejected_rows": eta_status.get("REJECTED", 0),
        "profile_rows": source.get("global_profile", 0),
        "bootstrap_rows": source.get("global_bootstrap", 0),
        "timing_groups": len(groups),
        "game_accuracy": "UNKNOWN",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--compare-run-dir", type=Path)
    args = parser.parse_args()
    rows = [summarize(args.run_dir)]
    if args.compare_run_dir:
        rows.append(summarize(args.compare_run_dir))
    out_dir = args.run_dir
    csv_path = out_dir / "v7142_song_timing_comparison.csv"
    fields = list(rows[0])
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report_path = out_dir / "v7142_song_timing_comparison.md"
    lines = ["# V7.14.2 song timing paired evidence", "",
             "This compares captured lifecycle and timing diagnostics only; game accuracy is **UNKNOWN**.", "",
             "| run | confirmed | scheduled | fired | key_down rows | Global AVAILABLE | profile rows | bootstrap rows | timing groups |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append("| `{}` | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            row["run_dir"], row["confirmed_uids"], row["scheduled_uids"], row["fired_uids"],
            row["key_down_rows"], row["global_available_rows"], row["profile_rows"],
            row["bootstrap_rows"], row["timing_groups"]))
    lines += ["", "`FIRED` and `key_down` are not game HIT/Perfect evidence.",
              f"CSV: `{csv_path.name}`"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"csv": str(csv_path), "report": str(report_path), "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
