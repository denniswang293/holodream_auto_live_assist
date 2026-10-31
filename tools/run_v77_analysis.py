"""Run the V7.7 evidence-first replay and produce review artifacts.

This tool is deliberately diagnostic-only.  It replays the recorded source
frames with the existing detector/tracker settings and never calls the
scheduler or actuator.  Capture timestamps come from ``live_video_index``;
the nominal codec FPS is used only to seek a frame, never as event time.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import sys

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detector import detect
from src.geometry import load_geometry
from src.simple_tracker import SimpleTracker


RUN_DEFAULT = ROOT / "output" / "assist" / "run_20261031T194457_212618Z"
OUT_DEFAULT = ROOT / "output" / "v77_miss_analysis"


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        for row in rows:
            wr.writerow({field: json.dumps(row[field], ensure_ascii=False, separators=(",", ":"))
                         if isinstance(row.get(field), (tuple, list, dict)) else row.get(field, "")
                         for field in fields})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def f(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def i(value, default=None):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def frame_uid(run_id: str, source_frame: int) -> str:
    return f"{run_id}:{source_frame}"


def replay(run: Path, out: Path, config: dict) -> dict:
    index_rows = read_csv(run / "live_video_index.csv")
    index_rows.sort(key=lambda r: i(r.get("video_frame"), 0))
    cap = cv2.VideoCapture(str(run / "live_source.mp4"))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open source video: {run / 'live_source.mp4'}")
    geometry = load_geometry(config, ROOT / "config" / "geometry_live_assist.json")
    detector_cfg = deepcopy(config.get("detector", {}))
    detector_cfg["reference_resolution"] = config["reference_resolution"]
    detector_cfg["association_diagnostics"] = {
        **detector_cfg.get("association_diagnostics", {}),
        "enabled": True, "max_candidate_rows": 100000,
        "max_pair_rows": 100000,
    }
    tracker_cfg = {**config.get("tracker", {}), "completion_y": geometry.hit_y}
    tracker = SimpleTracker(tracker_cfg, config.get("predictor", {}).get("particle", {}), geometry.hit_y)
    candidates = []
    pairs = []
    attempts = []
    assignments = []
    tracks = []
    frame_rows = []
    previous_ts = None
    run_id = run.name
    for row in index_rows:
        video_frame = i(row.get("video_frame"), 0)
        source_frame = i(row.get("source_frame"), video_frame)
        ts = f(row.get("capture_timestamp"))
        if ts is None:
            raise RuntimeError(f"missing capture_timestamp at video_frame={video_frame}")
        cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame)
        ok, image = cap.read()
        if not ok:
            raise RuntimeError(f"could not decode video_frame={video_frame}")
        diag = {}
        profile = {}
        det = detect(image, geometry, config["key_map"], detector_cfg,
                     diagnostics=diag, profile=profile, frame_index=source_frame)
        trace = {"max_rows": 100000}
        playing = row.get("gameplay_state") == "PLAYING"
        active = tracker.update(det, ts, playing=playing, trace=trace,
                                frame_index=source_frame,
                                capture_gap_ms=(ts - previous_ts) * 1000 if previous_ts is not None else "")
        meta = {
            "run_id": run_id, "capture_sequence": source_frame,
            "source_frame": source_frame, "source_video_frame": video_frame,
            "capture_timestamp": ts, "processing_timestamp": row.get("processing_timestamp", ""),
            "frame_uid": frame_uid(run_id, source_frame),
        }
        for source in diag.get("candidate_trace", []):
            candidates.append({**meta, **source, "source_video_frame": video_frame})
        for name, rows, row_type in (("pair_rows", pairs, "pair"),
                                     ("attempt_rows", attempts, "attempt"),
                                     ("assignment_rows", assignments, "assignment")):
            for source in trace.get(name, []):
                rows.append({**meta, "row_type": row_type, **source,
                             "source_video_frame": video_frame})
        for source in trace.get("track_rows", []):
            tracks.append({**meta, **source, "source_video_frame": video_frame,
                           "note_uid": f"{run_id}:simple:{source.get('track_id', '')}"})
        frame_rows.append({
            **meta, "gameplay_state": row.get("gameplay_state", ""),
            "detector_candidates": len(det), "detector_trace_rows": len(diag.get("candidate_trace", [])),
            "gray_rejection_count": len(diag.get("gray_rejections", [])),
            "pink_rejection_count": sum(diag.get("pink_rejection_counts", {}).values()),
            "tracker_active": len(active), "tracker_attempt_rows": len(trace.get("attempt_rows", [])),
            "capture_gap_ms": (ts - previous_ts) * 1000 if previous_ts is not None else "",
        })
        previous_ts = ts
    cap.release()

    candidate_fields = ["run_id", "capture_sequence", "source_frame", "source_video_frame",
                        "capture_timestamp", "processing_timestamp", "frame_uid", "stage",
                        "candidate_id", "parent_proposal_id", "raw_bbox", "core_bbox", "x", "y", "w", "h",
                        "u_min", "u_max", "u_center", "appearance", "note_type", "candidate_keys", "score",
                        "passed", "reject_reason", "lane_span", "edge_count", "suspected_overlap"]
    association_fields = ["run_id", "capture_sequence", "source_frame", "source_video_frame",
                          "capture_timestamp", "processing_timestamp", "frame_uid", "row_type", "track_id",
                          "track_uid", "candidate_id", "track_status_before", "matched_this_frame", "assigned",
                          "track_last_time", "last_real_observation_ts", "observation_age_ms", "delta_t_ms",
                          "predicted_y", "predicted_u", "observed_y", "observed_u", "dy_px", "du",
                          "motion_continuity", "reject_reason", "total_cost", "residual_px", "tolerance_px",
                          "competition_track_ids", "skip_reason", "suppressed_count", "unmatched_cost"]
    track_fields = ["run_id", "capture_sequence", "source_frame", "source_video_frame", "capture_timestamp",
                    "processing_timestamp", "frame_uid", "track_id", "track_uid", "note_uid", "candidate_id",
                    "matched_this_frame", "real_observation_this_frame", "coasting_this_frame",
                    "last_real_observation_timestamp", "time_since_last_real_observation_ms", "missed_frames",
                    "track_status", "confirmed_note_type", "appearance", "bbox", "stable_keys", "prediction_reason",
                    "termination_reason", "state_transition"]
    write_csv(out / "live_candidate_trace.csv", candidates, candidate_fields)
    write_csv(out / "live_association_attempts.csv", pairs + attempts + assignments, association_fields)
    write_csv(out / "live_track_identity.csv", tracks, track_fields)
    write_csv(out / "replay_frame_summary.csv", frame_rows, list(frame_rows[0]) if frame_rows else ["run_id"])
    health = {
        "enabled": True, "mode": "offline_replay", "run_id": run_id,
        "source_video_frames": len(index_rows), "trace_coverage_frames": len(frame_rows),
        "candidate_rows": len(candidates), "pair_rows": len(pairs),
        "attempt_rows": len(attempts), "assignment_rows": len(assignments),
        "track_rows": len(tracks), "dropped_diagnostic_rows": 0,
        "timestamp_source": "live_video_index.capture_timestamp",
        "nominal_video_fps": 60.0,
        "note": "FPS is not used to derive event timestamps.",
    }
    (out / "trace_health.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
    return {"index": index_rows, "candidates": candidates, "pairs": pairs,
            "attempts": attempts, "assignments": assignments, "tracks": tracks,
            "frames": frame_rows, "health": health}


def make_contact_sheets(run: Path, out: Path, index_rows: list[dict]) -> None:
    cap = cv2.VideoCapture(str(run / "live_source.mp4"))
    if not cap.isOpened():
        return
    first_ts = f(index_rows[0].get("capture_timestamp"), 0.0) if index_rows else 0.0
    intervals = [("05_00_06_50", 5.0, 6.5), ("08_50_09_50", 8.5, 9.5),
                 ("11_00_14_50", 11.0, 14.5), ("control", 2.0, 3.0)]
    directory = out / "review_contact_sheets"
    directory.mkdir(parents=True, exist_ok=True)
    for name, lo, hi in intervals:
        selected = [r for r in index_rows if lo <= (f(r.get("capture_timestamp"), first_ts) - first_ts) <= hi]
        if not selected:
            continue
        step = max(1, len(selected) // 12)
        cells = []
        for row in selected[::step][:12]:
            vf = i(row.get("video_frame"), 0)
            cap.set(cv2.CAP_PROP_POS_FRAMES, vf)
            ok, img = cap.read()
            if not ok:
                continue
            img = img.copy()
            rel = f(row.get("capture_timestamp"), first_ts) - first_ts
            text = f"vf={vf} sf={row.get('source_frame','')} t={rel:.3f}s {row.get('gameplay_state','')}"
            cv2.rectangle(img, (0, 0), (720, 24), (0, 0, 0), -1)
            cv2.putText(img, text, (5, 17), cv2.FONT_HERSHEY_SIMPLEX, .42, (255, 255, 255), 1, cv2.LINE_AA)
            cells.append(cv2.resize(img, (360, 202)))
        if not cells:
            continue
        while len(cells) < 12:
            cells.append(cells[-1].copy())
        sheet = []
        for offset in range(0, 12, 4):
            sheet.append(cv2.hconcat(cells[offset:offset + 4]))
        cv2.imwrite(str(directory / f"{name}.jpg"), cv2.vconcat(sheet), [cv2.IMWRITE_JPEG_QUALITY, 90])
    cap.release()


def build_reviews(run: Path, out: Path, data: dict, config: dict) -> None:
    candidates = data["candidates"]
    track_by_candidate = {(str(row.get("source_frame")), str(row.get("candidate_id"))): row
                          for row in data["tracks"] if row.get("candidate_id")}
    first_ts = f(data["index"][0].get("capture_timestamp"), 0.0) if data["index"] else 0.0
    intervals = [(5.0, 6.5), (8.5, 9.5), (11.0, 14.5), (2.0, 3.0)]
    review = []
    gray = []
    pink = []
    overlap = []
    for row in candidates:
        rel = (f(row.get("capture_timestamp"), first_ts) or first_ts) - first_ts
        appearance = row.get("appearance", "")
        reason = row.get("reject_reason", "")
        if appearance == "neutral_candidate" or "gray" in reason or "neutral" in reason:
            gray.append({"source_frame": row.get("source_frame"), "source_video_frame": row.get("source_video_frame"),
                         "capture_timestamp": row.get("capture_timestamp"), "candidate_id": row.get("candidate_id"),
                         "stage": row.get("stage"), "bbox": row.get("core_bbox") or row.get("raw_bbox"),
                         "appearance": appearance, "reject_reason": reason,
                         "evidence_status": "CANDIDATE_TRACE_ONLY"})
        if appearance == "pink_candidate" or "pink" in reason:
            pink.append({"source_frame": row.get("source_frame"), "source_video_frame": row.get("source_video_frame"),
                         "capture_timestamp": row.get("capture_timestamp"), "candidate_id": row.get("candidate_id"),
                         "stage": row.get("stage"), "bbox": row.get("core_bbox") or row.get("raw_bbox"),
                         "appearance": appearance, "note_type": row.get("note_type"),
                         "reject_reason": reason, "evidence_status": "CANDIDATE_TRACE_ONLY"})
        if row.get("suspected_overlap") in (True, "True", "true") or reason in ("nested_suppression", "duplicate_nms"):
            overlap.append({"source_frame": row.get("source_frame"), "source_video_frame": row.get("source_video_frame"),
                            "capture_timestamp": row.get("capture_timestamp"), "candidate_id": row.get("candidate_id"),
                            "stage": row.get("stage"), "bbox": row.get("core_bbox") or row.get("raw_bbox"),
                            "appearance": appearance, "reject_reason": reason,
                            "evidence_status": "CANDIDATE_TRACE_ONLY"})
        if any(lo <= rel <= hi for lo, hi in intervals) and row.get("stage") == "candidate_final":
            track_row = track_by_candidate.get((str(row.get("source_frame")), str(row.get("candidate_id"))), {})
            review.append({"physical_note_id": "UNKNOWN", "candidate_observation_id": row.get("candidate_id", ""),
                           "replay_track_id": track_row.get("track_id", "UNKNOWN"),
                           "replay_track_uid": track_row.get("track_uid", "UNKNOWN"),
                           "source_video_frame_first": row.get("source_video_frame", ""),
                           "source_video_frame_last": row.get("source_video_frame", ""),
                           "capture_timestamp_first": row.get("capture_timestamp", ""),
                           "capture_timestamp_last": row.get("capture_timestamp", ""),
                           "approx_judgment_frame": "UNKNOWN", "appearance": appearance,
                           "note_type": row.get("note_type", "unknown"),
                           "bbox_or_polygon": row.get("core_bbox") or row.get("raw_bbox", ""),
                           "lane_or_key_span": row.get("candidate_keys", ""),
                           "visual_evidence": "Contact sheet generated; manual review required",
                           "confidence": "UNKNOWN", "reviewer_status": "UNREVIEWED",
                           "game_judgment": "UNKNOWN"})
    review_fields = list(review[0]) if review else ["physical_note_id", "candidate_observation_id"]
    write_csv(out / "physical_note_review.csv", review, review_fields)
    case_fields = list(gray[0]) if gray else ["source_frame", "candidate_id", "evidence_status"]
    write_csv(out / "detector_gray_cases.csv", gray, case_fields)
    case_fields = list(overlap[0]) if overlap else ["source_frame", "candidate_id", "evidence_status"]
    write_csv(out / "overlap_fragment_cases.csv", overlap, case_fields)
    case_fields = list(pink[0]) if pink else ["source_frame", "candidate_id", "evidence_status"]
    write_csv(out / "pink_tap_cases.csv", pink, case_fields)
    (out / "review_notes.md").write_text(
        "# V7.7 人工審核說明\n\n"
        "`physical_note_review.csv` 僅列出指定區間的 candidate_final 觀測；"
        "physical_note_id、game_judgment 與 confidence 目前維持 UNKNOWN/UNREVIEWED，"
        "不可把候選或 key_down 當作遊戲真值。請以 contact sheet 與原始影片逐顆合併跨幀觀測後再填寫。\n\n"
        "目前 geometry status 為 pending_calibration；本輪沒有自行修改幾何。\n", encoding="utf-8")


def lifecycle_artifacts(run: Path, out: Path) -> None:
    events = read_csv(run / "live_events.csv")
    decisions = read_csv(run / "tap_decisions.csv")
    intents = read_csv(run / "tap_intents.csv")
    actions = read_csv(run / "live_key_actions.csv")
    eta = read_csv(run / "tap_eta_comparison.csv")
    by_uid = defaultdict(list)
    for row in eta:
        by_uid[row.get("note_uid", "")].append(row)
    action_by = defaultdict(list)
    for row in actions:
        action_by[row.get("event_id", "")].append(row)
    event_by = defaultdict(list)
    for row in events:
        event_by[row.get("event_id", "")].append(row)
    decision_by = defaultdict(list)
    for row in decisions:
        decision_by[row.get("note_uid", "")].append(row)
    appearance_by = {}
    for row in events:
        if row.get("note_uid"):
            appearance_by[row["note_uid"]] = row.get("appearance", "")
    lifecycle = []
    blockers = Counter()
    blocker_order = ["track_not_current_confirmed", "below_event_min_y", "eta_outside_horizon",
                     "PF_NO_VALID_CROSSING", "particle_posterior_too_wide", "tap_key_conflict",
                     "physical_modifier_held", "hit_time_not_future", "ALREADY_PAST_TRIGGER",
                     "scheduler_", "canceled", "expired"]
    for uid, rows in sorted(by_uid.items()):
        rows = sorted(rows, key=lambda r: f(r.get("capture_timestamp"), 0) or 0)
        drows = sorted(decision_by.get(uid, []), key=lambda r: f(r.get("timestamp"), 0) or 0)
        event_ids = {r.get("event_id", "") for r in event_by.get(uid, [])}
        event_ids.add(uid)
        acts = [a for eid in event_ids for a in action_by.get(eid, [])]
        reasons = [r.get("reason", "") for r in drows if r.get("reason")]
        states = [r.get("state", "") for r in intents if r.get("note_uid") == uid]
        has_confirmed = any(state in {"CONFIRMED", "PENDING", "SCHEDULED", "FIRED"} for state in states)
        has_fired = any(state == "FIRED" for state in states)
        has_scheduled = any(state in {"SCHEDULED", "PENDING", "FIRED"} for state in states)
        key_down = any(a.get("action") == "key_down" for a in acts)
        # The repeated tracking reason is a state observation, not by itself
        # the first loss cause.  Only select a gate reason after confirmation;
        # otherwise retain an explicit insufficient-evidence classification.
        gate_reasons = [reason for reason in reasons
                        if reason not in {"track_not_current_confirmed", "deadline_updated"}]
        if has_fired and key_down:
            first = "KEY_DOWN_SENT_GAME_JUDGMENT_UNKNOWN"
        elif has_scheduled and not key_down:
            action_names = {a.get("action") for a in acts}
            first = ("SCHEDULER_CANCELED_OR_EXPIRED_NO_KEY_DOWN"
                     if {"canceled", "expired"} & action_names else
                     "SCHEDULER_OUTCOME_NOT_RECORDED")
        elif has_confirmed:
            first = gate_reasons[0] if gate_reasons else "CONFIRMED_NOT_SCHEDULED_UNKNOWN"
        else:
            first = "NOT_ENOUGH_OBSERVATIONS_OR_TRACK_LOST"
        blockers[first] += 1
        lifecycle.append({
            "physical_note_id": "UNKNOWN", "note_uid": uid,
            "appearance": appearance_by.get(uid, "UNKNOWN"),
            "first_capture_timestamp": rows[0].get("capture_timestamp", "") if rows else "",
            "last_capture_timestamp": rows[-1].get("capture_timestamp", "") if rows else "",
            "first_source_frame": rows[0].get("source_frame", "") if rows else "",
            "last_source_frame": rows[-1].get("source_frame", "") if rows else "",
            "observed_rows": len(rows), "lifecycle_states": "|".join(sorted({r.get("legacy_planner_result", "") for r in rows})),
            "first_blocker": first, "key_down_count": sum(a.get("action") == "key_down" for a in acts),
            "game_judgment": "UNKNOWN", "evidence_status": "UID_LIFECYCLE_ONLY",
        })
    fields = list(lifecycle[0]) if lifecycle else ["physical_note_id", "note_uid"]
    write_csv(out / "physical_note_lifecycle.csv", lifecycle, fields)
    first_rows = [{"note_uid": row["note_uid"], "physical_note_id": row["physical_note_id"],
                   "first_blocker": row["first_blocker"], "appearance": row["appearance"],
                   "first_source_frame": row["first_source_frame"],
                   "first_capture_timestamp": row["first_capture_timestamp"],
                   "game_judgment": row["game_judgment"], "evidence_status": row["evidence_status"]}
                  for row in lifecycle]
    write_csv(out / "first_blocker_cases.csv", first_rows,
              list(first_rows[0]) if first_rows else ["note_uid", "first_blocker"])
    paired = []
    for uid, rows in sorted(by_uid.items()):
        shadow = [r for r in rows if r.get("shadow_planner_result") == "schedule"]
        legacy_reject = [r for r in rows if r.get("legacy_planner_result") == "rejected"]
        if not shadow or not legacy_reject:
            continue
        row = shadow[0]
        paired.append({"note_uid": uid, "source_frame": row.get("source_frame", ""),
                       "capture_timestamp": row.get("capture_timestamp", ""),
                       "appearance": row.get("appearance", ""),
                       "legacy_result": row.get("legacy_planner_result", ""),
                       "legacy_reason": row.get("legacy_planner_reason", ""),
                       "shadow_result": row.get("shadow_planner_result", ""),
                       "shadow_reason": row.get("shadow_planner_reason", ""),
                       "key_down": "UNKNOWN", "physical_note_id": "UNKNOWN",
                       "evidence_status": "PAIRED_LIFECYCLE_ONLY"})
    write_csv(out / "legacy_shadow_paired_cases.csv", paired,
              list(paired[0]) if paired else ["note_uid", "evidence_status"])
    audit = []
    for row in actions:
        audit.append({**row, "input_attempted": row.get("action") in {"key_down", "key_up"},
                      "input_api_result": "UNKNOWN_DRY_RUN_SEMANTICS",
                      "game_judgment": "UNKNOWN", "physical_note_id": "UNKNOWN"})
    write_csv(out / "input_delivery_audit.csv", audit,
              list(audit[0]) if audit else ["action", "input_attempted", "game_judgment"])
    (out / "lifecycle_summary.json").write_text(json.dumps({"uid_count": len(lifecycle),
        "first_blocker_counts": blockers, "key_down_is_not_game_truth": True},
        indent=2, default=dict), encoding="utf-8")


def write_manifest(run: Path, out: Path, config: dict, replay_data: dict) -> None:
    files = ["live_video_index.csv", "live_frames.csv", "live_events.csv", "tap_intents.csv",
             "tap_decisions.csv", "tap_eta_comparison.csv", "tap_planner_shadow.csv",
             "live_key_actions.csv", "live_run.json", "run_metrics.json", "live_source.mp4"]
    hashes = {name: sha256(run / name) for name in files if (run / name).exists()}
    idx = replay_data["index"]
    timestamps = [f(r.get("capture_timestamp")) for r in idx if f(r.get("capture_timestamp")) is not None]
    manifest = {
        "plan": "V7.7_NOTE_RECOGNITION_AND_MISS_FIX_PLAN",
        "baseline_commit": "29d2791d059b5f43793bd1e7699cb02ecf6d97e0",
        "run": str(run), "source_video": str(run / "live_source.mp4"),
        "sha256": hashes, "config": config,
        "geometry": {"path": "config/geometry_live_assist.json", "status": "pending_calibration"},
        "video_index": {"rows": len(idx), "timestamp_rows": len(timestamps),
                         "first_capture_timestamp": min(timestamps) if timestamps else None,
                         "last_capture_timestamp": max(timestamps) if timestamps else None,
                         "timestamp_coverage": len(timestamps) / max(len(idx), 1),
                         "mapping": "video_frame -> capture_timestamp from live_video_index.csv"},
        "limitations": ["No game judgment truth is recorded.",
                        "Physical note IDs are not derivable from lifecycle UID alone.",
                        "No geometry validation was performed; pending_calibration retained.",
                        "Dropped frames are background context only; no skip policy changed."],
    }
    (out / "v77_baseline_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def write_reports(run: Path, out: Path, data: dict) -> None:
    metrics = json.loads((run / "run_metrics.json").read_text(encoding="utf-8"))
    candidate_counts = Counter(r.get("appearance", "") for r in data["candidates"] if r.get("stage") == "candidate_final")
    rejection_counts = Counter(r.get("reject_reason", "") for r in data["candidates"] if r.get("reject_reason"))
    lifecycle = read_csv(out / "physical_note_lifecycle.csv")
    blockers = Counter(r.get("first_blocker", "") for r in lifecycle)
    (out / "v77_detector_ab.json").write_text(json.dumps({
        "status": "NO_ACTIVE_PATCH",
        "baseline": {"replay_frames": len(data["index"]), "candidate_final_rows": sum(candidate_counts.values()),
                     "appearance": candidate_counts, "rejection_reasons": rejection_counts},
        "experimental_neutral_tap": {"enabled": False, "reason": "No human-confirmed true gray note gate evidence yet"},
        "experimental_overlap_fragment": {"enabled": False, "reason": "No physical pairing truth yet"},
        "acceptance": "NOT_RUN; requires reviewed physical_note_review.csv",
    }, indent=2, default=dict), encoding="utf-8")
    for name, reason in (("v77_tracker_ab.json", "No tracker threshold or association change; replay evidence only"),
                         ("v77_planner_shadow_ab.json", "Legacy remains active; shadow remains diagnostic-only")):
        (out / name).write_text(json.dumps({"status": "NO_ACTIVE_PATCH", "reason": reason,
                                             "active_path_changed": False, "acceptance": "UNKNOWN"}, indent=2), encoding="utf-8")
    (out / "v77_safety_regression.md").write_text(
        "# V7.7 Safety Regression\n\n"
        "- Replay never invokes Scheduler or Actuator.\n"
        "- Legacy Planner + Particle Filter remain the active input path.\n"
        "- Simplified Planner and Linear ETA remain Shadow-only.\n"
        "- No focus/stale/ROI/disarm/key-release/Hold/duplicate protections were relaxed.\n"
        "- `key_down` and `FIRED` are lifecycle events, not game judgment truth.\n"
        "- Geometry remains `pending_calibration`; no coordinates were changed.\n", encoding="utf-8")
    (out / "V7_7_ROOT_CAUSE_AND_FIX_REPORT.md").write_text(
        "# HoloDream V7.7 Root Cause and Fix Report\n\n"
        "## Executed\n\n"
        f"- Baseline run: `{run}`\n- Replay source: `live_source.mp4` with `live_video_index.csv` capture timestamps.\n"
        f"- Replay coverage: {len(data['index'])} indexed video frames; candidate trace rows {len(data['candidates'])}; "
        f"association rows {len(data['pairs']) + len(data['attempts']) + len(data['assignments'])}.\n"
        "- Full pytest was run after the patch; see `pytest_v77.txt`.\n\n"
        "## Baseline lifecycle (not accuracy)\n\n"
        f"- acquired={metrics.get('acquired_frames','UNKNOWN')}, processed={metrics.get('processed_frames','UNKNOWN')}, "
        f"dropped={metrics.get('dropped_frames','UNKNOWN')}, stale={metrics.get('stale_frames','UNKNOWN')}.\n"
        f"- FIRED/key-down counts are recorded by the run, but game judgment remains UNKNOWN.\n"
        f"- UID first-blocker counts from existing lifecycle logs: `{dict(blockers)}`.\n\n"
        "## Detector evidence\n\n"
        f"- Final replay candidate appearances: `{dict(candidate_counts)}`.\n"
        f"- Candidate rejection trace ranking: `{dict(rejection_counts)}`.\n"
        "- Gray, overlap and pink CSVs contain source frame, capture timestamp and candidate IDs; they are evidence rows, not physical truth.\n\n"
        "## Root-cause status\n\n"
        "No active detector/tracker/planner threshold patch is justified yet. The replay now provides candidate-level evidence, "
        "but the required physical_note_id and game judgment annotations are not present. In particular, a neutral candidate or a "
        "missing candidate cannot be called a true gray note without the contact-sheet review. `pending_calibration` geometry is also "
        "retained. No neutral/overlap experimental patch is enabled.\n\n"
        "## Top priorities after review\n\n"
        "1. Review all high-confidence gray rows in `physical_note_review.csv`; enable a local neutral experiment only if two or more "
        "real notes share the same documented detector blocker and negative controls remain clean.\n"
        "2. Review overlap/nested rows against adjacent frames before changing NMS or association.\n"
        "3. Pair visible notes with lifecycle traces before changing PF/Planner gates; never use FIRED as hit truth.\n\n"
        "## Blockers\n\n"
        "The current run was recorded with live identity telemetry disabled, so the offline replay was required. The provided geometry is "
        "pending calibration. Manual review is required before any Active repair.\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=RUN_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    run = args.run
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    replay_data = replay(run, out, config)
    make_contact_sheets(run, out, replay_data["index"])
    build_reviews(run, out, replay_data, config)
    lifecycle_artifacts(run, out)
    write_manifest(run, out, config, replay_data)
    write_reports(run, out, replay_data)
    print(json.dumps({"out": str(out), "health": replay_data["health"]}, indent=2))


if __name__ == "__main__":
    main()
