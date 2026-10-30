"""Join one live Assist run into per-attempt PF/Tracker/Scheduler evidence."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


AUDIT_FIELDS = [
    "session_id", "event_id", "lifecycle_id", "physical_note_uid", "source_track_ids",
    "selected_key", "key_candidates", "appearance", "original_hit_at", "current_predicted_hit_at",
    "fire_deadline", "scheduled_at", "last_reliable_tap_at", "current_type", "confirmed_note_type",
    "identity_state", "tracker_status", "PF_measurement_status", "eta_p10", "eta_p50", "eta_p90",
    "crossing_mass", "ESS", "association_reason", "matched_new_id", "scheduler_state", "cancel_reason",
    "failed_predicate", "key_down_at", "alternative_uid_keydown", "classification", "result_confidence",
]
TRACE_FIELDS = ["timestamp", "event_id", "physical_note_uid", "track_id", "action", "action_reason",
                "key", "scheduled_hit", "scheduler_armed", "tracker_status", "current_type",
                "confirmed_note_type", "identity_state", "measurement_status", "association_reason",
                "first_failed_predicate", "all_failed_predicates"]
REVIEW_FIELDS=["event_id","tracker_uid_not_ground_truth","source_frame","capture_timestamp",
               "candidate_type","appearance","selected_key","key_candidates",
               "reviewed_physical_note_id","judgment_label","review_status"]


def read_rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open(newline="", encoding="utf-8-sig"))) if path.exists() else []


def write_rows(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def track_num(event_id: str) -> str:
    return event_id.rsplit(":", 1)[-1] if ":" in event_id else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    run = json.loads((run_dir / "live_run.json").read_text(encoding="utf-8-sig"))
    events = read_rows(run_dir / "live_events.csv")
    actions = read_rows(run_dir / "live_key_actions.csv")
    transitions = read_rows(run_dir / "pf_identity_transitions.csv")
    associations = read_rows(run_dir / "pf_unknown_association_audit.csv")
    eta_rows = read_rows(run_dir / "pf_hit_eta_diagnostics.csv")
    frames = read_rows(run_dir / "live_frames.csv")
    event_by_id = {row["event_id"]: row for row in events if row.get("event_id")}

    scheduled = defaultdict(list)
    downs = defaultdict(list)
    cancels = defaultdict(list)
    for row in actions:
        eid = row.get("event_id", "")
        if not eid:
            continue
        if row.get("action") == "scheduled":
            scheduled[eid].append(row)
        elif row.get("action") == "key_down":
            downs[eid].append(row)
        elif row.get("action") == "canceled":
            cancels[eid].append(row)

    eta_by_track = defaultdict(list)
    transitions_by_track = defaultdict(list)
    associations_by_track = defaultdict(list)
    for row in eta_rows:
        eta_by_track[str(row.get("track_id", ""))].append(row)
    for row in transitions:
        transitions_by_track[str(row.get("track_id", ""))].append(row)
    for row in associations:
        associations_by_track[str(row.get("track_id", ""))].append(row)
    for series in (*eta_by_track.values(), *transitions_by_track.values(), *associations_by_track.values()):
        series.sort(key=lambda row: float(row.get("capture_timestamp", row.get("timestamp", 0)) or 0))

    uid_downs = defaultdict(list)
    for eid, rows in downs.items():
        event = event_by_id.get(eid, {})
        uid = event.get("physical_track_uid", "")
        if uid:
            uid_downs[uid].extend(rows)

    max_lateness = 0.015
    audit, trace = [], []
    for eid, attempts in scheduled.items():
        attempts.sort(key=lambda row: float(row.get("timestamp", 0) or 0))
        event = event_by_id.get(eid, {})
        tid = track_num(eid)
        per_event_actions=sorted((r for r in actions if r.get("event_id")==eid),
            key=lambda row:float(row.get("timestamp",0) or 0))
        source_ids = event.get("source_track_ids", "")
        reidentified = event.get("reidentified_from_id", "")
        for attempt_index,first in enumerate(attempts,1):
            start=float(first.get("timestamp",0) or 0)
            next_start=float(attempts[attempt_index].get("timestamp",0) or 0) if attempt_index<len(attempts) else float("inf")
            window=[r for r in per_event_actions if start<=float(r.get("timestamp",0) or 0)<next_start]
            key_down=[r for r in window if r.get("action")=="key_down"]
            cancel=[r for r in window if r.get("action")=="canceled"]
            gate_rows=[r for r in window if r.get("action") in ("track_gate_rejected","commit_invalidated","track_finished")]
            reason=cancel[-1].get("reason","") if cancel else ""
            terminal_rows=key_down[-1:] if key_down else cancel[-1:]
            end_time=(float(terminal_rows[-1].get("timestamp",0) or 0) if terminal_rows else
                      max([float(r.get("timestamp",0) or 0) for r in window] or [start]))
            gate_rows=[r for r in gate_rows if float(r.get("timestamp",0) or 0)<=end_time]
            eta=[r for r in eta_by_track.get(tid,[]) if float(r.get("capture_timestamp",0) or 0)<=end_time]
            last_eta=eta[-1] if eta else {}
            trans=[r for r in transitions_by_track.get(tid,[]) if float(r.get("timestamp",0) or 0)<=end_time]
            last_transition=trans[-1] if trans else {}
            assoc=[r for r in associations_by_track.get(tid,[]) if float(r.get("timestamp",0) or 0)<=end_time]
            last_assoc=assoc[-1] if assoc else {}
            uid=event.get("physical_track_uid",last_transition.get("physical_note_uid",""))
            gate_detail=gate_rows[-1].get("reason","") if gate_rows else ""
            detail_status=gate_detail.split(";",1)[0] if gate_detail else ""
            tracker_status=detail_status.split(":",1)[0] if ":" in detail_status else last_eta.get("tracker_status","NOT_RECORDED")
            prediction_reason=detail_status.split(":",1)[1] if ":" in detail_status else ""
            if key_down:
                classification, failed = "FIRED_KEY_DOWN_RECORDED", "NONE"
            elif reason in ("global_escape_or_f12", "game_state_or_focus_or_roi_loss", "stale_frame_or_focus_loss"):
                classification, failed = "SAFETY_STOP_OR_CONTEXT_LOSS", "SAFETY_CONTEXT_INVALID"
            elif reason == "duplicate_hold_path":
                classification, failed = "DUPLICATE_HOLD_SUPPRESSED", "HOLD_DUPLICATE_GUARD"
            elif reason == "provisional_loss_expired":
                classification, failed = "TRACK_OR_IDENTITY_LOSS_EXPIRED", "PROVISIONAL_OR_IDENTITY_GRACE_EXPIRED"
            elif reason in ("assigned_key_no_longer_valid", "tap_key_conflict"):
                classification, failed = "KEY_CONFLICT_OR_COVERAGE_REJECTED", "KEY_EVIDENCE_INVALID"
            elif reason in ("unstable_hit_time", "hit_time_drift"):
                classification, failed = "PREDICTION_GATE_REJECTED", reason.upper()
            elif reason in ("track_not_current_or_confirmed", "no_current_eligible_observation"):
                classification, failed = "TRACK_ELIGIBILITY_REJECTED", (f"TRACKER_{tracker_status.upper()}" if tracker_status!="NOT_RECORDED" else "TRACK_STATE_OR_CURRENT_OBSERVATION_FAILED")
                if prediction_reason: failed += "|PREDICTION_"+prediction_reason.upper()
            elif reason:
                classification, failed = "CANCELED_OTHER", reason.upper()
            else:
                classification, failed = "PENDING_OR_EXPIRED_AT_STOP", "UNKNOWN_TERMINAL_STATE"
            other_downs=[row for row in uid_downs.get(uid,[]) if row.get("event_id")!=eid] if uid else []
            alternative="|".join(f"{row.get('event_id','')}:{row.get('key','')}" for row in other_downs)
            hit_at=float(first.get("scheduled_hit",0) or 0)
            audit.append({
            "session_id": eid.rsplit(":", 1)[0] if ":" in eid else "UNKNOWN",
            "event_id": eid, "lifecycle_id": f"{eid}#attempt-{attempt_index}", "physical_note_uid": uid or "UNKNOWN",
            "source_track_ids": source_ids or tid, "selected_key": first.get("key", "UNKNOWN"),
            "key_candidates": event.get("key_candidates", "UNKNOWN"), "appearance": event.get("appearance", "UNKNOWN"),
            "original_hit_at": hit_at, "current_predicted_hit_at": last_eta.get("hit_at", "UNKNOWN"),
            "fire_deadline": hit_at + max_lateness if hit_at else "UNKNOWN",
            "scheduled_at": first.get("timestamp", "UNKNOWN"), "last_reliable_tap_at": last_eta.get("last_reliable_tap_at","UNKNOWN"),
            "current_type": last_eta.get("current_observation_type", event.get("current_observation_type", "UNKNOWN")),
            "confirmed_note_type": last_eta.get("confirmed_note_type", event.get("confirmed_note_type", "UNKNOWN")),
            "identity_state": last_transition.get("to_state", event.get("identity_state", "UNKNOWN")),
            "tracker_status": tracker_status, "PF_measurement_status": last_eta.get("measurement_status", "UNKNOWN"),
            "eta_p10": last_eta.get("eta_p10", "UNKNOWN"), "eta_p50": last_eta.get("eta_p50", "UNKNOWN"),
            "eta_p90": last_eta.get("eta_p90", "UNKNOWN"), "crossing_mass": last_eta.get("valid_crossing_mass", "UNKNOWN"),
            "ESS": last_eta.get("particle_ess", "UNKNOWN"),
            "association_reason": last_assoc.get("final_reason", "UNKNOWN"),
            "matched_new_id": reidentified or "UNKNOWN", "scheduler_state": first.get("armed", "UNKNOWN"),
            "cancel_reason": reason or ("NONE_KEY_DOWN_RECORDED" if key_down else "UNKNOWN"),
            "failed_predicate": failed, "key_down_at": "|".join(r.get("timestamp", "") for r in key_down) or "NONE",
            "alternative_uid_keydown": alternative or "NONE",
            "classification": classification,
            "result_confidence": "ACTION_LOG_CONFIRMED" if key_down else "PIPELINE_ONLY_NO_GAME_TRUTH",
        })
            for row in window:
                trace.append({"timestamp": row.get("timestamp", ""), "event_id": eid,
                          "physical_note_uid": uid or "UNKNOWN", "track_id": tid,
                          "action": row.get("action", ""), "action_reason": row.get("reason", ""),
                          "key": row.get("key", ""), "scheduled_hit": row.get("scheduled_hit", ""),
                          "scheduler_armed": row.get("armed", ""),
                          "tracker_status": tracker_status,
                          "current_type": last_eta.get("current_observation_type", "UNKNOWN"),
                          "confirmed_note_type": last_eta.get("confirmed_note_type", "UNKNOWN"),
                          "identity_state": last_transition.get("to_state", "UNKNOWN"),
                          "measurement_status": last_eta.get("measurement_status", "UNKNOWN"),
                          "association_reason": last_assoc.get("final_reason", "UNKNOWN"),
                          "first_failed_predicate": failed,
                          "all_failed_predicates": failed})

    audit.sort(key=lambda row: float(row["scheduled_at"]) if row["scheduled_at"] not in ("", "UNKNOWN") else 0)
    trace.sort(key=lambda row: float(row["timestamp"]) if row["timestamp"] else 0)
    write_rows(run_dir / "pf_intent_failure_audit.csv", AUDIT_FIELDS, audit)
    trace_path=run_dir/"pf_identity_scheduler_trace.csv"
    if trace_path.exists() and trace_path.stat().st_size>0:
        trace_path=run_dir/"pf_identity_scheduler_trace_reconstructed.csv"
    write_rows(trace_path, TRACE_FIELDS, trace)

    unsent_attempts=[row for row in audit if row["classification"]!="FIRED_KEY_DOWN_RECORDED"]
    latest_by_event={}
    for row in audit:
        latest_by_event[row["event_id"]]=row
    unique_down_ids=len(set(downs).intersection(scheduled))
    no_down_event_ids=set(scheduled)-set(downs)
    unsent=[row for event_id,row in latest_by_event.items() if event_id in no_down_event_ids]
    event_index={r.get("event_id"):r for r in events}
    review=[]
    for row in unsent:
        event=event_index.get(row["event_id"],{})
        review.append({"event_id":row["event_id"],"tracker_uid_not_ground_truth":row["physical_note_uid"],
            "source_frame":event.get("source_frame","UNKNOWN"),"capture_timestamp":event.get("capture_timestamp","UNKNOWN"),
            "candidate_type":event.get("type","UNKNOWN"),"appearance":event.get("appearance","UNKNOWN"),
            "selected_key":row["selected_key"],"key_candidates":event.get("key_candidates","UNKNOWN"),
            "reviewed_physical_note_id":"UNKNOWN","judgment_label":"UNKNOWN",
            "review_status":"NOT_HUMAN_REVIEWED"})
    write_rows(run_dir/"v6_pf_real_note_review.csv",REVIEW_FIELDS,review)
    categories = Counter(row["classification"] for row in unsent)
    predictor_counts=Counter(row.get("predictor_mode","UNKNOWN") for row in events)
    unstable_counts=Counter(row.get("predictor_mode","UNKNOWN") for row in events
                            if row.get("abstain_reason")=="unstable_hit_time")
    lines = ["# V6 PF Intent Root Cause Audit", "", f"Run: `{run_dir.name}`", "",
             f"Schedule attempts: {len(audit)}; scheduled unique event IDs: {len(scheduled)}; key-down unique IDs: {unique_down_ids}; unique IDs without key-down: {len(unsent)}.",
             f"Unsent schedule attempts: {len(unsent_attempts)} (repeated schedule rows are retained by lifecycle attempt).",
             "These are scheduler pipeline counts, not physical-note MISS counts.", "",
             f"Events by predictor: {dict(predictor_counts)}. `unstable_hit_time` by predictor: {dict(unstable_counts)}.",
             "Unstable-hit candidates are not automatically misses; source type and any alternative key-down must be reviewed.", "",
             "## Unsent classifications", ""]
    lines.extend(f"- {name}: {count}" for name, count in categories.most_common())
    lines += ["", "## Per-ID rows", "", "| Event ID | UID | Key | Class | Failed predicate | Cancel reason |",
              "|---|---|---:|---|---|---|"]
    lines.extend(f"| {r['event_id']} | {r['physical_note_uid']} | {r['selected_key']} | {r['classification']} | {r['failed_predicate']} | {r['cancel_reason']} |"
                 for r in unsent)
    lines += ["", "`UNKNOWN` means the available run logs did not record that value. No row is labeled a game MISS without frame-level human judgment evidence.", ""]
    (run_dir / "v6_pf_root_cause_audit.md").write_text("\n".join(lines), encoding="utf-8")
    frame_rows = frames
    summary = {"events": len(events), "scheduled_attempts": len(audit),
               "scheduled_unique_event_ids": len(scheduled),
               "key_down_unique_event_ids": unique_down_ids, "no_key_down_unique_ids": len(no_down_event_ids),
               "no_key_down_schedule_attempts": len(unsent_attempts),
               "unsent_classifications": dict(categories), "identity_transition_rows": len(transitions),
               "events_by_predictor":dict(predictor_counts),"unstable_hit_time_by_predictor":dict(unstable_counts),
               "unknown_association_rows": len(associations), "eta_diagnostic_rows": len(eta_rows),
               "frame_rows": len(frame_rows), "game_accuracy": "UNVERIFIED"}
    (run_dir / "pf_audit_summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
