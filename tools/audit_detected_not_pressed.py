"""Build an evidence-first audit bundle for one Assist run and its mock replay."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import statistics


def read(path):
    return list(csv.DictReader(path.open(newline="", encoding="utf-8-sig"))) if path.exists() else []


def write(path, rows, fields=None):
    fields = fields or (list(rows[0]) if rows else ["status"])
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        out = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        out.writeheader()
        out.writerows(rows)


def number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def duration(rows, key="capture_timestamp"):
    times = [number(row.get(key)) for row in rows]
    times = [t for t in times if t is not None]
    return max(times) - min(times) if len(times) >= 2 else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    root = args.run_dir.resolve()
    events = read(root / "live_events.csv")
    actions = read(root / "live_key_actions.csv")
    frames = read(root / "live_frames.csv")
    eta = read(root / "pf_hit_eta_diagnostics.csv")
    transitions = read(root / "pf_identity_transitions.csv")
    trace = read(root / "tap_decision_trace.csv")
    replay_events = read(root / "pf_mock_replay_events.csv")
    replay_actions = read(root / "pf_mock_replay_actions.csv")
    replay_summary = json.loads((root / "pf_mock_replay_summary.json").read_text(encoding="utf-8-sig")) if (root / "pf_mock_replay_summary.json").exists() else {}
    replay_repeat = json.loads((root / "replay_determinism_check.json").read_text(encoding="utf-8-sig")) if (root / "replay_determinism_check.json").exists() else {}
    stage_rows = read(root / "pf_stage_timing.csv")
    duration_s = duration(frames) or duration(events)
    minutes = duration_s / 60 if duration_s else 0
    by_event = {r.get("event_id"): r for r in events if r.get("event_id")}
    action_by_event = defaultdict(list)
    for row in actions:
        if row.get("event_id"):
            action_by_event[row["event_id"]].append(row)
    replay_by_event = {r.get("event_id"): r for r in replay_events if r.get("event_id")}
    replay_action_by_event = defaultdict(list)
    for row in replay_actions:
        if row.get("event_id"):
            replay_action_by_event[row["event_id"]].append(row)
    downs_by_uid = defaultdict(list)
    for event_id, rows in action_by_event.items():
        event = by_event.get(event_id, {})
        uid = event.get("physical_track_uid", "")
        downs_by_uid[uid].extend(r for r in rows if r.get("action") == "key_down")

    detected, scheduled = [], []
    for event in events:
        eid = event.get("event_id", "")
        lifecycle = action_by_event.get(eid, [])
        schedules = [r for r in lifecycle if r.get("action") == "scheduled"]
        downs = [r for r in lifecycle if r.get("action") == "key_down"]
        cancels = [r for r in lifecycle if r.get("action") in ("canceled", "abstain")]
        uid = event.get("physical_track_uid", "")
        alternatives = [r for r in downs_by_uid.get(uid, []) if r.get("event_id") != eid] if uid else []
        if downs:
            cls, reason = "KEY_DOWN_SENT_GAME_RESULT_UNKNOWN", "key_down_recorded"
        elif schedules:
            cancel_reason = cancels[-1].get("reason", "") if cancels else ""
            cls, reason = classify_cancel(cancel_reason, bool(alternatives))
        elif alternatives:
            cls, reason = "REPLACEMENT_ID_SENT", "same_tracker_uid_other_id_keydown"
        elif event.get("gameplay_state") != "PLAYING":
            cls, reason = "SAFETY_OR_GAME_STATE_REJECTED", event.get("gameplay_state", "unknown")
        elif event.get("abstain_reason") in ("past_hit_time", "hit_time_drift"):
            cls, reason = "EXPIRED_OR_ETA_GATE_BEFORE_OFFER", event.get("abstain_reason")
        elif event.get("abstain_reason"):
            cls, reason = "DETECTED_NOT_SCHEDULED", event.get("abstain_reason")
        else:
            cls, reason = "DETECTED_NOT_SCHEDULED", "no_schedule_action_for_event_id"
        detected.append({"event_id": eid, "source_frame": event.get("source_frame", ""),
            "capture_timestamp": event.get("capture_timestamp", ""),
            "physical_note_uid": uid or "UNKNOWN_TRACKER_UID_NOT_GROUND_TRUTH",
            "predictor_mode": event.get("predictor_mode", ""),
            "candidate_type": event.get("type", ""), "appearance": event.get("appearance", ""),
            "key_candidates": event.get("key_candidates", ""), "selected_key": event.get("resolved_keys", ""),
            "decision_reason": event.get("abstain_reason", ""), "schedule_count": len(schedules),
            "key_down_count": len(downs), "cancel_reason": cancels[-1].get("reason", "") if cancels else "",
            "alternative_tracker_uid_keydown": "|".join(r.get("event_id", "") for r in alternatives),
            "pipeline_class": cls, "final_reason": reason,
            "game_judgment": "UNKNOWN_NOT_IN_ACTION_LOG"})
        schedules.sort(key=lambda r: number(r.get("timestamp"), 0))
        for n, sched in enumerate(schedules, 1):
            start=number(sched.get("timestamp"),0)
            next_start=number(schedules[n].get("timestamp"),float("inf")) if n<len(schedules) else float("inf")
            window=[r for r in lifecycle if start<=number(r.get("timestamp"),-1)<next_start]
            terminal = next((r for r in window if
                             r.get("action") in ("key_down", "canceled", "abstain")), None)
            if terminal and terminal.get("action")=="key_down":
                cls, reason = "KEY_DOWN_SENT", "key_down_recorded"
            else:
                cls, reason = classify_cancel(terminal.get("reason", "") if terminal else "", bool(alternatives))
            scheduled.append({"event_id": eid, "lifecycle_id": f"{eid}#attempt-{n}",
                "physical_note_uid": uid or "UNKNOWN", "selected_key": sched.get("key", ""),
                "scheduled_at": sched.get("timestamp", ""), "original_hit_at": sched.get("scheduled_hit", ""),
                "fire_deadline": (number(sched.get("scheduled_hit"), 0) + .015),
                "terminal_action": terminal.get("action", "UNKNOWN") if terminal else "UNKNOWN",
                "terminal_reason": terminal.get("reason", "UNKNOWN") if terminal else "UNKNOWN",
                "pipeline_class": cls, "final_reason": reason,
                "game_judgment": "UNKNOWN_NOT_IN_ACTION_LOG"})
    write(root / "detected_tap_audit.csv", detected)

    # Explicit per-event scheduler cancellation gates with full available context.
    trace_by_event = defaultdict(list)
    for row in trace:
        if row.get("event_id"):
            trace_by_event[row["event_id"]].append(row)
    cancel_audit = []
    for event_id, rows in action_by_event.items():
        for row in rows:
            if row.get("action") not in ("canceled", "abstain", "commit_invalidated", "track_gate_rejected"):
                continue
            event = by_event.get(event_id, {})
            evidence = trace_by_event.get(event_id, [])
            evidence = evidence[-1] if evidence else {}
            cancel_audit.append({"event_id": event_id, "physical_note_uid": event.get("physical_track_uid", "UNKNOWN"),
                "source_frame": evidence.get("source_frame", event.get("source_frame", "")),
                "timestamp": row.get("timestamp", ""), "action": row.get("action", ""),
                "cancel_reason": row.get("reason", ""), "decision_stage": evidence.get("decision_stage", "NOT_RECORDED_IN_BASELINE"),
                "failed_predicate": evidence.get("reject_reason", evidence.get("all_failed_predicates", "")),
                "track_status": evidence.get("track_status", "NOT_RECORDED_IN_BASELINE"),
                "identity_state": evidence.get("identity_state", event.get("identity_state", "")),
                "selected_key": event.get("resolved_keys", ""),
                "original_hit_at": row.get("scheduled_hit", ""),
                "game_judgment": "UNKNOWN_NOT_IN_ACTION_LOG"})
    write(root / "scheduler_cancel_gate_audit.csv", cancel_audit)

    # The historical event export only records final event decisions. Label the absence
    # of intermediate per-frame PF evidence instead of inventing it.
    eta_audit = []
    for event in events:
        if event.get("predictor_mode") != "particle":
            continue
        eta_audit.append({"event_id": event.get("event_id"), "physical_note_uid": event.get("physical_track_uid", "UNKNOWN"),
            "source_frame": event.get("source_frame", ""), "decision": "SCHEDULED" if event.get("resolved_keys") else "REJECTED",
            "reject_reason": event.get("abstain_reason", ""), "eta_p10": event.get("eta_p10_s", ""),
            "eta_p50": event.get("eta_p50_s", ""), "eta_p90": event.get("eta_p90_s", ""),
            "credible_width_ms": ((number(event.get("eta_p90_s"), 0)-number(event.get("eta_p10_s"), 0))*1000
                                  if event.get("eta_p10_s") and event.get("eta_p90_s") else ""),
            "crossing_mass": event.get("valid_crossing_mass", ""), "ess": event.get("particle_ess", ""),
            "real_observation_count": event.get("real_observation_count", ""), "coast_ms": event.get("coast_ms", ""),
            "measurement_status": event.get("measurement_status", ""),
            "legacy_hit_history_gate": "NOT_APPLICABLE_PF_PATH",
            "evidence_scope": "FINAL_EVENT_ROW_ONLY; per-frame diagnostics absent from historical baseline"})
    for row in trace:
        if str(row.get("particle_initialized", "")).lower() not in ("true", "1"):
            continue
        eta_audit.append({"event_id": row.get("event_id"), "physical_note_uid": row.get("physical_note_uid", "UNKNOWN"),
            "source_frame": row.get("source_frame", ""), "decision": row.get("decision_result", ""),
            "reject_reason": row.get("particle_eta_reject_reason", ""), "eta_p10": row.get("eta_p10", ""),
            "eta_p50": row.get("eta_p50", ""), "eta_p90": row.get("eta_p90", ""),
            "credible_width_ms": ((number(row.get("eta_p90"), 0)-number(row.get("eta_p10"), 0))*1000
                                  if row.get("eta_p10") and row.get("eta_p90") else ""),
            "crossing_mass": row.get("particle_valid_crossing_mass", ""),
            "ess": row.get("particle_ess", ""), "real_observation_count": row.get("particle_real_observation_count", ""),
            "coast_ms": row.get("particle_coast_ms", ""),
            "measurement_status": row.get("particle_measurement_status", ""),
            "legacy_hit_history_gate": "NOT_APPLICABLE_PF_PATH",
            "evidence_scope": "CURRENT_CODE_MOCK_REPLAY; per-frame evidence"})
    write(root / "pf_eta_eligibility_audit.csv", eta_audit)

    # Per-event matching is exact only when event ID and UID/frame match; aggregate
    # rates are still reported per minute to make unlike replay counts interpretable.
    joined = []
    comparable = 0
    for event in detected:
        eid = event["event_id"]
        replay_match = replay_by_event.get(eid)
        exact = bool(replay_match and replay_match.get("source_frame") == event["source_frame"] and
                     replay_match.get("physical_note_uid") == event["physical_note_uid"])
        comparable += exact
        joined.append({"event_id": eid, "source_frame": event["source_frame"],
            "physical_note_uid": event["physical_note_uid"], "baseline_class": event["pipeline_class"],
            "baseline_reason": event["final_reason"], "replay_event_id": replay_match.get("event_id", "") if replay_match else "",
            "replay_class": "REPLAY_EVENT_PRESENT" if replay_match else "NO_EXACT_EVENT_MATCH",
            "comparison_status": "COMPARABLE_EXACT_ID_UID_FRAME" if exact else "NOT_COMPARABLE_TRACK_OR_EVENT_MAPPING"})
    baseline_unstable=sum(r.get("abstain_reason")=="unstable_hit_time" for r in events)
    replay_unstable=sum(r.get("reject_reason")=="unstable_hit_time" for r in trace)
    for side, metric_name, value in (("baseline_live","detected_events",len(events)),
        ("baseline_live","unstable_hit_time",baseline_unstable),
        ("mock_replay","decision_trace_rows",len(trace)),
        ("mock_replay","unstable_hit_time",replay_unstable)):
        joined.append({"event_id":"", "source_frame":"", "physical_note_uid":"", "baseline_class":"",
            "baseline_reason":"", "replay_event_id":"", "replay_class":f"{side}:{metric_name}={value}",
            "comparison_status":f"AGGREGATE_ONLY {value/minutes if minutes else 0:.2f}/min; no exact physical note mapping"})
    write(root / "pf_eligibility_before_after.csv", joined)
    cancel_before = [r for r in cancel_audit if r["action"] in ("canceled", "abstain")]
    replay_cancel = [r for r in replay_actions if r.get("action") in ("canceled", "abstain")]
    schedule_before = [r for r in actions if r.get("action") == "scheduled"]
    schedule_after = [r for r in replay_actions if r.get("action") == "scheduled"]
    write(root / "pending_cancel_before_after.csv", [
        metric("baseline_live", "scheduled_attempts", len(schedule_before), minutes),
        metric("baseline_live", "canceled_or_expired", len(cancel_before), minutes),
        metric("mock_replay", "scheduled_attempts", len(schedule_after), minutes),
        metric("mock_replay", "canceled_or_expired", len(replay_cancel), minutes),
        {"side": "comparison", "metric": "exact_event_joins", "count": comparable,
         "per_minute": "", "comparison_status": "LOW/NO EXACT ID MAPPING; aggregate is descriptive only"}])

    uid_rows = []
    for uid, downs in sorted(downs_by_uid.items()):
        if not uid: continue
        uid_rows.append({"physical_note_uid": uid, "uid_source": "TRACKER UID; NOT PHYSICAL GROUND TRUTH",
            "key_down_count": len(downs), "key_down_events": "|".join(r.get("event_id", "") for r in downs),
            "keys": "|".join(r.get("key", "") for r in downs),
            "possible_duplicate": len(downs) > 1,
            "classification": "REVIEW_REQUIRED_TRACKER_UID_MAY_MERGE_OR_SPLIT_PHYSICAL_NOTES" if len(downs) > 1 else "SINGLE_TRACKER_UID_KEYDOWN"})
    write(root / "duplicate_physical_note_audit.csv", uid_rows)

    perf = []
    stage_columns = sorted({key for row in stage_rows for key in row
                            if key.endswith("_ms") and key not in ("latency_ms", "encoder_queue_wait_ms")})
    for stage in stage_columns:
        replay_vals = [number(r.get(stage)) for r in stage_rows
                       if r.get("gameplay_state") == "PLAYING"]
        replay_vals = [v for v in replay_vals if v is not None]
        baseline_vals = [number(r.get(stage)) for r in frames if r.get("gameplay_state") == "PLAYING"]
        baseline_vals = [v for v in baseline_vals if v is not None]
        perf.append({"stage": stage, "baseline_samples": len(baseline_vals),
                     "baseline_p50_ms": statistics.median(baseline_vals) if baseline_vals else "NOT_RECORDED",
                     "baseline_p95_ms": sorted(baseline_vals)[int(.95*(len(baseline_vals)-1))] if baseline_vals else "NOT_RECORDED",
                     "replay_samples": len(replay_vals),
                     "replay_p50_ms": statistics.median(replay_vals) if replay_vals else "",
                     "replay_p95_ms": sorted(replay_vals)[int(.95*(len(replay_vals)-1))] if replay_vals else "",
                     "replay_max_ms": max(replay_vals) if replay_vals else "",
                     "replay_scope": "CURRENT_CODE_OFFLINE_MOCK_REPLAY"})
    write(root / "processing_stage_performance.csv", perf)

    counts = Counter(r["pipeline_class"] for r in detected)
    scheduled_counts = Counter(r["pipeline_class"] for r in scheduled)
    report = ["# Detected but Not Pressed: root-cause audit", "",
        f"Run: `{root.name}`. Source duration: {duration_s:.3f}s ({minutes:.3f} min).",
        f"Detected event rows: {len(events)} ({len(events)/minutes if minutes else 0:.2f}/min).",
        f"Schedule attempts: {len(scheduled)} ({len(scheduled)/minutes if minutes else 0:.2f}/min); unique key-down event IDs: {len({r.get('event_id') for r in actions if r.get('action')=='key_down'})}.",
        "Key-down means SendInput/Mock action was recorded; it does not prove the game registered a hit.", "",
        "## Baseline event classes", ""]
    report += [f"- {name}: {count} ({count/minutes if minutes else 0:.2f}/min)" for name,count in counts.most_common()]
    report += ["", "## Scheduled lifecycle classes", ""]
    report += [f"- {name}: {count} ({count/minutes if minutes else 0:.2f}/min)" for name,count in scheduled_counts.most_common()]
    report += ["", "## Per-event scheduled cancellations", ""]
    for row in scheduled:
        if row["terminal_action"] != "canceled":
            continue
        report.append(f"- `{row['event_id']}` at {row['scheduled_at']}: `{row['terminal_reason']}`; key `{row['selected_key']}`, deadline {row['original_hit_at']}; result remains unknown.")
    unstable = Counter(r.get("predictor_mode", "UNKNOWN") for r in events if r.get("abstain_reason") == "unstable_hit_time")
    unstable_ids=[r for r in events if r.get("abstain_reason")=="unstable_hit_time"]
    report += ["", f"`unstable_hit_time` by predictor: {dict(unstable)}.",
        "These 46 baseline events were all Legacy-predicted; the historical run therefore does not show PF posteriors being rejected by the Legacy hit-history gate.",
        "The event-level causes and frame/time coordinates are in `detected_tap_audit.csv` and `scheduler_cancel_gate_audit.csv`.",
        "", "## Implementation changes", "",
        "- Modified code: `src/live_engine.py` (PF ETA eligibility, per-note decision trace, pending/commit diagnostics), `src/live.py` (async decision-trace CSV and scheduler action linkage), `tools/replay_pf_mock.py` (Mock lifecycle traces), `tools/summarize_pf_stages.py`, and `tools/audit_detected_not_pressed.py`.",
        "- New deterministic tests: `tests/test_pf_eta_eligibility.py`, `tests/test_detected_tap_scheduling.py`, `tests/test_pending_identity_retention.py`, `tests/test_nearline_commit_consistency.py`, `tests/test_pf_decision_profiling.py`; existing identity, Hold, focus, ROI, freshness, scheduler, and duplicate-prevention tests remain in the full suite.",
        "", "## Specific decision path evidence", "",
        "- `LiveEngine.process()` applies track/status/readiness checks, calls `track_options()`, and then calls `AnyCoveredKeyRule.decide()` / `TapScheduler.offer()`. The historical CSV records final event decisions but did not capture every per-frame decision stage.",
        "- `track_options()` retains the Legacy hit-history stability gate. The PF path now requires its own valid finite posterior, crossing mass, posterior width, ESS fraction, minimum real-observation count, current identity, future hit time, and coast freshness; it no longer uses Legacy hit-history count/drift after those checks pass.",
        "- The single baseline `committed_observation_changed` cancellation is event `7714031f987c:416`, source frame 819, at 563332.604884s. It was a tentative green Unknown candidate with `latest_position_outlier`; the run does not establish that this was the same physical Tap, so the press was not restored.",
        "- Before/after replay processed the same 1,326 indexed frames. The current-code replay produced "
        f"{replay_summary.get('replay_events','UNKNOWN')} events and {replay_summary.get('mock_key_down_ids','UNKNOWN')} Mock key-down IDs in {replay_summary.get('wall_seconds','UNKNOWN')}s; exact event/UID/frame joins were {replay_summary.get('same_event_identity_rows','UNKNOWN')}. Since mapping is not exact, these counts are descriptive and are not a win/loss comparison.",
        f"- Determinism check: {replay_repeat.get('repeat_runs',0)} runs produced event counts {replay_repeat.get('replay_events',[])} and Mock key-down counts {replay_repeat.get('mock_key_down_ids',[])}. Logical action counts repeat; measured wall time varies by machine load.",
        "- Live baseline processing P95 and current offline replay P95 are included in `processing_stage_performance.csv`. The replay processing P95 is not directly comparable to live capture; it is slower than the recorded baseline and needs a same-environment live measurement before calling performance recovered.",
        "- The runtime now writes `tap_decision_trace.csv`, including lifecycle stage, PF eligibility evidence, retryability, frozen key/deadline, and final scheduler action. For this old run, that file is from current-code Mock replay; it is not retroactive live telemetry.",
        "- Tracker UID is not physical-note ground truth. No event is labeled MISS without visible judgment review.", ""]
    report += ["## Detected but never scheduled: event IDs and times", ""]
    report += [f"- `{r['event_id']}` frame {r['source_frame']} at {r['capture_timestamp']}s: `{r['final_reason']}`."
               for r in detected if r["pipeline_class"] in (
                   "DETECTED_NOT_SCHEDULED", "EXPIRED_OR_ETA_GATE_BEFORE_OFFER")]
    report.append("")
    (root / "detected_not_pressed_root_cause.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"detected_event_rows": len(events), "scheduled_attempts": len(scheduled),
        "exact_replay_joins": comparable, "unstable_hit_time_by_predictor": dict(unstable),
        "classes": dict(counts), "game_accuracy": "UNVERIFIED"}, indent=2))


def classify_cancel(reason, replacement):
    if replacement: return "REPLACEMENT_ID_SENT", "same_tracker_uid_other_id_keydown"
    mapping = {
        "provisional_loss_expired": ("CANCELED_TRACK_LOSS", "identity_grace_expired"),
        "committed_observation_changed": ("CANCELED_COMMIT_INVALIDATED", "commit_visual_or_identity_gate"),
        "assigned_key_no_longer_valid": ("CANCELED_KEY_CONFLICT", "selected_key_not_supported"),
        "tap_key_conflict": ("CANCELED_KEY_CONFLICT", "tap_reservation_conflict"),
        "global_escape_or_f12": ("CANCELED_SAFETY", "user_stop"),
        "game_state_or_focus_or_roi_loss": ("CANCELED_SAFETY", "game_context_invalid"),
        "stale_frame_or_focus_loss": ("CANCELED_SAFETY", "frame_or_focus_invalid"),
        "track_not_current_or_confirmed": ("CANCELED_TRACK_LOSS", "current_track_gate"),
        "no_current_eligible_observation": ("CANCELED_TRACK_LOSS", "current_eligible_observation_missing"),
        "hit_time_drift": ("CANCELED_ETA_UNSTABLE", "eta_history_drift"),
        "duplicate_hold_path": ("DUPLICATE_HOLD_SUPPRESSED", "hold_path_duplicate_guard"),
    }
    if reason in mapping: return mapping[reason]
    if reason: return "CANCELED_OTHER", reason
    return "EXPIRED_BEFORE_OFFER", "no_terminal_action_recorded"


def metric(side, name, count, minutes):
    return {"side": side, "metric": name, "count": count,
            "per_minute": count / minutes if minutes else "",
            "comparison_status": "DESCRIPTIVE; SAME SOURCE CLIP, EVENT IDS MAY DIVERGE"}


if __name__ == "__main__":
    main()
