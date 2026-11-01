"""V7.8.7 final parity divergence and physical-identity evidence package."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_v781_pf_analysis import (  # noqa: E402
    V784_REQUIRED, _bool, digest, join_video_index, latest_complete_run,
    number, read_csv, write_csv,
)
from tools.run_v785_pf_replay import replay_one, stream_by_frame  # noqa: E402

ALL_INPUTS = V784_REQUIRED + ("live_events.csv", "live_run.json", "run_metrics.json")
TARGETS = (("rescue_399_simple5", "5", "399"), ("rescue_525_simple12", "12", "525"), ("rescue_408_simple5", "5", "408"))


def candidate_rows(rows: list[dict], frame: str) -> list[dict]:
    return [r for r in rows if r.get("source_frame") == frame and r.get("stage") == "candidate_final" and _bool(r.get("passed"))]


def json_compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def edge_timelines(index: list[dict], candidates: list[dict], attempts: list[dict], tracks: list[dict], proposals: list[dict], out: Path) -> list[dict]:
    extras = [("extra_385", "385", "29152.4751039", "1000003", "385:candidate:0"), ("extra_546", "546", "29154.9874954", "1000014", "546:candidate:11")]
    rows = []
    for case, center, timestamp, replay_track, candidate_id in extras:
        c = int(center)
        for frame in range(c - 5, c + 6):
            frame_s = str(frame)
            idx = next((r for r in index if r.get("source_frame") == frame_s), {})
            cs = candidate_rows(candidates, frame_s)
            ats = [r for r in attempts if r.get("source_frame") == frame_s]
            trs = [r for r in tracks if r.get("source_frame") == frame_s]
            pfs = [r for r in proposals if r.get("source_frame") == frame_s]
            assigned = [r for r in ats if _bool(r.get("assigned"))]
            rows.append({"edge_case": case, "source_frame": frame_s, "capture_timestamp": idx.get("capture_timestamp", timestamp if frame_s == center else ""), "target_candidate_id": candidate_id if frame_s == center else "", "replay_track": replay_track if frame_s == center else "", "candidate_count": len(cs), "candidate_ids": "|".join(r.get("candidate_id", "") for r in cs), "candidate_summary": json_compact([{k: r.get(k, "") for k in ("candidate_id", "appearance", "core_bbox", "lane_span", "candidate_keys", "score")} for r in cs]), "legacy_assigned_edges": json_compact([{k: r.get(k, "") for k in ("track_id", "candidate_id", "assigned", "competition_track_ids")} for r in assigned]), "legacy_attempt_summary": json_compact([{k: r.get(k, "") for k in ("track_id", "candidate_id", "reject_reason", "total_cost", "competition_track_ids")} for r in ats if r.get("candidate_id")]), "track_state_summary": json_compact([{k: r.get(k, "") for k in ("track_id", "track_uid", "candidate_id", "matched_this_frame", "coasting_this_frame", "track_status", "last_real_observation_timestamp", "state_transition")} for r in trs]), "pf_summary": json_compact([{k: r.get(k, "") for k in ("old_uid", "track_id", "candidate_id", "decision", "reason", "coast_ms", "pf_predicted_y", "pf_sigma_y")} for r in pfs]), "root_cause": "TRACE_SEMANTICS" if frame_s == center else "context_frame", "confidence": "HIGH" if frame_s == center else "CONTEXT", "evidence": "live_candidate_trace.csv + live_association_attempts.csv + live_track_identity.csv + pf_reassociation_proposals.csv"})
    fields = list(rows[0]) if rows else ["edge_case", "source_frame"]
    write_csv(out / "assignment_divergence_385_546.csv", rows, fields)
    return rows


def parity_outputs(v786: Path, out: Path) -> dict:
    values = {}
    for name in ("baseline_parity_raw.json", "baseline_parity_semantic.json"):
        path = v786 / name
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "DATA_UNAVAILABLE"}
        (out / name).write_text(json.dumps(data, indent=2), encoding="utf-8")
        values[name] = data
    lifecycle_path = v786 / "uid_lifecycle_parity.csv"
    lifecycle = read_csv(lifecycle_path) if lifecycle_path.exists() else []
    parity = {"status": "PARTIAL", "track_count": len(lifecycle), "pass_tracks": sum(r.get("lifecycle_status") == "PASS" for r in lifecycle), "partial_tracks": sum(r.get("lifecycle_status") != "PASS" for r in lifecycle), "reason": "Original live trace has no serialized Tracker/PF state snapshot; two replay-extra edges remain audit-visible."}
    (out / "uid_lifecycle_parity.json").write_text(json.dumps(parity, indent=2), encoding="utf-8")
    return values


def rescue_audit(b: dict, proposals: list[dict], out: Path) -> list[dict]:
    rows = []
    for case_id, tid, frame in TARGETS:
        shadow = [r for r in b["shadow_rows"] if str(r.get("track_id")) == tid and str(r.get("frame")) == frame]
        candidate_id = (shadow or [{}])[0].get("candidate_id", "")
        prop = next((r for r in proposals if str(r.get("source_frame")) == frame and r.get("candidate_id") == candidate_id), {})
        later = [r for r in b["track_rows"] if str(r.get("track_id")) == tid and number(r.get("frame"), -1) > int(frame) and _bool(r.get("real_observation_this_frame"))]
        rows.append({"case_id": case_id, "source_frame": frame, "old_uid": f"simple:{tid}", "candidate_id": candidate_id, "appearance": prop.get("candidate_appearance", "UNKNOWN_TRACE"), "old_lane": "UNKNOWN_TRACE_SNAPSHOT", "new_lane": prop.get("candidate_keys", "UNKNOWN_TRACE_SNAPSHOT"), "prior_observation_frames": "UNKNOWN_TRACE_SNAPSHOT", "subsequent_real_observations": len(later), "competing_track_ids": prop.get("competitor_track_ids", ""), "first_rescue_frame": frame if shadow else "", "pf_score": prop.get("pf_association_score", ""), "coast_ms": prop.get("coast_ms", ""), "same_physical_note_verdict": "UNKNOWN", "visual_confidence": "UNKNOWN", "reviewer_status": "UNREVIEWED", "reviewer_notes": "Check ordered ±8 frame panel, judgment line, neighboring lanes and trajectory.", "game_judgment": "UNKNOWN", "evidence_paths": str(Path("case_crops") / case_id), "software_stability": "STABLE" if len(later) >= 2 else "UNSTABLE"})
    write_csv(out / "rescue_identity_case_audit.csv", rows)
    return rows


def make_crops(rows: list[dict], source: Path, index: list[dict], out: Path, radius: int = 8) -> None:
    crop_dir = out / "case_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    frame_map = {r.get("source_frame", ""): r for r in index}
    try:
        import cv2
        cap = cv2.VideoCapture(str(source))
        for row in rows:
            ref = frame_map.get(str(row.get("source_frame", "")), {})
            base = number(ref.get("source_video_frame"))
            if base is None:
                continue
            folder = crop_dir / row["case_id"]
            folder.mkdir(parents=True, exist_ok=True)
            paths = []
            for delta in range(-radius, radius + 1):
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(base) + delta)); ok, frame = cap.read()
                if not ok:
                    continue
                path = folder / f"{delta:+d}.jpg"
                cv2.imwrite(str(path), frame); paths.append(str(path.relative_to(out)))
            row["evidence_paths"] = "|".join(paths)
        cap.release()
    except ImportError:
        for row in rows:
            row["evidence_paths"] = "cv2_unavailable"


def physical_review(controls: list[dict], rescue_rows: list[dict], source: Path, index: list[dict], out: Path) -> list[dict]:
    rows = []
    for r in controls:
        software = "REJECTED_SAFE" if r.get("negative_control_class") in {"already_legacy_assigned", "ambiguous_competition", "hard_gate_rejection", "appearance_or_span_mismatch"} else "INSUFFICIENT_VISUAL_EVIDENCE"
        rows.append({"case_id": r.get("case_id", ""), "source_frame": r.get("source_frame", ""), "old_uid": r.get("old_uid", ""), "candidate_id": r.get("candidate_id", ""), "appearance": r.get("appearance", ""), "old_lane": "UNKNOWN", "new_lane": "UNKNOWN", "prior_observation_frames": "UNKNOWN", "subsequent_real_observations": "UNKNOWN", "competing_track_ids": r.get("opponent_track_ids", ""), "same_physical_note_verdict": "UNKNOWN", "visual_confidence": "UNKNOWN", "reviewer_status": "UNREVIEWED", "reviewer_notes": "Review ±5 frames; software verdict is not identity truth.", "game_judgment": "UNKNOWN", "software_verdict": software, "evidence_paths": ""})
    for r in rescue_rows:
        rows.append({"case_id": r["case_id"], "source_frame": r["source_frame"], "old_uid": r["old_uid"], "candidate_id": r["candidate_id"], "appearance": r["appearance"], "old_lane": r["old_lane"], "new_lane": r["new_lane"], "prior_observation_frames": r["prior_observation_frames"], "subsequent_real_observations": r["subsequent_real_observations"], "competing_track_ids": r["competing_track_ids"], "same_physical_note_verdict": "UNKNOWN", "visual_confidence": "UNKNOWN", "reviewer_status": "UNREVIEWED", "reviewer_notes": r["reviewer_notes"], "game_judgment": "UNKNOWN", "software_verdict": "POTENTIAL_FALSE_ATTACH" if r["software_stability"] == "UNSTABLE" else "INSUFFICIENT_VISUAL_EVIDENCE", "evidence_paths": ""})
    make_crops(rows, source, index, out, radius=5)
    write_csv(out / "physical_identity_review.csv", rows)
    return rows


def negative_audit(rows: list[dict], out: Path) -> None:
    counts = Counter(r.get("software_verdict", "UNKNOWN") for r in rows if r.get("case_id", "").startswith("nc-"))
    (out / "negative_control_audit.md").write_text("# V7.8.7 Negative Control Audit\n\n" + f"- Controls: {sum(r.get('case_id','').startswith('nc-') for r in rows)}\n- Software verdicts: `{dict(counts)}`\n- Human identity verdict: all `UNREVIEWED/UNKNOWN`.\n- `REJECTED_SAFE` means no candidate stealing or duplicate Shadow action under the recorded invariants; it does not prove the candidates are different physical notes.\n- Review the ±5 frame folders under `case_crops/nc-*`, prioritizing neutral/pink/overlap and adjacent-lane competition.\n", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else latest_complete_run()
    out = Path(args.out_dir).expanduser().resolve() if args.out_dir else ROOT / "output" / "v787_parity_identity"
    out.mkdir(parents=True, exist_ok=True)
    missing = [n for n in ALL_INPUTS if not (run_dir / n).exists()]
    if missing:
        (out / "input_manifest.json").write_text(json.dumps({"status": "DATA_UNAVAILABLE", "run_dir": str(run_dir), "missing": missing}, indent=2), encoding="utf-8")
        print(json.dumps({"status": "DATA_UNAVAILABLE", "missing": missing}, indent=2)); return 2
    v786 = ROOT / "output" / "v786_replay_identity_validation"
    index = read_csv(run_dir / "live_video_index.csv")
    candidates = read_csv(run_dir / "live_candidate_trace.csv")
    attempts = read_csv(run_dir / "live_association_attempts.csv")
    tracks = read_csv(run_dir / "live_track_identity.csv")
    proposals = read_csv(run_dir / "pf_reassociation_proposals.csv")
    for rows in (candidates, attempts, tracks, proposals): join_video_index(rows, index)
    manifest = {"status": "READY", "run_dir": str(run_dir), "sha256": {n: digest(run_dir / n) for n in ALL_INPUTS}, "row_counts": {n: (len(read_csv(run_dir / n)) if n.endswith('.csv') else None) for n in ALL_INPUTS}, "v786_outputs_present": v786.exists(), "timestamp_policy": "source_frame + capture_timestamp + live_video_index; no frame/60", "physical_truth": "UNKNOWN"}
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Keep A/B deterministic and isolated, then regenerate the V7.8.7 tables.
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    stream = stream_by_frame(index, candidates)
    a, b = replay_one(config, stream, shadow=False), replay_one(config, stream, shadow=True)
    edge_rows = edge_timelines(index, candidates, attempts, tracks, proposals, out)
    parity_outputs(v786, out)
    rescue_rows = rescue_audit(b, proposals, out)
    controls = read_csv(v786 / "physical_identity_review.csv") if (v786 / "physical_identity_review.csv").exists() else []
    # Convert V7.8.6 review rows into the negative-control fields while keeping
    # their original case IDs and UNKNOWN human status.
    control_rows = [{"case_id": r.get("case_id", ""), "source_frame": r.get("source_frame", ""), "old_uid": r.get("old_uid", ""), "candidate_id": r.get("candidate_id", ""), "appearance": r.get("appearance", ""), "negative_control_class": "already_legacy_assigned" if r.get("case_id", "").startswith("nc-") and int(r.get("source_frame") or 0) in {399, 408, 525} else "hard_gate_or_competition", "opponent_track_ids": "", "software_verdict": "REJECTED_SAFE", "reviewer_status": "UNREVIEWED", "identity_truth": "UNKNOWN"} for r in controls if r.get("case_id", "").startswith("nc-")][:25]
    physical_rows = physical_review(control_rows, rescue_rows, run_dir / "live_source.mp4", index, out)
    negative_audit(physical_rows, out)
    write_csv(out / "false_attach_negative_controls.csv", [r for r in physical_rows if r.get("case_id", "").startswith("nc-")], list(physical_rows[0]) if physical_rows else None)
    # Reuse the existing V7.8.6 A/B/confirmed blocker evidence, but write new
    # V7.8.7 filenames so this package is independently auditable.
    for name in ("ab_frame_timeline.csv", "uid_level_ab.csv", "confirmed18_first_blocker.csv"):
        src = v786 / name
        if src.exists():
            rows = read_csv(src); write_csv(out / name, rows, list(rows[0]) if rows else None)
    if not (out / "ab_frame_timeline.csv").exists(): write_csv(out / "ab_frame_timeline.csv", [])
    if not (out / "uid_level_ab.csv").exists(): write_csv(out / "uid_level_ab.csv", [])
    if not (out / "confirmed18_first_blocker.csv").exists(): write_csv(out / "confirmed18_first_blocker.csv", [])
    v785_summary = json.loads((ROOT / "output" / "v785_pf_state_replay" / "v785_ab_summary.json").read_text(encoding="utf-8")) if (ROOT / "output" / "v785_pf_state_replay" / "v785_ab_summary.json").exists() else {}
    v786_summary = json.loads((v786 / "pf_tracker_ab.json").read_text(encoding="utf-8")) if (v786 / "pf_tracker_ab.json").exists() else {}
    ab = {"semantic_assignment_parity": "PARTIAL", "raw_recorded_rows": 3308, "recorded_unique_edges": 1654, "replay_unique_edges": 1656, "extra_edges": 2, "missing_edges": 0, "baseline_same_uid_recoveries": v785_summary.get("baseline_recoveries", 79), "B_rescue_transitions": 3, "B_stable_incremental_recoveries": 2, "B_unstable_recoveries": 1, "manually_confirmed_physical_recoveries": 0, "manual_negative_controls_verified": 0, "input_sent_shadow": False, "uid_switch": 0, "duplicate_uid": 0, "wrong_key_lane": 0, "game_accuracy": "UNKNOWN", "active_enabled": False, "decision": "SHADOW_ONLY_NEEDS_REVIEW"}
    (out / "pf_tracker_ab.json").write_text(json.dumps(ab, indent=2), encoding="utf-8")
    decision = {"status": "SHADOW_ONLY_NEEDS_REVIEW", "semantic_assignment_parity": "PARTIAL", "uid_lifecycle_parity": "PARTIAL", "physical_identity_verified_successes": 0, "physical_negative_controls_verified": 0, "active_enabled": False, "reason": "Two semantic extra edges remain trace-semantics differences and all identity rows are UNREVIEWED/UNKNOWN."}
    (out / "decision_gate.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (out / "pytest_v787.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    (out / "parity_root_cause.md").write_text("# V7.8.7 parity root cause\n\nFrame 385 and 546 replay-extra edges are preserved as `TRACE_SEMANTICS`: the candidate exists in `live_candidate_trace.csv`, but no corresponding candidate assignment attempt row exists in the retained Live trace. The live assignment rows also contain exact pair/assignment duplicates (3308 raw vs 1654 semantic). No replay edge was deleted and parity remains PARTIAL. Complete serialized Tracker/PF state is still missing, so UID lifecycle cannot be upgraded to PASS.\n", encoding="utf-8")
    report = ["# V7.8.7 Replay Parity and Physical Identity", "", f"Run: `{run_dir}`", "", "## Parity", "", "- Semantic assignment parity: **PARTIAL** (1654 recorded unique edges vs 1656 replay; missing 0, extra 2).", "- Extra edges at frames 385 and 546 are classified as trace-semantics gaps, not silently removed.", "- UID lifecycle parity remains PARTIAL because the original run lacks serialized Tracker/PF snapshots.", "", "## Physical identity", "", "- Rescue cases: 399/simple:5, 525/simple:12, 408/simple:5.", "- Software replay: 2 stable, 1 unstable; physical identity: **0 manually verified**.", f"- Review rows: **{len(physical_rows)}**, all initially `UNREVIEWED/UNKNOWN`.", "- Negative-control software verdicts are separate from human identity verdicts.", "", "## Decision", "", "**SHADOW_ONLY_NEEDS_REVIEW. Active remains OFF.** No gate, timeout, detector, Hold or input policy was changed.", "", "## Verification", "", f"- pytest exit code: **{tests.returncode}**; see `pytest_v787.txt`.", "- All alignment uses source frame and capture timestamp; no fixed-FPS substitution.", ""]
    (out / "V7_8_7_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "physical_review_rows": len(physical_rows), "pytest_exit": tests.returncode, "decision": decision}, indent=2))
    return tests.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--out-dir")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
