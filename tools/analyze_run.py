"""Create a compact, evidence-only V7.1 run report.

This intentionally counts note_uid outcomes rather than per-frame diagnostic rows.
It does not infer game hits from key_down actions.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


UNSCHEDULED_IDS = {
    "1000015", "1000036", "1000040", "1000102", "1000123", "1000146",
    "1000148", "1000167", "1000190", "1000208", "1000256", "1000265",
    "1000268", "1000278", "1000292", "1000293", "1000295",
}


def _read(path: Path):
    if not path.exists():
        return iter(())
    def stream_rows():
        with path.open("r", newline="", encoding="utf-8-sig") as stream:
            yield from csv.DictReader(stream)
    return stream_rows()


def _id(value: str) -> str:
    return value.rsplit(":", 1)[-1] if value else ""


def analyze(run: Path):
    events = defaultdict(lambda: {"states": [], "reasons": [], "timeline": [], "first": "", "last": "",
                                 "key": "", "hit_at": "", "track_id": ""})
    for row in _read(run / "tap_intents.csv"):
        uid = row.get("note_uid") or row.get("event_id")
        if not uid:
            continue
        item = events[uid]
        item["states"].append(row.get("state", ""))
        reason = row.get("reason", "")
        item["timeline"].append((row.get("timestamp", ""), row.get("state", ""), reason))
        if reason:
            item["reasons"].append(reason)
        item["first"] = item["first"] or row.get("timestamp", "")
        item["last"] = row.get("timestamp", "")
        item["key"] = item["key"] or row.get("key", "")
        item["hit_at"] = item["hit_at"] or row.get("predicted_hit_time", "")
        item["track_id"] = _id(uid)

    actions = defaultdict(list)
    for row in _read(run / "live_key_actions.csv"):
        uid = row.get("event_id", "")
        if uid:
            actions[uid].append(row)

    for uid, item in events.items():
        downs = [r for r in actions[uid] if r.get("action") == "key_down"]
        item["key_down"] = downs[0].get("timestamp", "") if downs else ""
        item["game_judgment"] = "UNVERIFIED"
        item["verdict"] = "FIRED" if downs else (
            "CONFIRMED_NOT_SCHEDULED" if "CONFIRMED" in item["states"] else "NO_FINAL_VERDICT")

    metrics = {}
    metrics_path = run / "run_metrics.json"
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8-sig"))
    return events, actions, metrics


def write_outputs(run: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    events, actions, metrics = analyze(run)
    rows = []
    for uid, item in sorted(events.items(), key=lambda pair: (int(_id(pair[0])) if _id(pair[0]).isdigit() else 10**12, pair[0])):
        rows.append({
            "note_uid": uid, "track_id": item["track_id"], "first_seen": item["first"],
            "last_observation": item["last"], "selected_key": item["key"],
            "predicted_hit_at": item["hit_at"], "key_down": item["key_down"],
            "states": "|".join(dict.fromkeys(item["states"])),
            "gate_failures": "|".join(dict.fromkeys(item["reasons"])),
            "game_judgment": item["game_judgment"], "physical_note_group": "UNRESOLVED",
            "verdict": item["verdict"], "verdict_confidence": "low",
        })
    fields = list(rows[0]) if rows else ["note_uid", "verdict"]
    with (out / "v7_1_note_cases.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    cases = [row for row in rows if row["track_id"] in UNSCHEDULED_IDS]
    lines = ["# V7.1 baseline report", "", f"Run: `{run}`", "",
             "Game judgment is unavailable; `FIRED` means a key_down was recorded, not a hit.",
             "Physical note groups remain `UNRESOLVED` unless manually reviewed.", "",
             "## Baseline metrics", ""]
    funnel = metrics.get("tap_lifecycle_transitions", {})
    for key in ("DETECTED", "CONFIRMED", "SCHEDULED", "FIRED", "CANCELED", "NOT_SCHEDULED"):
        lines.append(f"- {key}: {funnel.get(key, 'unavailable')}")
    for key in ("capture_fps", "processing_fps", "latency_p50_ms", "latency_p95_ms", "dropped_frames", "stale_frames"):
        if key in metrics:
            lines.append(f"- {key}: {metrics[key]}")
    lines += ["", "## Confirmed tracks without a recorded schedule", "",
              f"- Cases listed: {len(cases)} (track-level; not physical-note count)",
              "- Each case remains unverified until physical-note identity and game judgment are reviewed.", ""]
    (out / "v7_1_baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    timeline_fields = ["note_uid", "timestamp", "source", "state", "reason", "key", "hit_at"]
    with (out / "v7_1_timeline.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=timeline_fields)
        writer.writeheader()
        for uid, item in sorted(events.items()):
            for timestamp, state, reason in item["timeline"]:
                writer.writerow({"note_uid": uid, "timestamp": timestamp, "source": "tap_intents",
                                 "state": state, "reason": reason, "key": item["key"], "hit_at": item["hit_at"]})
    hold_rows = [r for r in actions.values() for r in r if r.get("note_type") == "hold"]
    hold_ids = sorted({r.get("event_id", "") for r in hold_rows})
    hold_canceled = sorted({r.get("event_id", "") + ":" + r.get("reason", "")
                            for r in hold_rows if r.get("action") == "canceled"})
    hold_lines = ["# V7.1 Hold suspects", "", f"Recorded Hold action rows: {len(hold_rows)}.",
                  f"Distinct Hold event IDs with action rows: {len(hold_ids)}.",
                  f"Canceled Hold rows: {', '.join(hold_canceled) if hold_canceled else 'none'}.",
                  "This report does not infer the 59–60.5s game MISS cause without video judgment matching.",
                  "A missing key_down would still need candidate, tracking, timing, scheduler, and game-judgment evidence.", ""]
    (out / "v7_1_hold_suspects.md").write_text("\n".join(hold_lines), encoding="utf-8")
    return len(rows), len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports"))
    args = parser.parse_args()
    if not args.run.is_dir():
        parser.error(f"run directory does not exist: {args.run}")
    total, cases = write_outputs(args.run, args.out)
    print(f"wrote {args.out}: {total} note cases, {cases} listed unscheduled cases")


if __name__ == "__main__":
    main()
