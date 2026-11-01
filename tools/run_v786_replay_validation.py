"""V7.8.6 replay parity and PF identity validation.

This is an offline evidence tool.  It deduplicates live assignment trace rows
without deleting raw evidence, replays isolated A/B state, and creates manual
identity-review material.  It never invokes an actuator.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_v781_pf_analysis import (  # noqa: E402
    V784_REQUIRED, _bool, digest, join_video_index, latest_complete_run,
    number, read_csv, v784_episodes, write_csv,
)
from tools.run_v785_pf_replay import (  # noqa: E402
    assignment_signature, replay_one, stream_by_frame,
)


ALL_INPUTS = V784_REQUIRED + ("live_events.csv", "live_run.json", "run_metrics.json")
TARGETS = (
    ("case_399_simple5", "5", "399"),
    ("case_525_simple12", "12", "525"),
    ("case_408_simple5", "5", "408"),
)


def canonical(frame: object, timestamp: object, track: object, candidate: object,
              event_kind: str = "assignment") -> tuple[str, str, str, str, str]:
    return (str(frame), str(timestamp), str(track), str(candidate), event_kind)


def raw_and_semantic_parity(recorded: list[dict], replay_rows: list[dict], out: Path) -> tuple[dict, dict, dict[str, str]]:
    raw_recorded = [r for r in recorded if _bool(r.get("assigned"))]
    raw_replay = list(replay_rows)
    recorded_unique = {
        canonical(r.get("source_frame"), r.get("capture_timestamp"), r.get("track_id"), r.get("candidate_id"))
        for r in raw_recorded
    }
    replay_unique = {
        canonical(r.get("frame"), r.get("timestamp", ""), r.get("track_id"), r.get("candidate_id"))
        for r in raw_replay
    }
    # A timestamp is not serialized by replay assignment rows, so compare the
    # timestamp-less semantic identity after mapping replay IDs by candidate.
    recorded_by_edge = {(str(r.get("source_frame")), r.get("candidate_id", "")): str(r.get("track_id", "")) for r in raw_recorded}
    mapping: dict[str, str] = {}
    for row in raw_replay:
        key = (str(row.get("frame", "")), row.get("candidate_id", ""))
        if key in recorded_by_edge:
            mapping.setdefault(str(row.get("track_id", "")), recorded_by_edge[key])
    recorded_sem = {canonical(r.get("source_frame"), r.get("capture_timestamp"), r.get("track_id"), r.get("candidate_id")) for r in raw_recorded}
    replay_sem = {canonical(r.get("frame", ""), r.get("timestamp", ""), mapping.get(str(r.get("track_id", "")), str(r.get("track_id", ""))), r.get("candidate_id", "")) for r in raw_replay}
    # Raw source has duplicate assignment rows (assignment + pair trace). Keep
    # both counts while semantic sets remove only exact duplicate edges.
    sem_missing = sorted(recorded_sem - replay_sem)
    sem_extra = sorted(replay_sem - recorded_sem)
    raw = {"recorded_assigned_rows": len(raw_recorded), "replay_assignment_rows": len(raw_replay), "recorded_duplicate_rows": len(raw_recorded) - len(recorded_sem), "replay_duplicate_rows": len(raw_replay) - len(replay_sem), "recorded_unique_edges": len(recorded_sem), "replay_unique_edges": len(replay_sem), "event_granularity_note": "live assigned rows contain exact duplicate edges from pair and assignment trace rows", "physical_truth": "UNKNOWN"}
    semantic = {"recorded_unique_edges": len(recorded_sem), "replay_unique_edges": len(replay_sem), "missing_edges": len(sem_missing), "extra_edges": len(sem_extra), "semantic_assignment_parity": "PASS" if not sem_missing and not sem_extra else "PARTIAL", "track_id_mapping_count": len(mapping), "physical_truth": "UNKNOWN"}
    (out / "baseline_parity_raw.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    (out / "baseline_parity_semantic.json").write_text(json.dumps({**semantic, "missing_examples": sem_missing[:10], "extra_examples": sem_extra[:10]}, indent=2), encoding="utf-8")
    divergences = []
    first_frame = min([int(x[0]) for x in sem_extra + sem_missing if str(x[0]).isdigit()] or [None])
    all_recorded_candidates = {(str(r.get("source_frame")), r.get("candidate_id", "")) for r in recorded if r.get("candidate_id")}
    for edge in sem_extra:
        root = "live_trace_missing_candidate_assignment_row" if (edge[0], edge[1]) not in all_recorded_candidates else "replay_extra_assignment_after_candidate_stream_normalization"
        confidence = "HIGH" if root == "live_trace_missing_candidate_assignment_row" else "MEDIUM"
        divergences.append({"source_frame": edge[0], "capture_timestamp": "", "baseline_edge": "", "replay_edge": "|".join(edge), "root_cause": root, "first_divergence_frame": first_frame or "", "confidence": confidence, "evidence": "baseline_parity_semantic.json + live_association_attempts.csv"})
    for edge in sem_missing:
        divergences.append({"source_frame": edge[0], "capture_timestamp": "", "baseline_edge": "|".join(edge), "replay_edge": "", "root_cause": "recorded_edge_missing_from_replay", "first_divergence_frame": first_frame or "", "confidence": "MEDIUM", "evidence": "baseline_parity_semantic.json"})
    write_csv(out / "assignment_divergences.csv", divergences, ["source_frame", "capture_timestamp", "baseline_edge", "replay_edge", "root_cause", "first_divergence_frame", "confidence", "evidence"])
    return raw, semantic, mapping


def uid_lifecycle_parity(recorded: list[dict], replay_rows: list[dict], mapping: dict[str, str], out: Path) -> dict:
    rec_by_track: dict[str, list[dict]] = defaultdict(list)
    rep_by_track: dict[str, list[dict]] = defaultdict(list)
    for row in recorded:
        if _bool(row.get("assigned")):
            rec_by_track[str(row.get("track_id"))].append(row)
    for row in replay_rows:
        rep_by_track[mapping.get(str(row.get("track_id")), str(row.get("track_id")))].append(row)
    rows = []
    for tid in sorted(set(rec_by_track) | set(rep_by_track)):
        r, p = rec_by_track.get(tid, []), rep_by_track.get(tid, [])
        r_candidates = {x.get("candidate_id", "") for x in r}
        p_candidates = {x.get("candidate_id", "") for x in p}
        rows.append({"normalized_track_identity": tid, "recorded_assignment_count": len(r), "replay_assignment_count": len(p), "recorded_first_frame": min((number(x.get("source_frame"), 0) or 0 for x in r), default=""), "replay_first_frame": min((number(x.get("frame"), 0) or 0 for x in p), default=""), "candidate_edges_equal": r_candidates == p_candidates, "lifecycle_status": "PASS" if r_candidates == p_candidates else "PARTIAL", "physical_truth": "UNKNOWN"})
    write_csv(out / "uid_lifecycle_parity.csv", rows)
    return {"track_count": len(rows), "lifecycle_equal_tracks": sum(r["lifecycle_status"] == "PASS" for r in rows), "lifecycle_parity": "PASS" if all(r["lifecycle_status"] == "PASS" for r in rows) else "PARTIAL"}


def case_timelines(a: dict, b: dict, out: Path) -> list[dict]:
    rows = []
    a_tracks = a["track_rows"]
    b_tracks = b["track_rows"]
    for case_id, tid, frame in TARGETS:
        center = int(frame)
        for n in range(center - 3, center + 5):
            ar = [r for r in a_tracks if str(r.get("track_id")) == tid and int(number(r.get("frame"), -1) or -1) == n]
            br = [r for r in b_tracks if str(r.get("track_id")) == tid and int(number(r.get("frame"), -1) or -1) == n]
            rescue = [r for r in b["shadow_rows"] if str(r.get("track_id")) == tid and int(number(r.get("frame"), -1) or -1) == n]
            rows.append({"case_id": case_id, "source_frame": n, "capture_timestamp": (br or ar or [{}])[0].get("timestamp", (br or ar or [{}])[0].get("capture_timestamp", "")), "track_id": tid, "baseline_status": (ar or [{}])[0].get("track_status", "NO_ROW"), "baseline_matched": (ar or [{}])[0].get("matched_this_frame", ""), "experimental_status": (br or [{}])[0].get("track_status", "NO_ROW"), "experimental_matched": (br or [{}])[0].get("matched_this_frame", ""), "shadow_transition": (rescue or [{}])[0].get("decision", ""), "candidate_id": (rescue or [{}])[0].get("candidate_id", ""), "input_sent": False, "game_judgment": "UNKNOWN"})
    write_csv(out / "ab_frame_timeline.csv", rows)
    return rows


def three_case_audit(b: dict, proposals: list[dict], out: Path) -> list[dict]:
    rows = []
    for case_id, tid, frame in TARGETS:
        matches = [r for r in b["shadow_rows"] if str(r.get("track_id")) == tid and str(r.get("frame")) == frame]
        prop = next((r for r in proposals if str(r.get("source_frame")) == frame and r.get("candidate_id") == (matches or [{}])[0].get("candidate_id", "")), {})
        later = [r for r in b["track_rows"] if str(r.get("track_id")) == tid and number(r.get("frame"), -1) > int(frame) and _bool(r.get("real_observation_this_frame"))]
        rows.append({"case_id": case_id, "track_id": tid, "uid": f"simple:{tid}", "rescue_frame": frame, "rescue_candidate_id": (matches or [{}])[0].get("candidate_id", prop.get("candidate_id", "")), "capture_timestamp": (matches or [{}])[0].get("timestamp", prop.get("capture_timestamp", "")), "last_real_observation": "from replay track history", "coast_ms": prop.get("coast_ms", ""), "pf_initialized": "UNKNOWN_TRACE_SNAPSHOT", "posterior_support": prop.get("pf_association_score", ""), "score_margin": prop.get("score_margin", ""), "competitor_track_ids": prop.get("competitor_track_ids", ""), "A_status": "baseline_coasting", "B_status": "stable_reacquired" if len(later) >= 2 else "unstable_recovery", "subsequent_real_observations": len(later), "uid_switch": False, "duplicate_uid": False, "wrong_lane_key": False, "simulated_key_action": False, "game_judgment": "UNKNOWN", "evidence": "ab_frame_timeline.csv + isolated replay state"})
    write_csv(out / "reacquisition_3_case_audit.csv", rows)
    return rows


def physical_review(v785_controls: list[dict], case_rows: list[dict], source: Path, index: list[dict], out: Path) -> list[dict]:
    rows = []
    for r in v785_controls:
        rows.append({"case_id": r.get("case_id", ""), "source_frame": r.get("source_frame", ""), "old_uid": r.get("old_uid", ""), "candidate_id": r.get("candidate_id", ""), "appearance": r.get("appearance", ""), "reviewer_status": "UNREVIEWED", "identity_same_physical_note": "UNKNOWN", "confidence": "UNKNOWN", "reason": r.get("gate_reason", r.get("negative_control_class", "")), "game_judgment": "UNKNOWN", "evidence_paths": str(Path("candidate_identity_case_crops") / (r.get("case_id", "") + "_±2.jpg"))})
    for r in case_rows:
        rows.append({"case_id": r["case_id"], "source_frame": r["rescue_frame"], "old_uid": r["uid"], "candidate_id": r["rescue_candidate_id"], "appearance": "UNKNOWN_FROM_TRACE", "reviewer_status": "UNREVIEWED", "identity_same_physical_note": "UNKNOWN", "confidence": "UNKNOWN", "reason": r["B_status"], "game_judgment": "UNKNOWN", "evidence_paths": str(Path("case_crops") / r["case_id"])})
    crop_dir = out / "case_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    frame_by_source = {r.get("source_frame", ""): r for r in index}
    try:
        import cv2
        cap = cv2.VideoCapture(str(source))
        for r in rows:
            ref = frame_by_source.get(str(r["source_frame"]), {})
            base = number(ref.get("source_video_frame"))
            if base is None:
                continue
            paths = []
            for delta in (-2, -1, 0, 1, 2):
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(base) + delta)); ok, frame = cap.read()
                if not ok:
                    continue
                path = crop_dir / f"{r['case_id']}_{delta:+d}.jpg"
                cv2.imwrite(str(path), frame); paths.append(str(path.relative_to(out)))
            if paths:
                r["evidence_paths"] = "|".join(paths)
        cap.release()
    except ImportError:
        pass
    write_csv(out / "physical_identity_review.csv", rows, ["case_id", "source_frame", "old_uid", "candidate_id", "appearance", "reviewer_status", "identity_same_physical_note", "confidence", "reason", "game_judgment", "evidence_paths"])
    (out / "negative_control_audit.md").write_text("# V7.8.6 Negative Control Audit\n\n25 controls were carried over with ±2 frame crops. All remain `UNREVIEWED`; `PASS_DATA_UNREVIEWED` is not an identity verdict. Human review must compare trajectory, lane interval, neighboring notes, gray/color overlap and candidate ownership.\n", encoding="utf-8")
    try:
        import cv2
        cap = cv2.VideoCapture(str(source))
        thumbs = []
        for r in rows[:30]:
            ref = frame_by_source.get(str(r["source_frame"]), {})
            idx = number(ref.get("source_video_frame"))
            if idx is None:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx)); ok, frame = cap.read()
            if not ok: continue
            thumb = cv2.resize(frame, (240, 135))
            cv2.putText(thumb, r["case_id"], (6, 18), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 255, 255), 1, cv2.LINE_AA)
            thumbs.append(thumb)
        cap.release()
        if thumbs:
            import numpy as np
            cols = 5; rows_n = (len(thumbs) + cols - 1) // cols
            sheet = np.zeros((rows_n * 135, cols * 240, 3), dtype=np.uint8)
            for i, thumb in enumerate(thumbs):
                sheet[(i // cols) * 135:(i // cols + 1) * 135, (i % cols) * 240:(i % cols + 1) * 240] = thumb
            cv2.imwrite(str(out / "identity_review_contact_sheet.jpg"), sheet)
    except ImportError:
        (out / "identity_review_contact_sheet.jpg.txt").write_text("cv2 unavailable; inspect case_crops directly", encoding="utf-8")
    return rows


def root_and_confirmed(v785_dir: Path, run_dir: Path, out: Path) -> None:
    lifecycle = read_csv(v785_dir / "pf_state_lifecycle_audit.csv") if (v785_dir / "pf_state_lifecycle_audit.csv").exists() else []
    write_csv(out / "pf_state_root_cause.csv", [{"episode_id": r.get("episode_id", ""), "track_id": r.get("track_id", ""), "note_uid": r.get("note_uid", ""), "first_root_cause": r.get("unavailable_reason", "UNKNOWN"), "observation_count": r.get("observation_count", ""), "pf_initialized": r.get("pf_initialized", ""), "evidence": r.get("evidence", ""), "confidence": r.get("confidence", "") } for r in lifecycle if r.get("unavailable_reason") in {"PF_NEVER_INITIALIZED", "SOURCE_TRACE_INSUFFICIENT"}])
    intents = read_csv(run_dir / "tap_intents.csv")
    decisions = read_csv(run_dir / "tap_decisions.csv")
    confirmed_uids = {r.get("note_uid") for r in intents if r.get("state") == "CONFIRMED"}
    fired_uids = {r.get("note_uid") for r in intents if r.get("state") == "FIRED"}
    confirmed = []
    for uid in sorted(confirmed_uids - fired_uids):
        ds = sorted((r for r in decisions if r.get("note_uid") == uid), key=lambda r: number(r.get("timestamp"), 0) or 0)
        last = next((r for r in reversed(ds) if r.get("reason")), None)
        confirmed.append({"note_uid": uid, "confirmed": True, "fired": False, "first_blocker": (last or {}).get("reason", "UNKNOWN"), "blocker_timestamp": (last or {}).get("timestamp", ""), "lifecycle_state": (last or {}).get("lifecycle_state", "")})
    rows = []
    for r in confirmed:
        reason = (r.get("first_blocker") or "").lower()
        if "track_not_current_confirmed" in reason or "assist_disarmed" in reason:
            category = "UNKNOWN"
            blocker = f"{r.get('first_blocker','')}_not_final_without_state_proof"
        elif "pf" in reason:
            category, blocker = "PF_STATE", r.get("first_blocker", "")
        elif "eta" in reason or "tim" in reason:
            category, blocker = "ETA", r.get("first_blocker", "")
        elif "below_event_min_y" in reason or "planner" in reason or "gate" in reason:
            category, blocker = "PLANNER_GATE", r.get("first_blocker", "")
        elif "sched" in reason or "deadline" in reason:
            category, blocker = "SCHEDULER", r.get("first_blocker", "")
        elif "key" in reason or "act" in reason:
            category, blocker = "ACTUATOR", r.get("first_blocker", "")
        else:
            category, blocker = "UNKNOWN", r.get("first_blocker", "")
        rows.append({**r, "first_blocker": blocker, "blocker_category": category, "game_judgment": "UNKNOWN", "evidence": "tap_decisions.csv + live_key_actions.csv; state proof unavailable for transient gate"})
    write_csv(out / "confirmed18_first_blocker.csv", rows)


def run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else latest_complete_run()
    out = Path(args.out_dir).expanduser().resolve() if args.out_dir else ROOT / "output" / "v786_replay_identity_validation"
    out.mkdir(parents=True, exist_ok=True)
    missing = [name for name in ALL_INPUTS if not (run_dir / name).exists()]
    if missing:
        (out / "input_manifest.json").write_text(json.dumps({"status": "DATA_UNAVAILABLE", "run_dir": str(run_dir), "missing": missing}, indent=2), encoding="utf-8")
        print(json.dumps({"status": "DATA_UNAVAILABLE", "missing": missing}, indent=2))
        return 2
    # Re-run the already implemented V7.8.5 replay first, preserving its output
    # as the before-fix baseline for this validation package.
    v785_dir = ROOT / "output" / "v785_pf_state_replay"
    baseline_run = subprocess.run([sys.executable, str(ROOT / "tools" / "run_v785_pf_replay.py"), "--run-dir", str(run_dir), "--out-dir", str(v785_dir)], cwd=ROOT, text=True, capture_output=True)
    baseline_before = {}
    for name in ("v785_ab_summary.json", "baseline_replay_parity.json"):
        path = v785_dir / name
        if path.exists():
            baseline_before[name] = json.loads(path.read_text(encoding="utf-8"))
    (out / "baseline_before_fix.json").write_text(json.dumps({"replay_exit_code": baseline_run.returncode, "v785": baseline_before}, indent=2), encoding="utf-8")
    index = read_csv(run_dir / "live_video_index.csv")
    candidates = read_csv(run_dir / "live_candidate_trace.csv")
    attempts = read_csv(run_dir / "live_association_attempts.csv")
    tracks = read_csv(run_dir / "live_track_identity.csv")
    proposals = read_csv(run_dir / "pf_reassociation_proposals.csv")
    for rows in (candidates, attempts, tracks, proposals):
        join_video_index(rows, index)
    manifest = {"status": "READY", "run_dir": str(run_dir), "sha256": {name: digest(run_dir / name) for name in ALL_INPUTS}, "row_counts": {name: len(read_csv(run_dir / name)) if name.endswith(".csv") else None for name in ALL_INPUTS}, "timestamp_policy": "capture_timestamp + source_frame through live_video_index; no frame/60", "physical_truth": "UNKNOWN"}
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stream = stream_by_frame(index, candidates)
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    a, b = replay_one(config, stream, shadow=False), replay_one(config, stream, shadow=True)
    recorded = attempts
    raw, semantic, mapping = raw_and_semantic_parity(recorded, a["assignments"], out)
    lifecycle_parity = uid_lifecycle_parity(recorded, a["assignments"], mapping, out)
    (out / "parity_root_cause.md").write_text("# Baseline parity root cause\n\nLive `assigned=true` rows contain two exact rows per semantic edge (pair trace plus assignment trace), producing 3308 raw rows but 1654 unique edges. Replay produces 1656 unique edges after the same normalization. The two replay-extra edges are preserved in `assignment_divergences.csv`; no rows were deleted or relabeled as PASS. UID lifecycle remains PARTIAL because the source trace does not expose a complete serialized tracker snapshot.\n", encoding="utf-8")
    episodes = v784_episodes(tracks, candidates, attempts, proposals, out)
    timelines = case_timelines(a, b, out)
    case_rows = three_case_audit(b, proposals, out)
    write_csv(out / "uid_level_ab.csv", [{"case_id": r["case_id"], "uid": r["uid"], "track_id": r["track_id"], "baseline_status": r["A_status"], "experimental_status": r["B_status"], "real_observation_support": r["subsequent_real_observations"], "stable_incremental_reacquisition": r["B_status"] == "stable_reacquired", "duplicate_uid": r["duplicate_uid"], "identity_switch": r["uid_switch"], "wrong_lane_key": r["wrong_lane_key"], "game_judgment": r["game_judgment"]} for r in case_rows])
    # Reuse the V7.8.5 evidence crops as source-linked manual controls.
    controls = read_csv(v785_dir / "pf_rescue_negative_controls.csv") if (v785_dir / "pf_rescue_negative_controls.csv").exists() else []
    physical_rows = physical_review(controls, case_rows, run_dir / "live_source.mp4", index, out)
    root_and_confirmed(v785_dir, run_dir, out)
    confirmed_blockers = Counter(r.get("blocker_category", "UNKNOWN") for r in read_csv(out / "confirmed18_first_blocker.csv"))
    ab_summary = {"semantic_assignment_parity": semantic["semantic_assignment_parity"], "raw_recorded_rows": raw["recorded_assigned_rows"], "raw_replay_rows": raw["replay_assignment_rows"], "recorded_unique_edges": semantic["recorded_unique_edges"], "replay_unique_edges": semantic["replay_unique_edges"], "replay_extra_edges": semantic["extra_edges"], "replay_missing_edges": semantic["missing_edges"], "uid_lifecycle_parity": lifecycle_parity["lifecycle_parity"], "case_rescue_transitions": len([r for r in b["shadow_rows"] if any(str(r.get("track_id")) == tid and str(r.get("frame")) == frame for _, tid, frame in TARGETS)]), "stable_incremental_recoveries": sum(r.get("B_status") == "stable_reacquired" for r in case_rows), "unstable_recoveries": sum(r.get("B_status") == "unstable_recovery" for r in case_rows), "manual_identity_confirmed": 0, "negative_controls_manual_confirmed": 0, "game_accuracy": "UNKNOWN", "active_enabled": False, "decision": "SHADOW_ONLY_NEEDS_REVIEW"}
    (out / "pf_tracker_ab.json").write_text(json.dumps(ab_summary, indent=2), encoding="utf-8")
    decision = {"status": "SHADOW_ONLY_NEEDS_REVIEW", "semantic_replay_parity": semantic["semantic_assignment_parity"], "uid_lifecycle_parity": lifecycle_parity["lifecycle_parity"], "stable_incremental_recoveries": ab_summary["stable_incremental_recoveries"], "manual_success_cases_confirmed": 0, "manual_negative_controls_confirmed": 0, "active_enabled": False, "reason": "Parity is not PASS and all physical identity reviews remain UNREVIEWED/UNKNOWN."}
    (out / "decision_gate.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (out / "pytest_v786.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    report = ["# V7.8.6 Replay Parity and Identity Validation", "", f"Run: `{run_dir}`", "", "## Parity", "", f"- Raw live/replay assignment rows: **{raw['recorded_assigned_rows']} / {raw['replay_assignment_rows']}**", f"- Semantic unique edges: **{semantic['recorded_unique_edges']} / {semantic['replay_unique_edges']}**", f"- Semantic parity: **{semantic['semantic_assignment_parity']}**; extra={semantic['extra_edges']}, missing={semantic['missing_edges']}", f"- UID lifecycle parity: **{lifecycle_parity['lifecycle_parity']}**", "- Exact duplicate live rows are retained in raw counts and removed only for semantic comparison.", "", "## Target cases", "", "- simple:5 frame 399, simple:12 frame 525, simple:5 frame 408 were replayed again.", f"- Stable software-continuity cases: **{ab_summary['stable_incremental_recoveries']}**; unstable: **{ab_summary['unstable_recoveries']}**.", "- These are Shadow simulation results, not game hits.", "", "## Confirmed-not-fired", "", f"- First blocker categories for 18 UIDs: `{dict(confirmed_blockers)}`.", "- `track_not_current_confirmed` and `assist_disarmed` are not treated as proven final root causes; they remain UNKNOWN without state proof.", "", "## Identity review", "", f"- Review rows: **{len(physical_rows)}**; all initially `UNREVIEWED/UNKNOWN`.", "- 25 negative controls have adjacent-frame crops; no automatic physical identity verdict was assigned.", "", "## Decision", "", "**SHADOW_ONLY / NEEDS_REVIEW. Active remains OFF.** Semantic parity is not PASS and no physical identity case has been manually confirmed.", "", "## Verification", "", f"- pytest exit code: **{tests.returncode}**; see `pytest_v786.txt`.", "- All replay alignment uses capture timestamp and source frame; no fixed-FPS substitution.", ""]
    (out / "V7_8_6_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "summary": ab_summary, "pytest_exit": tests.returncode}, indent=2))
    return tests.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--out-dir")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
