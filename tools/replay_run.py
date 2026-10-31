"""Offline, input-free replay of recorded decision/action timelines.

This replay does not call Windows input and does not rerun detection when the
recorded run lacks source frames. It reports that limitation explicitly.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

try:
    from .analyze_run import analyze, write_outputs
except ImportError:
    from analyze_run import analyze, write_outputs


CASES = ("18", "45", "13", "64", "61", "1000027", "1000060",
         "1000012", "1000026", "1000029", "1000032", "1000018")


def replay(run: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    total, _ = write_outputs(run, out)
    events, actions, metrics = analyze(run)
    fields = ["note_uid", "track_id", "first_seen", "last_seen", "confirmed",
              "eligible", "proposed", "scheduled", "amended_revisions",
              "canceled", "fired", "game_judgment", "root_cause", "evidence_refs"]
    rows = []
    for uid, item in events.items():
        states = item["states"]
        reasons = list(dict.fromkeys(item["reasons"]))
        action_rows = actions.get(uid, [])
        canceled_rows = [r for r in action_rows if r.get("action") == "canceled"]
        amended_rows = [r for r in action_rows if r.get("action") == "amended"]
        if canceled_rows:
            root_cause = canceled_rows[-1].get("reason") or "canceled"
        elif item["key_down"]:
            root_cause = "FIRED"
        else:
            root_cause = reasons[-1] if reasons else "UNRESOLVED"
        rows.append({
            "note_uid": uid, "track_id": item["track_id"], "first_seen": item["first"],
            "last_seen": item["last"], "confirmed": "CONFIRMED" in states,
            "eligible": "ELIGIBLE" in states or "SCHEDULED" in states,
            "proposed": bool(item["hit_at"]), "scheduled": "SCHEDULED" in states,
            "amended_revisions": max(sum(1 for s in states if s == "AMENDED"), len(amended_rows)),
            "canceled": "CANCELED" in states or bool(canceled_rows),
            "fired": bool(item["key_down"]), "game_judgment": "UNVERIFIED",
            "root_cause": root_cause,
            "evidence_refs": "tap_intents.csv;live_key_actions.csv",
        })
    with (out / "note_fates.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    suspect_ids = set(CASES)
    with (out / "suspect_timeline.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["note_uid", "timestamp", "state", "reason", "key", "hit_at"])
        for uid, item in events.items():
            if uid.rsplit(":", 1)[-1] not in suspect_ids:
                continue
            for timestamp, state, reason in item["timeline"]:
                writer.writerow([uid, timestamp, state, reason, item["key"], item["hit_at"]])
    source_present = (run / "live_source.mp4").exists() and (run / "live_video_index.csv").exists()
    report = ["# V7.2 offline replay", "", f"Run: `{run}`", "",
              f"Note fates: {total} unique note_uid records.",
              "Replay mode: recorded CSV timeline; Windows input was not called.",
              f"Source video/index available: `{source_present}`.",
              "Game judgments: UNVERIFIED; FIRED is not a hit.", "",
              "Fixed cases: " + ", ".join(CASES)]
    (out / "v72_replay.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path("reports/v72_replay"))
    args = parser.parse_args()
    if not args.run.is_dir():
        parser.error(f"run directory does not exist: {args.run}")
    replay(args.run, args.out)
    print(f"wrote offline replay to {args.out}")


if __name__ == "__main__":
    main()
