"""Build the V7.14.10 evidence set from the two available Assist runs.

This is deliberately source-first: it uses the monotonic capture timestamps
and software lifecycle/input records, and leaves physical game truth UNKNOWN
unless a reviewer supplies an unambiguous one-to-one label.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.assist_config import resolve_config


RUNS = {
    "tap-earlier": Path("output/run_20261103T095842_860336Z"),
    "stable": Path("output/run_20261103T100128_930576Z"),
}


def read_csv(path):
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def f(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _uid_from(row):
    return row.get("note_uid") or row.get("event_id") or ""


def _terminal_state(uid, actions, intents):
    """Prefer actual scheduler actions over later diagnostic NOT_SCHEDULED rows."""
    rows = actions.get(uid, [])
    if any(row.get("action") == "key_down" and row.get("note_type") == "tap" for row in rows):
        return "FIRED"
    if any(row.get("action") == "canceled" and row.get("note_type") == "tap" for row in rows):
        return "CANCELED"
    if any(row.get("action") == "abstain" and row.get("note_type") == "tap" for row in rows):
        return "EXPIRED"
    for row in reversed(intents.get(uid, [])):
        if row.get("state") in {"FIRED", "CANCELED", "EXPIRED"}:
            return row["state"]
    if any(row.get("state") == "PENDING" for row in intents.get(uid, [])):
        return "PENDING"
    if any(row.get("state") == "NOT_SCHEDULED" for row in intents.get(uid, [])):
        return "NOT_SCHEDULED"
    return "UNKNOWN"


def _primary_blocker(uid, intents, decisions, global_rows, actions, terminal):
    if terminal == "FIRED":
        return "FIRED_SOFTWARE_PATH"
    rows = intents.get(uid, [])
    reasons = [str(row.get("reason", "")) for row in rows if row.get("reason")]
    reasons += [str(row.get("reason", "")) for row in decisions.get(uid, []) if row.get("reason")]
    reasons += [str(row.get("eta_reason", "")) for row in global_rows.get(uid, []) if row.get("eta_reason")]
    lower = " ".join(reasons).lower()
    if any(row.get("action") == "canceled" for row in actions.get(uid, [])):
        return "SCHEDULER_CANCELED"
    if any(token in lower for token in ("stale", "expired", "past", "future")):
        return "ETA_OR_DEADLINE_GATE"
    if any(token in lower for token in ("uncertainty", "speed_variation", "not_ready", "prediction")):
        return "GLOBAL_ETA_GATE"
    if any(token in lower for token in ("conflict", "key")):
        return "PLANNER_OR_KEY_GATE"
    if any(token in lower for token in ("track", "confirmed", "motion")):
        return "TRACKER_CONFIRMATION_OR_CONTINUITY"
    return "UNKNOWN_BLOCKER"


def analyze_run(run_dir: Path, profile: str, out_dir: Path):
    actions_rows, _ = read_csv(run_dir / "input_actions.csv")
    intents_rows, _ = read_csv(run_dir / "tap_intents.csv")
    decisions_rows, _ = read_csv(run_dir / "tap_decisions.csv")
    global_rows_all, _ = read_csv(run_dir / "global_tap_timing_shadow.csv")
    index_rows, _ = read_csv(run_dir / "live_video_index.csv")
    actions = defaultdict(list)
    intents = defaultdict(list)
    decisions = defaultdict(list)
    global_rows = defaultdict(list)
    for row in actions_rows:
        uid = row.get("event_id", "")
        if uid:
            actions[uid].append(row)
    for row in intents_rows:
        uid = _uid_from(row)
        if uid:
            intents[uid].append(row)
    for row in decisions_rows:
        uid = _uid_from(row)
        if uid:
            decisions[uid].append(row)
    for row in global_rows_all:
        uid = _uid_from(row)
        if uid:
            global_rows[uid].append(row)
    for rows in (*actions.values(), *intents.values(), *decisions.values(), *global_rows.values()):
        rows.sort(key=lambda row: f(row.get("timestamp") or row.get("capture_timestamp"), math.inf))
    indexed = [(f(row.get("capture_timestamp")), row.get("video_frame", row.get("source_frame", "")))
               for row in index_rows if f(row.get("capture_timestamp")) is not None]

    def nearest_video_frame(timestamp):
        if timestamp is None or not indexed:
            return "UNKNOWN"
        return min(indexed, key=lambda item: abs(item[0] - timestamp))[1]

    confirmed = set()
    for uid, rows in intents.items():
        if any(row.get("state") == "CONFIRMED" for row in rows):
            confirmed.add(uid)
    all_uids = sorted(set(intents) | set(actions))
    triage = []
    for uid in all_uids:
        terminal = _terminal_state(uid, actions, intents)
        confirmed_rows = [row for row in intents[uid] if row.get("state") == "CONFIRMED"]
        if not confirmed_rows and terminal not in {"FIRED", "CANCELED", "EXPIRED"}:
            continue
        gr = global_rows[uid]
        available = [row for row in gr if row.get("eta_status") == "AVAILABLE"]
        first_confirmed = f(confirmed_rows[0].get("timestamp")) if confirmed_rows else None
        observed = [f(row.get("observed_at")) for row in gr if f(row.get("observed_at")) is not None]
        last_obs = max(observed) if observed else None
        keydowns = [row for row in actions[uid] if row.get("action") == "key_down"]
        schedules = [row for row in actions[uid] if row.get("action") == "scheduled"]
        safe_times = [f(row.get("last_safe_schedule_at")) for row in decisions[uid]
                      if f(row.get("last_safe_schedule_at")) is not None]
        track_ids = sorted({row.get("track_id", "") for row in decisions[uid] if row.get("track_id")})
        reasons = sorted({row.get("reason", "") for row in intents[uid] + decisions[uid] if row.get("reason")})
        anchor_at = f(available[0].get("capture_timestamp")) if available else last_obs
        triage.append({
            "run": str(run_dir), "profile": profile, "uid": uid,
            "first_confirmed_at": first_confirmed or "", "last_real_obs_at": last_obs or "",
            "observed_lane": "UNKNOWN", "video_frame": nearest_video_frame(anchor_at),
            "visible_physical_note_confidence": "UNKNOWN", "physical_note_truth": "UNKNOWN",
            "any_available_eta": bool(available),
            "first_available_at": (f(available[0].get("capture_timestamp")) if available else ""),
            "last_safe_schedule_at": max(safe_times) if safe_times else "UNKNOWN",
            "ever_scheduled": bool(schedules),
            "ever_key_down": bool(keydowns), "hold_overlap": any("hold" in r.lower() for r in reasons),
            "duplicate_suspected": len(track_ids) > 1,
            "primary_blocker": _primary_blocker(uid, intents, decisions, global_rows, actions, terminal),
            "secondary_blockers": ";".join(reasons),
            "actionable_without_unsafe_override": False,
            "video_evidence_path": "", "review_status": "UNKNOWN",
            "lifecycle_terminal": terminal,
            "post_fire_diagnostic_rejection": bool(terminal == "FIRED" and any(
                row.get("state") == "NOT_SCHEDULED" for row in intents[uid])),
        })

    # Reconstruct final deadline state and amendment oscillation from actual
    # action transitions, never from repeated diagnostics.
    oscillation = []
    for uid, rows in actions.items():
        tap = [row for row in rows if row.get("note_type") == "tap" and
               row.get("action") in {"scheduled", "amended", "key_down", "canceled"}]
        deadlines = [row for row in tap if row.get("action") in {"scheduled", "amended"} and
                     f(row.get("scheduled_hit")) is not None]
        if not deadlines:
            continue
        initial = f(deadlines[0].get("scheduled_hit")); current = initial
        earlier = later = reversals = 0; sum_abs = 0.; previous = None
        for row in deadlines[1:]:
            new = f(row.get("scheduled_hit"))
            if row.get("action") != "amended" or new is None:
                current = new if new is not None else current
                continue
            delta = (new - current) * 1000
            direction = "earlier" if delta < 0 else "later" if delta > 0 else "none"
            if direction == "earlier": earlier += 1
            if direction == "later": later += 1
            if previous and direction != "none" and direction != previous: reversals += 1
            if direction != "none": previous = direction
            sum_abs += abs(delta); current = new
        keydowns = [row for row in tap if row.get("action") == "key_down"]
        key_at = f(keydowns[-1].get("timestamp")) if keydowns else None
        oscillation.append({
            "run": str(run_dir), "profile": profile, "uid": uid,
            "initial_deadline": initial, "last_accepted_deadline": current,
            "key_down_actual_at": key_at or "", "net_shift_ms": (current-initial)*1000,
            "sum_abs_shift_ms": sum_abs, "earlier_count": earlier, "later_count": later,
            "reversal_count": reversals,
            "amend_to_fire_gap_ms": ((key_at-current)*1000 if key_at is not None else ""),
            "final_amend_within_30ms_of_deadline": "UNKNOWN" if key_at is None else
                abs((key_at-current)*1000) <= 30,
            "game_truth": "UNKNOWN",
        })

    # Pick a small set of frame anchors for manual review; do not attempt OCR
    # or infer grades.  The source path is recorded even when extraction is
    # unavailable, so a reviewer can reproduce the lookup.
    for row in triage:
        row["video_evidence_path"] = str(run_dir / "live_source.mp4") if (run_dir / "live_source.mp4").exists() else ""
    return triage, oscillation, {
        "run": str(run_dir), "profile": profile,
        "confirmed_uids": len(confirmed),
        "confirmed_no_key_down": sum(1 for row in triage if row["ever_key_down"] is False and row["first_confirmed_at"]),
        "fired_uids": sum(1 for row in triage if row["lifecycle_terminal"] == "FIRED"),
        "input_fired": sum(1 for uid in actions if any(r.get("action") == "key_down" and r.get("note_type") == "tap" for r in actions[uid])),
        "source_available": (run_dir / "live_source.mp4").exists(),
        "video_index_rows": len(index_rows),
    }


def write_docs(out_dir, triage, oscillation, summaries):
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = resolve_config(profile="stable")
    snapshot = {
        "profile": "stable", "source_mode": resolved.metadata["source_mode"],
        "key_map": resolved.config["key_map"],
        "global_tap_timing": resolved.config["live"]["global_tap_timing"],
        "tap_deadline_amend": resolved.config["live"]["tap_deadline_amend"],
        "max_frame_age_ms": resolved.config["live"]["max_frame_age_ms"],
        "max_input_lateness_ms": resolved.config["live"]["max_input_lateness_ms"],
        "pf_role": "tracking_only", "hold_role": "visual_tail",
        "game_truth": "UNKNOWN",
    }
    (out_dir / "baseline_policy_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["run", "profile", "uid", "first_confirmed_at", "last_real_obs_at", "observed_lane",
              "video_frame", "visible_physical_note_confidence", "physical_note_truth", "any_available_eta", "first_available_at",
              "last_safe_schedule_at", "ever_scheduled", "ever_key_down", "hold_overlap",
              "duplicate_suspected", "primary_blocker", "secondary_blockers",
              "actionable_without_unsafe_override", "video_evidence_path", "review_status",
              "lifecycle_terminal", "post_fire_diagnostic_rejection"]
    write_csv(out_dir / "unfired_uid_triage.csv", triage, fields)
    write_csv(out_dir / "deadline_oscillation.csv", oscillation,
              ["run", "profile", "uid", "initial_deadline", "last_accepted_deadline", "key_down_actual_at",
               "net_shift_ms", "sum_abs_shift_ms", "earlier_count", "later_count", "reversal_count",
               "amend_to_fire_gap_ms", "final_amend_within_30ms_of_deadline", "game_truth"])
    # Source videos are available, but no independent HUD-grade labels were
    # supplied. Keep explicit UNKNOWN schemas instead of inferring MISS/Hit.
    write_csv(out_dir / "video_grade_events.csv", [],
              ["run", "capture_timestamp", "video_frame", "grade_text", "display_event_id",
               "confidence", "review_status", "notes"])
    write_csv(out_dir / "video_grade_uid_links.csv", [],
              ["run", "uid", "display_event_id", "capture_timestamp", "lane", "link_confidence",
               "physical_note_truth", "review_status", "notes"])
    review_dir = out_dir / "review_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "README.txt").write_text(
        "No trusted HUD labels were supplied; no frame was auto-labelled. "
        "Use live_video_index.csv to extract source frames for manual review.\n",
        encoding="utf-8")
    report = ["# V7.14.10 Tap 未送鍵根因與終態修正", "",
              "本報告只使用軟體觀測與 monotonic capture timestamp；遊戲判定真值為 UNKNOWN。",
              "FIRED/key_down 代表輸入執行，不代表遊戲命中。後續 NOT_SCHEDULED 不會覆蓋先前 FIRED。", ""]
    for summary in summaries:
        report += [f"## {summary['profile']}",
                   f"- Run: `{summary['run']}`; source video: `{summary['source_available']}`; video index rows: {summary['video_index_rows']}.",
                   f"- Confirmed UID: {summary['confirmed_uids']}; confirmed/no-key-down (software): {summary['confirmed_no_key_down']}; input FIRED: {summary['input_fired']} (not game truth).", ""]
    counts = Counter(row["primary_blocker"] for row in triage if not row["ever_key_down"])
    report += ["## 未送鍵主要阻塞（分母為本次可追蹤的 confirmed/terminal triage rows）", ""]
    for reason, count in counts.most_common():
        report.append(f"- `{reason}`: {count}")
    report += ["", "## 10 個可重播案例索引（尚未人工確認）", ""]
    for row in [r for r in triage if not r["ever_key_down"]][:20][:10]:
        report.append(f"- `{row['profile']}` `{row['uid']}`: source `{row['video_evidence_path']}`, nearest video frame `{row['video_frame']}`, blocker `{row['primary_blocker']}`, review `UNKNOWN`." )
    report += ["", "## 資料限制", "",
               "- `observed_lane`、`video_frame` 與 physical_note_truth 未在現有 CSV 形成可靠的一對一鏈結，保留 UNKNOWN。",
               "- 最小補強是把每個 capture frame 的 source video frame、候選 bbox/lane 與 note UID 寫入同一 trace row，再由人工確認 anchor。",
               "- 未執行遊戲 OCR，也未把 Combo、score、FIRED 或 key_down 當成命中。", "",
               "## 下一步（最多一項 Active 修正候選）", "",
               "在完成至少 10 個高信度逐顆影片鏈結前，不修改 Active gate；目前只保留終態分類修正與可追溯 triage。"]
    (Path("docs") / "V7.14.10_TAP_UNFIRED_ROOT_CAUSE.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    amend = ["# V7.14.10 Amendment 影響", "", "所有數值重建自 input_actions.csv 的 scheduled/amended，不把重複排程診斷當 amendment。", ""]
    for profile in {s["profile"] for s in summaries}:
        rows = [r for r in oscillation if r["profile"] == profile]
        amend += [f"## {profile}", f"- UIDs with action ledger: {len(rows)}; reversal UIDs: {sum(r['reversal_count'] > 0 for r in rows)}; game truth: UNKNOWN.",
                   f"- Earlier actions: {sum(r['earlier_count'] for r in rows)}; later actions: {sum(r['later_count'] for r in rows)}.", ""]
    (Path("docs") / "V7.14.10_AMEND_IMPACT.md").write_text("\n".join(amend) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=Path("output"))
    parser.add_argument("--out-dir", type=Path, default=Path("output/analysis_v71410"))
    args = parser.parse_args()
    triage = []; oscillation = []; summaries = []
    for profile, relative in RUNS.items():
        run_dir = args.run_root / relative.name
        rows, amendments, summary = analyze_run(run_dir, profile, args.out_dir)
        triage.extend(rows); oscillation.extend(amendments); summaries.append(summary)
    write_docs(args.out_dir, triage, oscillation, summaries)
    print(json.dumps({"triage_rows": len(triage), "oscillation_rows": len(oscillation),
                      "summaries": summaries}, indent=2))


if __name__ == "__main__":
    main()
