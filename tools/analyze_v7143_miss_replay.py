"""Deterministic before/after replay for the V7.14.3 Global uncertainty fix.

It replays only recorded matched observations into the Global model.  It does
not call a scheduler or actuator and treats eligibility as a diagnostic
candidate, not as a proven game hit.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict, Counter
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.global_tap_timing import GlobalTapTimingEstimator


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def flt(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def bbox_y(raw):
    try:
        box = json.loads(raw)
        return float(box[1]) + float(box[3]) / 2.0
    except (TypeError, ValueError, json.JSONDecodeError, IndexError):
        return None


def truthy(value):
    return str(value).lower() in {"1", "true", "yes"}


def run_replay(run_dir):
    identity = rows(run_dir / "live_track_identity.csv")
    old_global = rows(run_dir / "global_tap_timing_shadow.csv")
    intents = rows(run_dir / "tap_intents.csv")
    config_path = Path("config/live_assist.json")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    timing_cfg = dict(config.get("global_tap_timing", {}))
    timing_cfg.update({"enabled": True, "mode": "shadow"})
    modeler = GlobalTapTimingEstimator(timing_cfg)

    by_frame = defaultdict(list)
    tracks = {}
    for row in identity:
        capture = flt(row.get("capture_timestamp"))
        if capture is None:
            continue
        by_frame[(capture, row.get("capture_sequence", ""))].append(row)
    before = defaultdict(lambda: {"old_available": None, "old_eligible": None,
                                  "old_uncertainty": 0, "old_near_uncertainty": None,
                                  "old_reasons": Counter()})
    for row in old_global:
        uid = row.get("note_uid", "")
        if not uid:
            continue
        capture = flt(row.get("capture_timestamp"))
        status = row.get("eta_status", "")
        reason = row.get("planner_reason") or row.get("eta_reason") or ""
        before[uid]["old_reasons"][reason] += 1
        if status == "AVAILABLE" and before[uid]["old_available"] is None:
            before[uid]["old_available"] = capture
        if row.get("planner_status") == "schedule" and before[uid]["old_eligible"] is None:
            before[uid]["old_eligible"] = capture
        uncertainty = flt(row.get("uncertainty_s"))
        if uncertainty is not None:
            before[uid]["old_uncertainty"] = max(before[uid]["old_uncertainty"], uncertainty)
            observed_y = flt(row.get("observed_y"))
            eta_s = flt(row.get("eta_s"))
            if (observed_y is not None and observed_y >= 270) or (eta_s is not None and eta_s <= .45):
                before[uid]["old_near_uncertainty"] = uncertainty
    for row in intents:
        uid = row.get("note_uid", "")
        if uid:
            state = row.get("state", "")
            before[uid].setdefault("states", Counter())[state] += 1

    after = defaultdict(lambda: {"new_available": None, "new_eligible": None,
                                 "new_reasons": Counter(), "max_uncertainty": 0.0})
    ordered = sorted(by_frame.items(), key=lambda item: (item[0][0], item[0][1]))
    for (capture, _), frame_rows in ordered:
        current_ids = set()
        for row in frame_rows:
            track_id = row.get("track_id", "")
            uid = row.get("note_uid", "")
            y = bbox_y(row.get("bbox", ""))
            if not track_id or y is None:
                continue
            try:
                numeric_id = int(track_id)
            except ValueError:
                continue
            state = row.get("track_status", "")
            track = tracks.setdefault(numeric_id, SimpleNamespace(
                track_id=numeric_id, history=[], status="tentative",
                confirmed_note_type=None, missed=0, note_uid=uid))
            if truthy(row.get("matched_this_frame")) and truthy(row.get("real_observation_this_frame")):
                track.history.append((capture, y))
                track.history = track.history[-24:]
            track.status = state
            track.confirmed_note_type = ("tap" if row.get("confirmed_note_type") == "tap" else None)
            track.missed = int(flt(row.get("missed_frames")) or 0)
            track.note_uid = uid or track.note_uid
            if state in {"confirmed", "tentative"}:
                current_ids.add(numeric_id)
        active = [track for track_id, track in tracks.items() if track_id in current_ids]
        modeler.update(active, trigger_y=325.5, capture_timestamp=capture,
                       now=capture, playing=True)
        for track in active:
            uid = track.note_uid
            if not uid or track.status != "confirmed" or track.confirmed_note_type != "tap":
                continue
            eta = modeler.estimate(track, trigger_y=295.5,
                                   physical_hit_y=325.5, now=capture)
            after[uid]["new_reasons"][eta.reason] += 1
            if eta.uncertainty_s is not None:
                after[uid]["max_uncertainty"] = max(after[uid]["max_uncertainty"], eta.uncertainty_s)
                observed_y = track.history[-1][1] if track.history else None
                if (observed_y is not None and observed_y >= 270) or (eta.eta_s is not None and eta.eta_s <= .45):
                    after[uid]["near_uncertainty"] = eta.uncertainty_s
            if eta.status == "AVAILABLE" and after[uid]["new_available"] is None:
                after[uid]["new_available"] = capture
            if (eta.status == "AVAILABLE" and eta.hit_at is not None and
                    eta.hit_at > capture and eta.eta_s is not None and eta.eta_s <= .45 and
                    eta.uncertainty_s is not None and eta.uncertainty_s <= .04 and
                    after[uid]["new_eligible"] is None):
                after[uid]["new_eligible"] = capture
    action_rows = rows(run_dir / "input_actions.csv")
    video_rows = rows(run_dir / "live_video_index.csv")
    base = min((flt(r.get("capture_timestamp")) for r in video_rows
                if flt(r.get("capture_timestamp")) is not None), default=None)
    if base is None:
        base = min((flt(r.get("capture_timestamp")) for r in identity
                    if flt(r.get("capture_timestamp")) is not None), default=None)
    windows = [(13.7, 14.3), (35.5, 36.2), (41.8, 42.2)]
    miss_windows = []
    for start, end in windows:
        selected = [r for r in action_rows if r.get("action") == "key_down" and
                    base is not None and flt(r.get("timestamp")) is not None and
                    start <= flt(r.get("timestamp")) - base <= end]
        miss_windows.append({"window_s": f"{start:.1f}-{end:.1f}",
                             "key_down_count": len(selected),
                             "keys": "|".join(r.get("key", "") for r in selected),
                             "classification": "UNRESOLVED"})
    all_uids = sorted(set(before) | set(after))
    output = []
    for uid in all_uids:
        b, a = before[uid], after[uid]
        output.append({
            "note_uid": uid,
            "confirmed_rows": b.get("states", {}).get("CONFIRMED", 0),
            "old_first_available": b.get("old_available") or "",
            "new_first_available": a.get("new_available") or "",
            "old_first_eligible": b.get("old_eligible") or "",
            "new_first_eligible": a.get("new_eligible") or "",
            "old_near_uncertainty_s": b.get("old_near_uncertainty") or "",
            "new_near_uncertainty_s": a.get("near_uncertainty") or "",
            "old_reason_top": b.get("old_reasons", Counter()).most_common(1)[0][0] if b.get("old_reasons") else "",
            "new_reason_top": a.get("new_reasons", Counter()).most_common(1)[0][0] if a.get("new_reasons") else "",
            "old_scheduled": b.get("states", {}).get("SCHEDULED", 0) > 0,
            "old_fired": b.get("states", {}).get("FIRED", 0) > 0,
            "game_result": "UNKNOWN",
        })
    csv_path = run_dir / "v7143_uid_before_after.csv"
    fields = list(output[0]) if output else ["note_uid"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); writer.writerows(output)
    report_path = run_dir / "v7143_miss_root_cause.md"
    lines = ["# V7.14.3 Global miss root-cause replay", "",
             f"Run: `{run_dir}`", "",
             "Replay uses recorded matched observations and capture timestamps; it does not send input.",
             "FIRED/key_down and replay eligibility are not game HIT evidence; game result remains **UNKNOWN**.", "",
             f"UID rows: {len(output)}", f"New replay first-available UID count: {sum(bool(row['new_first_available']) for row in output)}",
             f"New replay first-eligible UID count: {sum(bool(row['new_first_eligible']) for row in output)}", "",
             "## Candidate game-MISS windows", "",
             "| window | key_down count | keys | classification |", "|---|---:|---|---|"]
    for row in miss_windows:
        lines.append(f"| {row['window_s']} | {row['key_down_count']} | {row['keys']} | {row['classification']} |")
    lines += ["", "## Interpretation", "",
              "The three windows require visual frame review against the supplied video before any NO_INPUT or timing classification.",
              "Rows with an improved replay eligibility are candidate scheduling evidence only; they do not authorize bypassing uncertainty, key, Hold, focus, or stale gates.",
              f"Per-UID CSV: `{csv_path.name}`"]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"csv": str(csv_path), "report": str(report_path),
            "uid_count": len(output), "miss_windows": miss_windows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_replay(args.run_dir), indent=2))


if __name__ == "__main__":
    main()
