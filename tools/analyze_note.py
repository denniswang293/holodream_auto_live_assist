"""Build an evidence-only timeline for one Simple Core track in a run folder."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def rows(path: Path):
    if not path.exists():
        return None
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def analyze(run: Path, track: str):
    suffix = str(track)
    event_rows = rows(run / "live_events.csv")
    action_rows = rows(run / "input_actions.csv") or rows(run / "live_key_actions.csv")
    decision_rows = rows(run / "tap_decisions.csv")
    if decision_rows is None:
        decision_rows = rows(run / "live_decision_trace.csv")
    matches = []
    insufficient = []
    for name, data in (("live_events.csv", event_rows), ("input_actions.csv", action_rows),
                       ("tap_decisions.csv", decision_rows)):
        if data is None:
            insufficient.append(f"missing:{name}")
            continue
        for row in data:
            identity = row.get("note_uid", "") or row.get("event_id", "")
            if identity.endswith(":" + suffix) or identity == suffix:
                if name == "live_events.csv":
                    matches.append({
                        "timestamp": row.get("capture_timestamp") or row.get("processing_timestamp", ""),
                        "source": name,
                        "frame": row.get("source_frame", ""),
                        "state": row.get("simple_core_state", ""),
                        "reason": row.get("simple_core_reason") or row.get("abstain_reason", ""),
                        "key": row.get("resolved_keys", ""),
                        "hit_at": row.get("predicted_hit_time", ""),
                        "observed_y": row.get("crossing_y", ""),
                        "eta_s": row.get("eta_p50_s", ""),
                        "details": row.get("particle_predicted_y", ""),
                    })
                elif name == "input_actions.csv":
                    matches.append({
                        "timestamp": row.get("timestamp", ""), "source": name,
                        "frame": "", "state": row.get("action", ""),
                        "reason": row.get("reason", ""), "key": row.get("key", ""),
                        "hit_at": row.get("scheduled_hit", ""), "observed_y": "",
                        "eta_s": "", "details": row.get("note_type", ""),
                    })
                else:
                    matches.append({
                        "timestamp": row.get("timestamp", ""), "source": name,
                        "frame": "", "state": row.get("lifecycle_state", ""),
                        "reason": row.get("reason", ""), "key": row.get("key", ""),
                        "hit_at": row.get("hit_at", ""), "observed_y": "",
                        "eta_s": row.get("eta_s", ""), "details": row.get("gates_json", ""),
                    })
    matches.sort(key=lambda row: (float(row["timestamp"]) if _number(row["timestamp"]) else float("inf"),
                                  row["source"], row["state"]))
    if not matches:
        insufficient.append(f"no_evidence_for_track:{suffix}")
    return matches, insufficient


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--track", required=True, help="track id or note_uid suffix")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.run.is_dir():
        parser.error(f"run directory does not exist: {args.run}")
    result, insufficient = analyze(args.run, args.track)
    destination = args.out or args.run / f"note_{args.track}_timeline.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp", "source", "frame", "state", "reason", "key", "hit_at",
              "observed_y", "eta_s", "details", "evidence_status"]
    with destination.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in result:
            writer.writerow({**row, "evidence_status": "OBSERVED"})
        if insufficient:
            writer.writerow({"state": "INSUFFICIENT_EVIDENCE", "reason": ";".join(insufficient),
                             "evidence_status": "INSUFFICIENT_EVIDENCE"})
    print(f"{destination}: {len(result)} evidence rows; " +
          ("; ".join(insufficient) if insufficient else "complete across available sources"))


if __name__ == "__main__":
    main()
