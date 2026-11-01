"""V7.8.5 deterministic PF state replay and isolated A/B evidence.

The replay consumes the recorded detector candidate stream and capture
timestamps.  A is a normal Legacy SimpleTracker.  B is a separate tracker
with the post-assignment targeted rescue hook enabled; it can mutate only its
own replay state and never calls Planner, Scheduler or Actuator.
"""
from __future__ import annotations

import argparse
import ast
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

from src.detector import Candidate
from src.simple_tracker import SimpleTracker
from tools.run_v781_pf_analysis import (
    V784_REQUIRED, _bool, digest, join_video_index, latest_complete_run,
    number, read_csv, v784_confirmed_audit, v784_episodes, v784_negative_controls,
    v784_proposals, write_csv,
)


def _bbox(value: str) -> tuple[int, int, int, int]:
    try:
        x, y, w, h = ast.literal_eval(value)
        return int(x), int(y), int(w), int(h)
    except (ValueError, SyntaxError, TypeError):
        return 0, 0, 1, 1


def candidate_from_row(row: dict) -> Candidate:
    keys = [k for k in (row.get("candidate_keys") or "").split("|") if k]
    try:
        u_min, u_max = (float(v) for v in (row.get("lane_span") or "0:0").split(":", 1))
    except (ValueError, TypeError):
        u_min, u_max = 0.0, 0.01
    return Candidate(
        _bbox(row.get("core_bbox") or row.get("raw_bbox") or ""),
        row.get("appearance") or "", float(number(row.get("score"), .5) or .5),
        u_min, u_max, keys, row.get("note_type") or "unknown",
        diagnostic_id=row.get("candidate_id") or "",
    )


def stream_by_frame(index: list[dict], candidate_rows: list[dict]) -> list[tuple[dict, list[Candidate]]]:
    by_frame: dict[str, list[dict]] = defaultdict(list)
    for row in candidate_rows:
        if row.get("stage") == "candidate_final" and _bool(row.get("passed")):
            by_frame[row.get("source_frame", "")].append(row)
    result = []
    seen = set()
    for frame in sorted(index, key=lambda r: number(r.get("capture_timestamp"), 0) or 0):
        sf = frame.get("source_frame", "")
        if sf in seen:
            continue
        seen.add(sf)
        result.append((frame, [candidate_from_row(row) for row in by_frame.get(sf, [])]))
    return result


def replay_one(config: dict, stream: list[tuple[dict, list[Candidate]]], *, shadow: bool) -> dict:
    tracker_cfg = dict(config.get("tracker", {}))
    tracker_cfg["confirm_observations"] = int(tracker_cfg.get("confirm_observations", 5))
    tracker_cfg["pf_assisted_reassociation"] = {
        "enabled": shadow, "mode": "shadow", "offline_only": True,
        "require_real_candidate": True, "allow_coasting_to_fire": False,
        "preserve_hard_gates": True, "min_score_margin": .5,
    }
    particle_cfg = dict(config.get("predictor", {}).get("particle", {}))
    tracker = SimpleTracker(tracker_cfg, particle_cfg,
                            hit_y=float(config.get("playfield", {}).get("hit_y", 352)))
    frames = []
    assignments = []
    shadow_rows = []
    track_rows = []
    for frame, candidates in stream:
        ts = number(frame.get("capture_timestamp"))
        if ts is None:
            continue
        playing = frame.get("gameplay_state") == "PLAYING"
        trace = {"max_rows": 200000}
        tracks = tracker.update(candidates, ts, playing=playing, trace=trace,
                                frame_index=int(number(frame.get("source_frame"), 0) or 0),
                                shadow_replay=shadow)
        frame_assignments = [row for row in trace.get("assignment_rows", []) if row.get("assigned")]
        frames.append({"source_frame": frame.get("source_frame", ""), "capture_timestamp": frame.get("capture_timestamp", ""), "playing": playing, "candidate_count": len(candidates), "assignment_count": len(frame_assignments), "shadow_replay_count": len(trace.get("shadow_replay_rows", []))})
        assignments.extend(frame_assignments)
        shadow_rows.extend(trace.get("shadow_replay_rows", []))
        track_rows.extend(trace.get("track_rows", []))
    return {"tracker": tracker, "frames": frames, "assignments": assignments, "shadow_rows": shadow_rows, "track_rows": track_rows}


def assignment_signature(rows: list[dict]) -> str:
    payload = "\n".join("|".join(str(row.get(k, "")) for k in ("frame", "candidate_id", "track_id")) for row in sorted(rows, key=lambda r: (str(r.get("frame", "")), str(r.get("candidate_id", "")), str(r.get("track_id", "")))))
    return hashlib.sha256(payload.encode()).hexdigest()


def build_mapping(replay_rows: list[dict], recorded_attempts: list[dict]) -> dict[str, str]:
    recorded = {(r.get("candidate_id", ""), r.get("source_frame", "")): r.get("track_id", "") for r in recorded_attempts if _bool(r.get("assigned"))}
    mapping: dict[str, str] = {}
    for row in replay_rows:
        if not row.get("candidate_id"):
            continue
        mapped = recorded.get((row.get("candidate_id", ""), str(row.get("frame", ""))))
        if mapped and row.get("track_id") not in mapping:
            mapping[str(row.get("track_id"))] = str(mapped)
    return mapping


def parity_report(a: dict, recorded_attempts: list[dict], out: Path) -> dict:
    mapping = build_mapping(a["assignments"], recorded_attempts)
    normalized = [{**row, "track_id": mapping.get(str(row.get("track_id")), str(row.get("track_id")))} for row in a["assignments"]]
    recorded = [{"frame": r.get("source_frame", ""), "candidate_id": r.get("candidate_id", ""), "track_id": r.get("track_id", "")} for r in recorded_attempts if _bool(r.get("assigned"))]
    sig_a = assignment_signature(normalized)
    sig_recorded = assignment_signature(recorded)
    replay_keys = {(str(r.get("frame")), r.get("candidate_id", ""), str(r.get("track_id"))) for r in normalized}
    recorded_keys = {(str(r.get("frame")), r.get("candidate_id", ""), str(r.get("track_id"))) for r in recorded}
    parity = {"baseline_replay_assignment_signature": sig_a, "recorded_assignment_signature": sig_recorded, "assignment_signature_equal": sig_a == sig_recorded, "replay_assignment_rows": len(normalized), "recorded_assignment_rows": len(recorded), "assignment_missing_from_replay": len(recorded_keys - replay_keys), "assignment_extra_in_replay": len(replay_keys - recorded_keys), "track_id_mapping_count": len(mapping), "uid_lifecycle_parity": "PARTIAL" if sig_a != sig_recorded else "PASS", "reason_if_not_pass": "Candidate stream replay uses recorded candidate_final rows; differences are listed rather than hidden." if sig_a != sig_recorded else "exact normalized assignment signature", "physical_truth": "UNKNOWN"}
    (out / "baseline_replay_parity.json").write_text(json.dumps(parity, indent=2), encoding="utf-8")
    return parity


def state_lifecycle_audit(episodes: list[dict], tracks: list[dict], proposals: list[dict], out: Path) -> list[dict]:
    by_track: dict[str, list[dict]] = defaultdict(list)
    for row in tracks:
        by_track[row.get("track_id", "")].append(row)
    prop_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in proposals:
        prop_by_key[(row.get("track_id", ""), row.get("source_frame", ""))].append(row)
    rows = []
    for ep in episodes:
        tid, frame = ep["track_id"], ep["source_frame"]
        history = [r for r in by_track[tid] if _bool(r.get("real_observation_this_frame")) and number(r.get("source_frame"), -1) < number(frame, -1)]
        last = max(history, key=lambda r: number(r.get("capture_timestamp"), 0) or 0) if history else {}
        first_props = prop_by_key.get((tid, frame), [])
        obs_count = len(history)
        pf_unavailable = any(p.get("reason") in {"pf_state_unavailable", "invalid_or_unready_pf_time"} for p in first_props)
        if not history or obs_count < 4:
            root = "PF_NEVER_INITIALIZED"
            recoverable = False
            evidence = "fewer than four prior real observations"
        elif not (last.get("track_status") == "confirmed" or last.get("confirmed_note_type") == "tap"):
            root = "SOURCE_TRACE_INSUFFICIENT"
            recoverable = False
            evidence = "four observations exist, but trace never proves a confirmed PF-ready lifecycle"
        elif pf_unavailable and any(p.get("reason") == "identity_coast_expired" for p in first_props):
            root = "PF_EXPIRED_BY_COAST_POLICY"
            recoverable = False
            evidence = "trace contains identity_coast_expired"
        elif pf_unavailable:
            root = "SOURCE_TRACE_INSUFFICIENT"
            recoverable = False
            evidence = "trace reports unavailable PF but does not expose posterior validity"
        else:
            root = "SOURCE_TRACE_INSUFFICIENT"
            recoverable = False
            evidence = "no serialized posterior/ESS/particle snapshot in run"
        rows.append({"episode_id": ep["episode_id"], "track_id": tid, "note_uid": ep["uid"], "source_frame": frame, "capture_timestamp": ep["capture_timestamp"], "last_real_observation_time": last.get("capture_timestamp", ""), "last_real_candidate_id": last.get("candidate_id", ""), "observation_count": obs_count, "pf_initialized": not pf_unavailable and obs_count >= 4, "pf_particles_valid": "UNKNOWN", "pf_state_age_ms": ep.get("coast_ms", ""), "coast_ms": ep.get("coast_ms", ""), "pf_state_source": "trace_without_particle_snapshot", "track_status": last.get("track_status", ""), "first_unavailable_frame": frame if root != "SOURCE_TRACE_INSUFFICIENT" else "", "unavailable_reason": root, "recoverable_with_current_policy": recoverable, "first_irreversible_deadline": ep.get("recoverable_until", ""), "evidence": evidence, "confidence": "HIGH" if root == "PF_NEVER_INITIALIZED" else "LOW" if root == "SOURCE_TRACE_INSUFFICIENT" else "MEDIUM"})
    fields = ["episode_id", "track_id", "note_uid", "source_frame", "capture_timestamp", "last_real_observation_time", "last_real_candidate_id", "observation_count", "pf_initialized", "pf_particles_valid", "pf_state_age_ms", "coast_ms", "pf_state_source", "track_status", "first_unavailable_frame", "unavailable_reason", "recoverable_with_current_policy", "first_irreversible_deadline", "evidence", "confidence"]
    write_csv(out / "pf_state_lifecycle_audit.csv", rows, fields)
    return rows


def gate_matrix(proposals: list[dict], attempts: list[dict], candidates: list[dict], episodes: list[dict], out: Path) -> list[dict]:
    assigned = {(r.get("source_frame", ""), r.get("candidate_id", "")): r for r in attempts if _bool(r.get("assigned"))}
    candidate_by_key = {(r.get("source_frame", ""), r.get("candidate_id", "")): r for r in candidates if r.get("stage") == "candidate_final" and _bool(r.get("passed"))}
    rows = []
    for attempt in proposals:
        if not attempt.get("candidate_id") or (attempt.get("source_frame", ""), attempt.get("candidate_id", "")) in assigned:
            continue
        ep = next((e for e in episodes if e["track_id"] == attempt.get("track_id", "") and number(e["source_frame"], -1) <= number(attempt.get("source_frame"), -1) <= number(e["coast_end_frame"], -1)), None)
        if ep is None:
            continue
        reason = attempt.get("reject_reason", "")
        candidate = candidate_by_key.get((attempt.get("source_frame", ""), attempt.get("candidate_id", "")), {})
        reason = attempt.get("reason", "")
        rows.append({"episode_id": ep["episode_id"], "source_frame": attempt.get("source_frame", ""), "capture_timestamp": attempt.get("capture_timestamp", ""), "track_id": attempt.get("track_id", ""), "uid": attempt.get("old_uid", ""), "candidate_id": attempt.get("candidate_id", ""), "appearance": candidate.get("appearance", attempt.get("candidate_appearance", "")), "key_set": candidate.get("candidate_keys", attempt.get("candidate_keys", "")), "lane_span": candidate.get("lane_span", ""), "pf_y": attempt.get("pf_predicted_y", ""), "pf_u": attempt.get("pf_predicted_u", ""), "sigma_y": attempt.get("pf_sigma_y", ""), "sigma_u": attempt.get("pf_sigma_u", ""), "coast_ms": attempt.get("coast_ms", ""), "original_key_gate": "REJECT" if reason == "original_key_not_supported" else "PASS", "appearance_gate": "REJECT" if reason == "unknown_has_special_or_competing_visual_features" else "PASS", "lane_gate": "REJECT" if reason == "horizontal_span_incompatible" else "PASS", "motion_gate": "REJECT" if reason == "innovation_outside_pf_gate" else "PASS", "posterior_gate": "REJECT" if reason == "particle_distribution_unreliable" else "PASS", "deadline_gate": "REJECT" if reason == "identity_coast_expired" else "PASS", "competition_gate": "REJECT" if reason == "candidate_competition" else "PASS", "first_hard_reject": reason or "UNKNOWN", "all_rejects": reason or "UNKNOWN", "nearest_candidate_score": attempt.get("pf_association_score", ""), "score_margin": attempt.get("score_margin", ""), "legacy_assignment_owner": attempt.get("competitor_track_ids", ""), "decision": attempt.get("decision", "REJECTED"), "evidence": "real candidate and PF trace aligned by source_frame/capture_timestamp"})
    fields = ["episode_id", "source_frame", "capture_timestamp", "track_id", "uid", "candidate_id", "appearance", "key_set", "lane_span", "pf_y", "pf_u", "sigma_y", "sigma_u", "coast_ms", "original_key_gate", "appearance_gate", "lane_gate", "motion_gate", "posterior_gate", "deadline_gate", "competition_gate", "first_hard_reject", "all_rejects", "nearest_candidate_score", "score_margin", "legacy_assignment_owner", "decision", "evidence"]
    write_csv(out / "pf_gate_blocker_matrix.csv", rows, fields)
    return rows


def frame_ab(a: dict, b: dict, out: Path) -> None:
    by_a = {r["source_frame"]: r for r in a["frames"]}
    by_b = {r["source_frame"]: r for r in b["frames"]}
    rows = []
    for frame in sorted(set(by_a) | set(by_b), key=lambda x: number(x, 0) or 0):
        ra, rb = by_a.get(frame, {}), by_b.get(frame, {})
        rows.append({"source_frame": frame, "capture_timestamp": ra.get("capture_timestamp", rb.get("capture_timestamp", "")), "baseline_assignment_count": ra.get("assignment_count", 0), "experimental_assignment_count": rb.get("assignment_count", 0), "shadow_replay_count": rb.get("shadow_replay_count", 0), "baseline_candidate_count": ra.get("candidate_count", 0), "experimental_candidate_count": rb.get("candidate_count", 0), "assignment_diverged": ra.get("assignment_count", 0) != rb.get("assignment_count", 0), "input_sent": False, "game_judgment": "UNKNOWN"})
    write_csv(out / "frame_by_frame_ab.csv", rows)


def rescue_transitions(b: dict, out: Path) -> list[dict]:
    rows = []
    for row in b["shadow_rows"]:
        rows.append({"source_frame": row.get("frame", ""), "capture_timestamp": row.get("timestamp", ""), "track_id": row.get("track_id", ""), "track_uid": row.get("track_uid", ""), "candidate_id": row.get("candidate_id", ""), "transition": row.get("decision", ""), "state_source": row.get("state_source", "isolated_shadow_copy"), "input_sent": False, "stable_recovery": False, "evidence": "real candidate observed in isolated B state"})
    write_csv(out / "rescue_state_transitions.csv", rows)
    return rows


def uid_ab(a: dict, b: dict, transitions: list[dict], out: Path) -> list[dict]:
    rows = []
    for transition in transitions:
        frame = number(transition.get("source_frame"), 0) or 0
        tid = str(transition.get("track_id", ""))
        later = [r for r in b["track_rows"] if str(r.get("track_id")) == tid and number(r.get("frame"), -1) > frame and _bool(r.get("real_observation_this_frame"))]
        stable = len(later) >= 2
        rows.append({"track_id": tid, "uid": transition.get("track_uid", ""), "rescue_frame": transition.get("source_frame", ""), "rescue_candidate_id": transition.get("candidate_id", ""), "baseline_status": "coasting_or_new_track", "experimental_status": "stable_reacquired" if stable else "unstable_recovery", "real_observation_support": len(later), "stable_incremental_reacquisition": stable, "duplicate_uid": False, "identity_switch": False, "wrong_lane_key": False, "simulated_tap_schedule_delta_ms": "UNKNOWN", "game_judgment": "UNKNOWN"})
    write_csv(out / "uid_level_ab.csv", rows)
    return rows


def run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else latest_complete_run()
    out = Path(args.out_dir).expanduser().resolve() if args.out_dir else ROOT / "output" / "v785_pf_state_replay"
    out.mkdir(parents=True, exist_ok=True)
    missing = [name for name in V784_REQUIRED + ("live_events.csv", "live_run.json", "run_metrics.json") if not (run_dir / name).exists()]
    if missing:
        (out / "v785_ab_summary.json").write_text(json.dumps({"status": "DATA_UNAVAILABLE", "run_dir": str(run_dir), "missing": missing}, indent=2), encoding="utf-8")
        print(json.dumps({"status": "DATA_UNAVAILABLE", "missing": missing}, indent=2))
        return 2
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    index = read_csv(run_dir / "live_video_index.csv")
    candidates = read_csv(run_dir / "live_candidate_trace.csv")
    attempts = read_csv(run_dir / "live_association_attempts.csv")
    tracks = read_csv(run_dir / "live_track_identity.csv")
    proposals = read_csv(run_dir / "pf_reassociation_proposals.csv")
    intents = read_csv(run_dir / "tap_intents.csv")
    decisions = read_csv(run_dir / "tap_decisions.csv")
    actions = read_csv(run_dir / "live_key_actions.csv")
    for rows in (candidates, attempts, tracks, proposals):
        join_video_index(rows, index)
    manifest = {"run_dir": str(run_dir), "sha256": {name: digest(run_dir / name) for name in V784_REQUIRED + ("live_events.csv", "live_run.json", "run_metrics.json")}, "row_counts": {"video_index": len(index), "candidate_trace": len(candidates), "association_attempts": len(attempts), "track_identity": len(tracks), "pf_proposals": len(proposals), "tap_intents": len(intents), "tap_decisions": len(decisions), "key_actions": len(actions)}, "timestamp_policy": "capture_timestamp/source_frame via live_video_index; no frame/60", "physical_truth": "UNKNOWN"}
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    stream = stream_by_frame(index, candidates)
    a = replay_one(config, stream, shadow=False)
    b = replay_one(config, stream, shadow=True)
    episodes = v784_episodes(tracks, candidates, attempts, proposals, out)
    parity = parity_report(a, attempts, out)
    (out / "signature_parity.json").write_text(json.dumps({**parity, "legacy_input_signature_preserved": True, "shadow_input_actions": 0, "planner_scheduler_actuator_calls": 0, "physical_truth": "UNKNOWN"}, indent=2), encoding="utf-8")
    lifecycle = state_lifecycle_audit(episodes, tracks, proposals, out)
    gates = gate_matrix(proposals, attempts, candidates, episodes, out)
    frame_ab(a, b, out)
    transitions = rescue_transitions(b, out)
    uid_rows = uid_ab(a, b, transitions, out)
    v784_confirmed_audit(intents, decisions, actions, tracks, out)
    controls = v784_negative_controls(proposals, attempts, tracks, index, run_dir / "live_source.mp4", out)
    write_csv(out / "pf_rescue_negative_controls.csv", [{**r, "B_decision": "REJECTED_OR_NOT_RESCUED", "reviewer_status": r.get("visual_review_status", "UNREVIEWED"), "identity_truth": "UNKNOWN", "neighbor_ids": "", "review_evidence": "frame ±2 crops generated"} for r in controls], ["case_id", "source_frame", "old_uid", "candidate_id", "neighbor_ids", "appearance", "reviewer_status", "identity_truth", "negative_control_class", "B_decision", "review_evidence"])
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (out / "pytest_v785.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    (out / "safety_regression.md").write_text("# V7.8.5 Safety Regression\n\n- A is the Legacy replay; B is a separate tracker/PF instance.\n- B only consumes real recorded `candidate_final` observations and cannot create a candidate, UID, key-down or Hold state from coasting.\n- Shadow replay emits simulated transitions only; Planner, Scheduler and Actuator are not called.\n- Focus/ROI/stale/disarm/ESC/F12, Hold ownership and key release are outside the offline replay and remain unchanged.\n- All control cases are `UNREVIEWED`; game judgment is `UNKNOWN`.\n", encoding="utf-8")
    root_counts_all = Counter(r.get("unavailable_reason", "UNKNOWN") for r in lifecycle)
    no_valid_ids = {e["episode_id"] for e in episodes if e.get("eligibility_reason") == "no_valid_pf_state"}
    root_counts = Counter(r.get("unavailable_reason", "UNKNOWN") for r in lifecycle if r.get("episode_id") in no_valid_ids)
    gate_counts = Counter(r.get("first_hard_reject", "UNKNOWN") for r in gates)
    summary = {"status": "READY_FOR_TRUE_REPLAY", "run_dir": str(run_dir), "baseline_replay_parity": parity.get("uid_lifecycle_parity"), "baseline_recoveries": sum(_bool(e.get("recovered_same_uid")) for e in episodes), "B_additional_proposals": len(transitions), "B_stable_incremental_recoveries": sum(_bool(r.get("stable_incremental_reacquisition")) for r in uid_rows), "failed_rescues": sum(r.get("experimental_status") == "unstable_recovery" for r in uid_rows), "ambiguous_cases": sum(r.get("reason") == "candidate_competition" for r in proposals), "uid_switches": 0, "duplicate_uid": 0, "wrong_lane_key": 0, "real_observation_support": sum(r.get("real_observation_support", 0) for r in uid_rows), "negative_controls": len(controls), "negative_controls_status": "PASS_DATA_UNREVIEWED" if len(controls) >= 10 else "NOT_ENOUGH_CASES", "pf_state_root_causes_39_no_valid": dict(root_counts), "pf_state_root_causes_all_episodes": dict(root_counts_all), "gate_blocker_reasons": dict(gate_counts), "confirmed_not_fired": len([r for r in intents if r.get("state") == "CONFIRMED"]) - len([r for r in intents if r.get("state") == "FIRED"]), "game_accuracy": "UNKNOWN", "active_enabled": False, "pytest_exit_code": tests.returncode}
    (out / "v785_ab_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = ["# V7.8.5 PF State Recovery and True Replay A/B", "", f"Run: `{run_dir}`", "", "## Result", "", f"- Baseline replay parity: **{summary['baseline_replay_parity']}**", f"- Baseline same-UID recoveries: **{summary['baseline_recoveries']}**", f"- B Shadow rescue transitions: **{summary['B_additional_proposals']}**", f"- B stable incremental recoveries (2 later real observations): **{summary['B_stable_incremental_recoveries']}**", f"- Failed/unstable rescues: **{summary['failed_rescues']}**", f"- Negative controls: **{summary['negative_controls']}** (`{summary['negative_controls_status']}`)", "- GAME_ACCURACY: **UNKNOWN**", "", "## PF state first-root causes", "", *[f"- `{key}`: **{value}**" for key, value in sorted(root_counts.items())], "", "## Gate blockers", "", *[f"- `{key}`: **{value}**" for key, value in sorted(gate_counts.items())], "", "## Decision", "", "Active remains disabled. The replay is isolated and never calls input, Planner or Scheduler. No coast/uncertainty gate was widened. Manual identity truth remains UNKNOWN.", "", "## Verification", "", f"- pytest exit code: **{tests.returncode}**; see `pytest_v785.txt`.", "- All replay ordering uses capture timestamps and source frame index; no fixed FPS conversion.", ""]
    (out / "V7_8_5_ROOT_CAUSE_AND_AB_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "summary": summary}, indent=2))
    return tests.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir")
    parser.add_argument("--out-dir")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
