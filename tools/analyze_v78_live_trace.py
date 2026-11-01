"""V7.8 evidence-first analysis of the recorded live identity trace.

The tool consumes the local trace CSVs from one run.  It never changes the
detector/tracker/scheduler and never sends input.  All joins use
``source_frame + capture_timestamp``; encoded video frame numbers are only
resolved through ``live_video_index.csv``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_v77_analysis import f, i, read_csv, write_csv

RUN_DEFAULT = ROOT / "output" / "run_20261031T201055_348946Z"
OUT_DEFAULT = ROOT / "output" / "v78_live_trace_root_cause"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(run: Path) -> dict[str, list[dict]]:
    names = [
        "live_video_index", "live_frames", "live_candidate_trace",
        "live_association_attempts", "live_track_identity", "live_events",
        "tap_intents", "tap_decisions", "tap_planner_shadow", "live_key_actions",
    ]
    return {name: read_csv(run / f"{name}.csv") for name in names}


def index_maps(rows: list[dict]) -> tuple[dict[tuple[str, str], dict], dict[str, dict]]:
    by_key = {}
    by_source = {}
    for row in rows:
        sf = str(row.get("source_frame", ""))
        ts = str(row.get("capture_timestamp", ""))
        by_key[(sf, ts)] = row
        by_source[sf] = row
    return by_key, by_source


def resolve_trace_rows(rows: list[dict], idx_by_key: dict, idx_by_source: dict) -> list[dict]:
    resolved = []
    for row in rows:
        out = dict(row)
        sf = str(row.get("source_frame", row.get("capture_sequence", "")))
        ts = str(row.get("capture_timestamp", ""))
        index = idx_by_key.get((sf, ts)) or idx_by_source.get(sf)
        out["source_video_frame_resolved"] = index.get("source_video_frame", index.get("video_frame", "")) if index else "UNKNOWN"
        out["video_frame_join_confidence"] = "HIGH" if index and (sf, ts) in idx_by_key else "SOURCE_FRAME_ONLY" if index else "UNKNOWN"
        resolved.append(out)
    return resolved


def trace_audit(run: Path, out: Path, data: dict, health: dict) -> dict:
    index = data["live_video_index"]
    frames = data["live_frames"]
    trace_sources = set()
    for name in ("live_candidate_trace", "live_association_attempts", "live_track_identity"):
        trace_sources.update(str(r.get("source_frame", r.get("capture_sequence", "")))
                            for r in data[name] if r.get("source_frame", r.get("capture_sequence", "")) != "")
    frame_states = defaultdict(Counter)
    for row in frames:
        frame_states[str(row.get("frame", ""))][row.get("gameplay_state", "")] += 1
    rows = []
    for frame in frames:
        sf = str(frame.get("frame", ""))
        trace_rows = sum(1 for name in ("live_candidate_trace", "live_association_attempts", "live_track_identity")
                         for row in data[name] if str(row.get("source_frame", row.get("capture_sequence", ""))) == sf)
        rows.append({"source_frame": sf, "capture_timestamp": frame.get("capture_timestamp", ""),
                     "gameplay_state": frame.get("gameplay_state", ""),
                     "focused": frame.get("focused", ""), "roi_status": frame.get("roi_status", ""),
                     "trace_row_count": trace_rows, "trace_covered": sf in trace_sources,
                     "reason_if_uncovered": "NO_TRACE_ROW_SUBMITTED" if not trace_rows else ""})
    write_csv(out / "trace_coverage_audit.csv", rows, list(rows[0]) if rows else ["source_frame"])
    by_state = Counter(row["gameplay_state"] for row in rows)
    uncovered = Counter(row["gameplay_state"] for row in rows if not row["trace_covered"])
    row_counts = {name: len(data[name]) for name in ("live_candidate_trace", "live_association_attempts", "live_track_identity")}
    sentinel = Counter(r.get("skip_reason", "") for r in data["live_association_attempts"] if r.get("skip_reason"))
    summary = {
        "run_id": run.name, "processed_frames": len(frames), "indexed_video_frames": len(index),
        "trace_covered_frames": len(trace_sources), "trace_uncovered_frames": len(rows) - len(trace_sources),
        "processed_state_counts": by_state, "uncovered_state_counts": uncovered,
        "trace_row_counts": row_counts, "health": health,
        "submitted_written_difference": int(health.get("submitted_rows", 0)) - int(health.get("written_rows", 0)),
        "csv_trace_rows_sum": sum(row_counts.values()),
        "sentinel_counts": sentinel,
        "diagnostic_cap_rows": Counter(r.get("trace_status", "") for name in ("live_candidate_trace", "live_association_attempts", "live_track_identity")
                                       for r in data[name] if "cap" in r.get("trace_status", "").lower()),
        "uncovered_frame_sample": [row["source_frame"] for row in rows if not row["trace_covered"]][:40],
        "interpretation": "Trace coverage is row-submission coverage, not processing-frame coverage; an empty frame can be validly uncovered.",
    }
    (out / "trace_integrity_summary.json").write_text(json.dumps(summary, indent=2, default=dict), encoding="utf-8")
    return summary


def uid_groups(data: dict, out: Path) -> tuple[list[dict], list[dict], list[dict]]:
    intents = data["tap_intents"]
    decisions = data["tap_decisions"]
    events = data["live_events"]
    tracks = data["live_track_identity"]
    pairs = data["live_association_attempts"]
    candidates = data["live_candidate_trace"]
    by_uid = defaultdict(list)
    for row in intents:
        by_uid[row.get("note_uid", "")].append(row)
    d_by_uid = defaultdict(list)
    for row in decisions:
        d_by_uid[row.get("note_uid", "")].append(row)
    e_by_uid = defaultdict(list)
    for row in events:
        e_by_uid[row.get("note_uid", row.get("event_id", ""))].append(row)
    tr_by_uid = defaultdict(list)
    for row in tracks:
        tr_by_uid[row.get("note_uid", "")].append(row)
    pair_by_track = defaultdict(list)
    for row in pairs:
        if row.get("track_id"):
            pair_by_track[row["track_id"]].append(row)
    candidate_by_key = defaultdict(list)
    for row in candidates:
        candidate_by_key[(str(row.get("source_frame", "")), row.get("candidate_id", ""))].append(row)

    root_rows = []
    for uid, irows in sorted(by_uid.items()):
        if not uid:
            continue
        irows = sorted(irows, key=lambda r: f(r.get("timestamp"), 0) or 0)
        drows = sorted(d_by_uid.get(uid, []), key=lambda r: f(r.get("timestamp"), 0) or 0)
        trows = sorted(tr_by_uid.get(uid, []), key=lambda r: f(r.get("capture_timestamp"), 0) or 0)
        states = {r.get("state", "") for r in irows}
        terminal = "FIRED" if "FIRED" in states else "CONFIRMED_NOT_FIRED" if "CONFIRMED" in states else "DETECTED_ONLY"
        track_ids = sorted({r.get("track_id", "") for r in trows if r.get("track_id")})
        last_real = [r for r in trows if str(r.get("real_observation_this_frame", "")).lower() == "true"]
        last_real_row = last_real[-1] if last_real else (trows[-1] if trows else {})
        lost = next((r for r in trows if r.get("track_status") in {"lost", "completed"} or r.get("termination_reason")), None)
        track_id = track_ids[0] if track_ids else "UNKNOWN"
        p_rows = pair_by_track.get(track_id, [])
        reject_counts = Counter(r.get("reject_reason", "") for r in p_rows if r.get("reject_reason"))
        accepted = [r for r in p_rows if str(r.get("accepted", "")).lower() == "true"]
        local_candidates = []
        for tr in trows:
            cid = tr.get("candidate_id", "")
            local_candidates.extend(candidate_by_key.get((str(tr.get("source_frame", "")), cid), []))
        local_rejects = Counter(r.get("reject_reason", "") for r in local_candidates if r.get("reject_reason"))
        reasons = [r.get("reason", "") for r in drows if r.get("reason")]
        blocker = classify_blocker(terminal, irows, drows, trows, reasons)
        root_rows.append({
            "physical_note_id": "UNKNOWN", "note_uid": uid, "terminal_group": terminal,
            "appearance": (e_by_uid.get(uid) or [{}])[0].get("appearance", "UNKNOWN"),
            "track_id": track_id, "track_ids": "|".join(track_ids),
            "last_real_source_frame": last_real_row.get("source_frame", "UNKNOWN"),
            "last_real_capture_timestamp": last_real_row.get("capture_timestamp", "UNKNOWN"),
            "last_real_candidate_id": last_real_row.get("candidate_id", "UNKNOWN"),
            "first_lost_source_frame": lost.get("source_frame", "") if lost else "",
            "first_lost_capture_timestamp": lost.get("capture_timestamp", "") if lost else "",
            "first_causal_blocker": blocker[0], "secondary_blockers": blocker[1],
            "evidence": blocker[2], "counterevidence": blocker[3], "confidence": blocker[4],
            "pair_count": len(p_rows), "accepted_pair_count": len(accepted),
            "pair_reject_reasons": json.dumps(reject_counts, default=dict),
            "local_detector_reject_reasons": json.dumps(local_rejects, default=dict),
            "last_recoverable_time": blocker[5], "first_failed_time": blocker[6],
            "time_to_target_ms": "UNKNOWN", "trace_reference": f"track={track_id};uid={uid}",
        })
    fields = list(root_rows[0]) if root_rows else ["note_uid"]
    write_csv(out / "uid_root_cause_195.csv", root_rows, fields)
    unconfirmed = [r for r in root_rows if r["terminal_group"] == "DETECTED_ONLY"]
    confirmed = [r for r in root_rows if r["terminal_group"] == "CONFIRMED_NOT_FIRED"]
    write_csv(out / "unconfirmed_121_cases.csv", unconfirmed, fields)
    write_csv(out / "confirmed_not_fired_24_cases.csv", confirmed, fields)
    counts = Counter(r["first_causal_blocker"] for r in root_rows)
    (out / "first_causal_blocker_counts.json").write_text(json.dumps({"counts": counts, "game_accuracy": "UNKNOWN"}, indent=2, default=dict), encoding="utf-8")
    links = []
    for row in root_rows:
        links.append({"physical_note_id": row["physical_note_id"], "note_uid": row["note_uid"],
                      "track_id": row["track_id"], "candidate_id": row["last_real_candidate_id"],
                      "source_frame": row["last_real_source_frame"], "capture_timestamp": row["last_real_capture_timestamp"],
                      "confidence": row["confidence"], "mapping_basis": "track_identity + source_frame + capture_timestamp",
                      "physical_truth": "UNKNOWN"})
    write_csv(out / "candidate_track_uid_links.csv", links, list(links[0]) if links else ["note_uid"])
    return root_rows, unconfirmed, confirmed


def classify_blocker(terminal, irows, drows, trows, reasons):
    states = {r.get("state", "") for r in irows}
    ordered = []
    for reason in reasons:
        if reason not in ordered and reason not in {"simple_track_created", "ordinary_tap_motion_confirmed", "scheduler_accepted", "deadline_updated"}:
            ordered.append(reason)
    last = trows[-1] if trows else {}
    last_time = last.get("capture_timestamp", "")
    first_failed = ""
    if terminal == "FIRED":
        return ("KEY_DOWN_LOGGED_GAME_TRUTH_UNKNOWN", "|".join(ordered),
                "FIRED/key_down lifecycle evidence", "No game judgment truth in run", "MEDIUM", last_time, first_failed)
    if terminal == "CONFIRMED_NOT_FIRED":
        if any(r.get("termination_reason") == "track_expired_max_gap" for r in trows):
            return ("TRACK_COAST_TIMEOUT", "|".join(ordered), "Confirmed UID has max-gap termination", "Earlier observations were recoverable", "MEDIUM", last_time, first_failed)
        for gate in ("PF_NO_VALID_CROSSING", "particle_posterior_too_wide", "eta_outside_horizon",
                     "below_event_min_y", "ALREADY_PAST_TRIGGER", "hit_time_not_future"):
            if gate in ordered:
                return (gate, "|".join(r for r in ordered if r != gate), f"Confirmed decision rows contain {gate}", "No physical-note truth", "LOW", last_time, first_failed)
        return ("CONFIRMED_NOT_CURRENT", "|".join(ordered), "Confirmed but no FIRED transition", "Scheduler/input delivery may be incomplete", "LOW", last_time, first_failed)
    if any(r.get("termination_reason") == "track_expired_max_gap" for r in trows):
        return ("TRACK_COAST_TIMEOUT", "|".join(ordered), "Track terminated after max gap", "No physical-note mapping", "LOW", last_time, first_failed)
    if ordered:
        return ("NOT_ENOUGH_OBSERVATIONS", "|".join(ordered), "UID never reached confirmed lifecycle", "Detector candidates and track rows exist", "LOW", last_time, first_failed)
    return ("UNKNOWN", "", "No causal gate can be proved from UID trace", "No physical-note annotation", "UNKNOWN", last_time, first_failed)


def physical_cases(run: Path, out: Path, data: dict, root_rows: list[dict]) -> list[dict]:
    index = data["live_video_index"]
    index_by_source = {str(r.get("source_frame")): r for r in index}
    traces = [r for r in data["live_candidate_trace"] if r.get("stage") == "candidate_final"]
    tracks = data["live_track_identity"]
    track_by_key = {(str(r.get("source_frame")), r.get("candidate_id", "")): r for r in tracks if r.get("candidate_id")}
    first_ts = f(index[0].get("capture_timestamp"), 0) if index else 0
    selected = []
    seen_tracks = set()
    # Spread local review cases over the visible section and preserve all pink/neutral candidates.
    priority = sorted(traces, key=lambda r: (r.get("appearance") not in {"neutral_candidate", "pink_candidate"},
                                             float(r.get("capture_timestamp") or 0)))
    for row in priority:
        sf = str(row.get("source_frame", ""))
        tr = track_by_key.get((sf, row.get("candidate_id", "")), {})
        tid = tr.get("track_id", "")
        if tid in seen_tracks:
            continue
        rel = (f(row.get("capture_timestamp"), first_ts) or first_ts) - first_ts
        if 5.0 <= rel <= 17.0 or row.get("appearance") in {"neutral_candidate", "pink_candidate"}:
            seen_tracks.add(tid)
            selected.append((row, tr))
        if len(selected) >= 40:
            break
    cases = []
    for n, (row, tr) in enumerate(selected, 1):
        cid = f"v78_pn_{n:03d}"
        idx = index_by_source.get(str(row.get("source_frame")), {})
        cases.append({"physical_note_id": cid, "source_video_frame_first": idx.get("source_video_frame", "UNKNOWN"),
                      "source_video_frame_last": idx.get("source_video_frame", "UNKNOWN"),
                      "capture_timestamp_first": row.get("capture_timestamp", ""),
                      "capture_timestamp_last": row.get("capture_timestamp", ""),
                      "approx_judgment_frame": "UNKNOWN", "appearance": row.get("appearance", "UNKNOWN"),
                      "note_type": row.get("note_type", "unknown"),
                      "bbox_or_polygon": row.get("core_bbox", row.get("raw_bbox", "")),
                      "lane_or_key_span": row.get("candidate_keys", ""),
                      "replay_track_id": tr.get("track_id", "UNKNOWN"),
                      "note_uid": tr.get("note_uid", "UNKNOWN"),
                      "candidate_id": row.get("candidate_id", "UNKNOWN"),
                      "visual_evidence": f"case_crops/{cid}_first.jpg",
                      "confidence": "UNREVIEWED", "reviewer_status": "UNREVIEWED", "game_judgment": "UNKNOWN"})
    fields = list(cases[0]) if cases else ["physical_note_id"]
    write_csv(out / "physical_notes_review.csv", cases, fields)
    write_csv(out / "gray_physical_cases.csv", [r for r in cases if r["appearance"] == "neutral_candidate"], fields)
    write_csv(out / "pink_physical_cases.csv", [r for r in cases if r["appearance"] == "pink_candidate"], fields)
    overlap = [r for r in cases if r["candidate_id"] and any(x.get("candidate_id") == r["candidate_id"] and x.get("reject_reason") == "nested_suppression" for x in data["live_candidate_trace"])]
    write_csv(out / "overlap_physical_cases.csv", overlap, fields)
    crops = out / "case_crops"
    crops.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(run / "live_source.mp4"))
    # The top-level run may keep CSVs while the source video remains in assist.
    source = run / "live_source.mp4"
    if not source.exists():
        source = ROOT / "output" / "assist" / run.name / "live_source.mp4"
    cap.release()
    cap = cv2.VideoCapture(str(source))
    if cap.isOpened():
        for case in cases:
            vf = i(case["source_video_frame_first"], None)
            if vf is None:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, vf)
            ok, image = cap.read()
            if not ok:
                continue
            cv2.rectangle(image, (0, 0), (720, 24), (0, 0, 0), -1)
            cv2.putText(image, f"{case['physical_note_id']} vf={vf} {case['appearance']} UNREVIEWED", (5, 17),
                        cv2.FONT_HERSHEY_SIMPLEX, .40, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imwrite(str(crops / f"{case['physical_note_id']}_first.jpg"), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cap.release()
    (out / "paired_miss_timeline.md").write_text(
        "# V7.8 paired miss timeline\n\n"
        "The CSV is a local review corpus, not an automatic physical-note truth set. "
        "Every case remains `UNREVIEWED`/`UNKNOWN` until a human verifies adjacent frames and game judgment. "
        "Pink candidates are treated as ordinary Tap; no Flick semantics are introduced.\n", encoding="utf-8")
    return cases


def scheduler_artifacts(out: Path, data: dict, confirmed: list[dict]) -> None:
    decisions = data["tap_decisions"]
    intents = data["tap_intents"]
    actions = data["live_key_actions"]
    eta = data["tap_planner_shadow"]
    by_uid = defaultdict(list)
    for row in decisions:
        by_uid[row.get("note_uid", "")].append(row)
    timeline = []
    for case in confirmed:
        uid = case["note_uid"]
        rows = sorted(by_uid.get(uid, []), key=lambda r: f(r.get("timestamp"), 0) or 0)
        accepted = [r for r in rows if r.get("reason") == "scheduler_accepted"]
        timeline.append({"note_uid": uid, "track_id": case["track_id"], "appearance": case["appearance"],
                         "first_confirmed": next((r.get("timestamp") for r in rows if r.get("lifecycle_state") == "TRACK_CONFIRMED"), "UNKNOWN"),
                         "last_current": case["last_real_capture_timestamp"],
                         "first_eligible_to_schedule": accepted[0].get("timestamp", "UNKNOWN") if accepted else "UNKNOWN",
                         "first_proposed_hit_at": accepted[0].get("hit_at", "UNKNOWN") if accepted else "UNKNOWN",
                         "legacy_reasons": "|".join(dict.fromkeys(r.get("reason", "") for r in rows if r.get("reason"))),
                         "shadow_proposal": "UNKNOWN", "scheduler_input": "UNKNOWN",
                         "last_tracker_observation": case["last_real_source_frame"],
                         "cancel_or_key_down": "UNKNOWN", "game_judgment": "UNKNOWN"})
    fields = list(timeline[0]) if timeline else ["note_uid"]
    write_csv(out / "confirmed_24_event_timeline.csv", timeline, fields)
    audit = []
    for row in actions:
        audit.append({**row, "input_attempted": row.get("action") in {"key_down", "key_up"},
                      "input_api_result": "CALL_LOG_ONLY", "delivery_status": "DELIVERY_UNVERIFIED",
                      "game_judgment": "UNKNOWN"})
    write_csv(out / "scheduler_input_delivery_audit.csv", audit, list(audit[0]) if audit else ["action"])
    pf_rows = [r for r in data["tap_decisions"] if r.get("reason") in {
        "PF_NO_VALID_CROSSING", "particle_posterior_too_wide", "eta_outside_horizon", "eta_uncertainty_too_high",
        "hit_time_not_future", "ALREADY_PAST_TRIGGER"}]
    write_csv(out / "pf_eta_gate_cases.csv", pf_rows, list(pf_rows[0]) if pf_rows else ["note_uid", "reason"])
    hold_rows = [r for r in actions if r.get("lifecycle_state", "").startswith("HOLD") or r.get("note_type") == "hold"]
    collisions = []
    for tap in actions:
        if tap.get("action") not in {"key_down", "scheduled"} or tap.get("note_type") == "hold":
            continue
        t = f(tap.get("timestamp"), None)
        if t is None:
            continue
        for hold in hold_rows:
            ht = f(hold.get("timestamp"), None)
            if ht is not None and tap.get("key") == hold.get("key") and abs(t - ht) < .12:
                collisions.append({"tap_event_id": tap.get("event_id"), "hold_event_id": hold.get("event_id"),
                                   "key": tap.get("key"), "tap_timestamp": tap.get("timestamp"),
                                   "hold_timestamp": hold.get("timestamp"), "window_ms": abs(t - ht) * 1000,
                                   "classification": "POTENTIAL_COLLISION_REVIEW", "game_judgment": "UNKNOWN"})
    write_csv(out / "hold_tap_collision_cases.csv", collisions,
              list(collisions[0]) if collisions else ["tap_event_id", "hold_event_id", "classification"])


def ab_and_report(run: Path, out: Path, data: dict, summary: dict, roots: list[dict], cases: list[dict]) -> None:
    terminal = Counter(r["terminal_group"] for r in roots)
    blocker = Counter(r["first_causal_blocker"] for r in roots)
    physical = Counter(r["appearance"] for r in cases)
    (out / "v78_patch_ab.json").write_text(json.dumps({
        "status": "PATCH_NOT_JUSTIFIED", "baseline": "existing Legacy + PF path",
        "patch_off": "same as baseline", "patch_on": "NOT_RUN; no qualifying HIGH-confidence physical cases",
        "physical_case_count": len(cases), "physical_case_appearances": physical,
        "negative_controls": "see negative_controls.csv", "game_accuracy": "UNKNOWN",
        "reason": "Cases are unreviewed and geometry is pending_calibration; no active repair is safe.",
    }, indent=2, default=dict), encoding="utf-8")
    review_fields = list(cases[0]) if cases else ["physical_note_id"]
    ab_rows = [{**case, "variant": "baseline", "scheduled": "UNKNOWN", "duplicate_schedule": "UNKNOWN",
                "uid_identity": "REPLAY_ONLY", "game_judgment": "UNKNOWN"} for case in cases]
    write_csv(out / "physical_note_ab.csv", ab_rows, review_fields + ["variant", "scheduled", "duplicate_schedule", "uid_identity", "game_judgment"])
    controls = [r for r in roots if r["terminal_group"] == "FIRED"][:5]
    write_csv(out / "negative_controls.csv", [{"note_uid": r["note_uid"], "track_id": r["track_id"],
                                                "appearance": r["appearance"], "control_status": "FIRED_LIFECYCLE_ONLY",
                                                "game_judgment": "UNKNOWN"} for r in controls],
              ["note_uid", "track_id", "appearance", "control_status", "game_judgment"])
    (out / "V7_8_ROOT_CAUSE_AND_FIX_REPORT.md").write_text(
        "# HoloDream V7.8 Live Trace Root Cause and Fix Report\n\n"
        f"- Source run: `{run}`\n- Source SHA manifest: `v78_manifest.json`\n"
        f"- Trace coverage: {summary['trace_covered_frames']} frames with submitted telemetry rows out of {summary['processed_frames']} processed frames; "
        f"{summary['trace_uncovered_frames']} frames had no submitted diagnostic row. This is not automatically data loss.\n"
        f"- Trace rows: candidate={summary['trace_row_counts']['live_candidate_trace']}, association={summary['trace_row_counts']['live_association_attempts']}, "
        f"track={summary['trace_row_counts']['live_track_identity']}; health submitted/written={summary['health'].get('submitted_rows')}/{summary['health'].get('written_rows')}; "
        f"dropped={summary['health'].get('dropped_diagnostic_rows')}.\n\n"
        "## UID funnel\n\n"
        f"{dict(terminal)}. These are software UID groups, not physical-note count or accuracy.\n\n"
        "## Root-cause classification\n\n"
        f"{dict(blocker)}. Each row includes evidence, counterevidence, frame, timestamp, candidate/track references and confidence in `uid_root_cause_195.csv`. "
        "`track_not_current_confirmed` is not used as a complete root cause.\n\n"
        "## Physical review\n\n"
        f"The review corpus contains {len(cases)} local cases: {dict(physical)}. They are all `UNREVIEWED` and game judgment is `UNKNOWN`; "
        "the local IDs are not official game IDs. Pink is treated as ordinary Tap. Contact crops are in `case_crops/`.\n\n"
        "## Patch decision\n\n"
        "`PATCH_NOT_JUSTIFIED`: no two HIGH-confidence, manually verified physical notes with the same irreversible blocker are available. "
        "No Detector/Tracker/PF/Planner/Scheduler/Hold threshold was changed, no Active Shadow path was enabled, and no FPS/drop policy was changed.\n\n"
        "## Next single user action\n\n"
        "Review `physical_notes_review.csv` and the corresponding `case_crops/` adjacent frames, filling only physical_note_id, reviewer_status, confidence and game_judgment. "
        "Do not change config or record another run yet.\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=RUN_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    run, out = args.run, args.out
    out.mkdir(parents=True, exist_ok=True)
    data = load(run)
    idx_by_key, idx_by_source = index_maps(data["live_video_index"])
    for name in ("live_candidate_trace", "live_association_attempts", "live_track_identity"):
        data[name] = resolve_trace_rows(data[name], idx_by_key, idx_by_source)
    health = json.loads((run / "live_identity_trace_health.json").read_text(encoding="utf-8"))
    summary = trace_audit(run, out, data, health)
    roots, unconfirmed, confirmed = uid_groups(data, out)
    cases = physical_cases(run, out, data, roots)
    scheduler_artifacts(out, data, confirmed)
    source = run / "live_source.mp4"
    if not source.exists():
        source = ROOT / "output" / "assist" / run.name / "live_source.mp4"
    overlay = run / "live_overlay.mp4"
    if not overlay.exists():
        overlay = ROOT / "output" / "assist" / run.name / "live_overlay.mp4"
    files = ["live_video_index.csv", "live_candidate_trace.csv", "live_association_attempts.csv",
             "live_track_identity.csv", "live_events.csv", "tap_intents.csv", "tap_decisions.csv",
             "tap_planner_shadow.csv", "live_key_actions.csv", "live_frames.csv", "live_run.json", "run_metrics.json"]
    hashes = {name: digest(run / name) for name in files if (run / name).exists()}
    if source.exists():
        hashes["live_source.mp4"] = digest(source)
    if overlay.exists():
        hashes["live_overlay.mp4"] = digest(overlay)
    (out / "v78_manifest.json").write_text(json.dumps({
        "plan": "V7.8_LIVE_TRACE_ROOT_CAUSE_AND_FIX",
        "baseline_commit": "fcc614cf3e20044031be5df19fad264c9bd93adc",
        "run": str(run), "source_video": str(source), "overlay_video": str(overlay), "sha256": hashes,
        "trace_health": health, "trace_summary": summary,
        "timestamp_join": "source_frame + capture_timestamp -> live_video_index; no frame/60 timing",
        "geometry_status": "pending_calibration", "game_accuracy": "UNKNOWN",
    }, indent=2, default=dict), encoding="utf-8")
    (out / "pytest_v78.txt").write_text("Run `py -m pytest -q` after analysis.\n", encoding="utf-8")
    ab_and_report(run, out, data, summary, roots, cases)
    print(json.dumps({"out": str(out), "uid_groups": Counter(r["terminal_group"] for r in roots),
                      "trace": summary, "review_cases": len(cases)}, indent=2, default=dict))


if __name__ == "__main__":
    main()
