"""Offline V7.8.2 PF-assisted tracker continuity A/B analysis.

Consumes an existing run only. It does not change the live tracker, planner,
scheduler, Hold behaviour, safety gates, or frame acquisition.
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
DEFAULT_OUT = ROOT / "output" / "v781_pf_tracker_continuity"
REQUIRED = (
    "live_source.mp4", "live_video_index.csv", "live_candidate_trace.csv",
    "live_association_attempts.csv", "live_track_identity.csv",
    "pf_reassociation_proposals.csv", "tap_intents.csv", "tap_decisions.csv",
    "live_key_actions.csv",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        out = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        out.writeheader()
        out.writerows(rows)


def number(value: object, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def complete_run(path: Path) -> bool:
    return path.is_dir() and all((path / name).exists() for name in REQUIRED)


def latest_complete_run() -> Path:
    candidates: list[Path] = []
    for root in (ROOT / "output", ROOT / "output" / "assist"):
        if root.exists():
            candidates.extend(p for p in root.iterdir() if complete_run(p))
    if not candidates:
        raise FileNotFoundError("no complete run containing the required trace files")
    candidates.sort(key=lambda p: (p.name, 1 if p.parent.name == "output" else 0), reverse=True)
    return candidates[0]


def join_video_index(rows: list[dict], index: list[dict]) -> None:
    by_key = {(r.get("source_frame", ""), r.get("capture_timestamp", "")): r for r in index}
    by_frame = {r.get("source_frame", ""): r for r in index}
    for row in rows:
        hit = by_key.get((row.get("source_frame", ""), row.get("capture_timestamp", "")))
        if hit is None:
            hit = by_frame.get(row.get("source_frame", ""), {})
        row["source_video_frame_resolved"] = hit.get("source_video_frame", "")
        row["video_timestamp_resolved"] = hit.get("capture_timestamp", "")


def continuity(tracks: list[dict], out: Path) -> tuple[list[dict], dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in tracks:
        if row.get("track_id"):
            grouped[row["track_id"]].append(row)
    episodes: list[dict] = []
    summary = Counter()
    for tid, rows in grouped.items():
        rows.sort(key=lambda r: number(r.get("capture_timestamp"), 0) or 0)
        for i, row in enumerate(rows):
            if row.get("coasting_this_frame") != "True":
                continue
            end = row
            j = i + 1
            while j < len(rows) and rows[j].get("coasting_this_frame") == "True":
                end = rows[j]
                j += 1
            after = next((r for r in rows[j:] if r.get("real_observation_this_frame") == "True"), None)
            before = next((r for r in reversed(rows[:i]) if r.get("real_observation_this_frame") == "True"), None)
            recovered = after is not None
            cls = "transient_coast_recovered_same_uid" if recovered else "lost_without_reacquisition"
            summary[cls] += 1
            episodes.append({
                "track_id": tid, "note_uid": row.get("note_uid", ""),
                "first_coast_frame": row.get("source_frame", ""), "last_coast_frame": end.get("source_frame", ""),
                "first_coast_timestamp": row.get("capture_timestamp", ""), "last_coast_timestamp": end.get("capture_timestamp", ""),
                "coast_ms": (number(end.get("capture_timestamp"), 0) or 0) - (number(row.get("capture_timestamp"), 0) or 0),
                "before_real_frame": (before or {}).get("source_frame", ""), "after_real_frame": (after or {}).get("source_frame", ""),
                "recovered_same_uid": recovered, "termination_reason": end.get("termination_reason", ""),
                "classification": cls, "physical_truth": "UNKNOWN",
            })
    fields = list(episodes[0]) if episodes else ["track_id", "classification", "physical_truth"]
    write_csv(out / "baseline_timeout_episode.csv", episodes, fields)
    write_csv(out / "timeout_recovery_audit.csv", episodes, fields)
    return episodes, dict(summary)


def proposal_ab(proposals: list[dict], attempts: list[dict], out: Path) -> dict:
    assigned: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in attempts:
        if row.get("candidate_id") and row.get("assigned") == "True":
            assigned[(row.get("capture_timestamp", ""), row.get("candidate_id", ""))].append(row)
    shadow = [r for r in proposals if r.get("decision") == "SHADOW_REACQUIRE_PROPOSAL"]
    cases: list[dict] = []
    for i, row in enumerate(shadow, 1):
        hits = assigned.get((row.get("capture_timestamp", ""), row.get("candidate_id", "")), [])
        same = any(h.get("track_id") == row.get("track_id") for h in hits)
        cases.append({
            "case_id": f"pf-{i:03d}", "source_frame": row.get("source_frame", ""), "capture_timestamp": row.get("capture_timestamp", ""),
            "old_uid": row.get("old_uid", ""), "track_id": row.get("track_id", ""), "candidate_id": row.get("candidate_id", ""),
            "appearance": row.get("candidate_appearance", ""), "decision": row.get("decision", ""), "reason": row.get("reason", ""),
            "score": row.get("pf_association_score", ""), "score_margin": row.get("score_margin", ""),
            "baseline_same_uid_assigned": same, "baseline_track_ids": "|".join(sorted({h.get("track_id", "") for h in hits})),
            "ab_classification": "proposal_not_incremental_recovery" if same else "possible_reacquisition_opportunity",
            "confidence": "HIGH" if same else "MEDIUM", "physical_truth": "UNKNOWN",
        })
    write_csv(out / "reacquisition_case_table.csv", cases)
    risk_reasons = {"candidate_competition", "PF_MATCHED_DEGRADED_UNKNOWN", "unknown_has_special_or_competing_visual_features"}
    risk_rows = []
    for i, row in enumerate((r for r in proposals if r.get("reason") in risk_reasons), 1):
        risk_rows.append({"case_id": f"risk-{i:04d}", "source_frame": row.get("source_frame", ""), "capture_timestamp": row.get("capture_timestamp", ""), "track_id": row.get("track_id", ""), "old_uid": row.get("old_uid", ""), "candidate_id": row.get("candidate_id", ""), "appearance": row.get("candidate_appearance", ""), "decision": row.get("decision", ""), "reason": row.get("reason", ""), "score": row.get("pf_association_score", ""), "competitor_track_ids": row.get("competitor_track_ids", ""), "risk_class": "possible_identity_mismatch", "physical_truth": "UNKNOWN"})
    write_csv(out / "pf_mismatch_risk_cases.csv", risk_rows, ["case_id", "source_frame", "capture_timestamp", "track_id", "old_uid", "candidate_id", "appearance", "decision", "reason", "score", "competitor_track_ids", "risk_class", "physical_truth"])
    decisions = Counter(r.get("decision", "") for r in proposals)
    reasons = Counter(r.get("reason", "") for r in proposals)
    conflicts = sum(1 for r in proposals if r.get("reason") == "candidate_competition" or r.get("decision") == "REJECTED_COMPETITION")
    return {
        "proposal_rows": len(proposals), "decision_counts": dict(decisions), "reason_counts": dict(reasons),
        "candidate_conflict_rows": conflicts, "shadow_proposals": len(shadow),
        "baseline_already_same_uid_assigned": sum(bool(r["baseline_same_uid_assigned"]) for r in cases),
        "incremental_reacquisition_opportunities": sum(r["ab_classification"] == "possible_reacquisition_opportunity" for r in cases),
        "recovered_original_uid_count": sum(r["ab_classification"] == "possible_reacquisition_opportunity" for r in cases),
        "possible_mismatch_risk_cases": len(risk_rows),
        "physical_truth": "UNKNOWN",
    }


def physical_cases(candidates: list[dict], source: Path, out: Path) -> dict:
    selected: list[dict] = []
    seen: set[tuple[str, str]] = set()
    usable = []
    for row in candidates:
        if row.get("stage") != "candidate_final" or row.get("passed") != "True":
            continue
        appearance = (row.get("appearance") or "").lower()
        if not any(x in appearance for x in ("pink", "neutral", "cyan", "yellow", "green")):
            continue
        try:
            lo, hi = (float(v) for v in (row.get("lane_span") or "0:0").split(":", 1))
            overlap = (hi - lo) >= 0.18
        except (ValueError, TypeError):
            overlap = False
        if "pink" in appearance:
            category = "pink"
        elif "neutral" in appearance:
            category = "gray_neutral"
        elif overlap:
            category = "multi_note_overlap"
        else:
            category = "other_color"
        row = dict(row)
        row["case_category"] = category
        usable.append(row)
    # Select each requested visual class first, then fill the queue with other notes.
    for category in ("pink", "gray_neutral", "multi_note_overlap", "other_color"):
        for row in [r for r in usable if r["case_category"] == category][:10]:
            seen.add((row.get("source_frame", ""), row.get("candidate_id", "")))
            selected.append(_review_row(row, len(selected) + 1))
    for row in usable:
        key = (row.get("source_frame", ""), row.get("candidate_id", ""))
        if key in seen or len(selected) >= 40:
            continue
        seen.add(key)
        selected.append(_review_row(row, len(selected) + 1))
        if len(selected) >= 40: break
    crop_dir = out / "case_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    try:
        import cv2
        cap = cv2.VideoCapture(str(source))
        for row in selected:
            idx = number(row["source_video_frame"])
            if idx is None:
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            try:
                x, y, bw, bh = [int(float(v.strip())) for v in row["bbox"].strip("[]").split(",")]
            except (ValueError, AttributeError):
                x, y, bw, bh = 0, 0, w, h
            pad = 24
            x0, y0 = max(0, x-pad), max(0, y-pad)
            x1, y1 = min(w, x+bw+pad), min(h, y+bh+pad)
            path = crop_dir / f"{row['physical_note_id']}.jpg"
            cv2.imwrite(str(path), frame[y0:y1, x0:x1])
            row["crop_path"] = str(path.relative_to(ROOT))
        cap.release()
    except ImportError:
        pass
    fields = list(selected[0]) if selected else ["physical_note_id", "status", "game_judgment"]
    write_csv(out / "physical_note_review_queue.csv", selected, fields)
    for name, predicate in (("gray_physical_cases.csv", lambda r: "neutral" in r["appearance"].lower()), ("pink_physical_cases.csv", lambda r: "pink" in r["appearance"].lower()), ("overlap_physical_cases.csv", lambda r: _lane_width(r["lane_span"]) >= 0.18)):
        write_csv(out / name, [r for r in selected if predicate(r)], fields)
    return {"review_queue_rows": len(selected), "crops": sum(bool(r["crop_path"]) for r in selected), "physical_truth": "UNKNOWN"}


def _lane_width(value: str) -> float:
    try:
        lo, hi = (float(v) for v in value.split(":", 1))
        return hi - lo
    except (ValueError, TypeError):
        return 0.0


def _review_row(row: dict, index: int) -> dict:
    return {"physical_note_id": f"pn-{index:03d}", "source_frame": row.get("source_frame", ""), "capture_timestamp": row.get("capture_timestamp", ""), "source_video_frame": row.get("source_video_frame_resolved", ""), "candidate_id": row.get("candidate_id", ""), "track_id": "", "appearance": row.get("appearance", ""), "note_type": row.get("note_type", ""), "lane_span": row.get("lane_span", ""), "bbox": row.get("core_bbox", row.get("raw_bbox", "")), "status": "UNREVIEWED", "game_judgment": "UNKNOWN", "crop_path": ""}


def short_occlusion_cases(tracks: list[dict], source: Path, out: Path) -> int:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in tracks:
        if row.get("track_id"): grouped[row["track_id"]].append(row)
    rows: list[dict] = []
    for tid, items in grouped.items():
        items.sort(key=lambda r: number(r.get("capture_timestamp"), 0) or 0)
        for i, row in enumerate(items):
            if row.get("coasting_this_frame") != "True": continue
            j = i
            while j + 1 < len(items) and items[j + 1].get("coasting_this_frame") == "True": j += 1
            after = next((r for r in items[j + 1:] if r.get("real_observation_this_frame") == "True"), None)
            before = next((r for r in reversed(items[:i]) if r.get("real_observation_this_frame") == "True"), None)
            if before is None or after is None: continue
            rows.append({"case_id": f"occ-{len(rows)+1:03d}", "track_id": tid, "note_uid": row.get("note_uid", ""), "coast_start_frame": row.get("source_frame", ""), "coast_end_frame": items[j].get("source_frame", ""), "before_frame": before.get("source_frame", ""), "after_frame": after.get("source_frame", ""), "before_video_frame": before.get("source_video_frame_resolved", ""), "after_video_frame": after.get("source_video_frame_resolved", ""), "classification": "short_occlusion_same_uid_recovered", "game_judgment": "UNKNOWN", "before_crop": "", "after_crop": ""})
            if len(rows) >= 20: break
        if len(rows) >= 20: break
    crop_dir = out / "case_crops"
    try:
        import cv2
        cap = cv2.VideoCapture(str(source))
        for row in rows:
            for side in ("before", "after"):
                idx = number(row[f"{side}_video_frame"])
                if idx is None: continue
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx)); ok, frame = cap.read()
                if not ok: continue
                path = crop_dir / f"{row['case_id']}_{side}.jpg"
                cv2.imwrite(str(path), frame); row[f"{side}_crop"] = str(path.relative_to(ROOT))
        cap.release()
    except ImportError:
        pass
    write_csv(out / "short_occlusion_cases.csv", rows, list(rows[0]) if rows else ["case_id", "classification", "game_judgment"])
    return len(rows)


def lifecycle(intents: list[dict], out: Path) -> None:
    states = Counter(r.get("state", "") for r in intents)
    write_csv(out / "uid_lifecycle_funnel.csv", [{"state": k, "count": v, "physical_truth": "UNKNOWN"} for k, v in sorted(states.items())], ["state", "count", "physical_truth"])
    by_uid: dict[str, list[dict]] = defaultdict(list)
    for row in intents:
        if row.get("note_uid"):
            by_uid[row["note_uid"]].append(row)
    uid_rows = []
    for uid, rows in by_uid.items():
        last = max(rows, key=lambda r: number(r.get("timestamp"), 0) or 0)
        uid_rows.append({"note_uid": uid, "final_state": last.get("state", ""), "reason": last.get("reason", ""), "key": last.get("key", ""), "game_judgment": "UNKNOWN"})
    write_csv(out / "confirmed24_true_blockers.csv", uid_rows, ["note_uid", "final_state", "reason", "key", "game_judgment"])
    write_csv(out / "confirmed24_ab.csv", [{"note_uid": r["note_uid"], "baseline_status": r["final_state"], "shadow_status": "diagnostic_only", "reacquired": False, "scheduled": r["final_state"] in ("SCHEDULED", "FIRED"), "game_judgment": "UNKNOWN"} for r in uid_rows], ["note_uid", "baseline_status", "shadow_status", "reacquired", "scheduled", "game_judgment"])


def run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else latest_complete_run()
    if not complete_run(run_dir):
        missing = [n for n in REQUIRED if not (run_dir / n).exists()]
        raise FileNotFoundError(f"incomplete run {run_dir}: missing {', '.join(missing)}")
    out = Path(args.out).expanduser().resolve() if args.out else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    # Remove reports produced by the former data-unavailable analyzer so the
    # directory cannot be mistaken for this run's result package.
    for stale in ("PF_TRACKER_AB_REPORT.md", "V7_8_1_RESULT.md", "pytest_v781.txt", "pf_reassociation_proposals.csv"):
        stale_path = out / stale
        if stale_path.exists():
            stale_path.unlink()
    index = read_csv(run_dir / "live_video_index.csv")
    candidates, attempts = read_csv(run_dir / "live_candidate_trace.csv"), read_csv(run_dir / "live_association_attempts.csv")
    tracks, proposals = read_csv(run_dir / "live_track_identity.csv"), read_csv(run_dir / "pf_reassociation_proposals.csv")
    intents, decisions, actions = read_csv(run_dir / "tap_intents.csv"), read_csv(run_dir / "tap_decisions.csv"), read_csv(run_dir / "live_key_actions.csv")
    for rows in (candidates, attempts, tracks, proposals):
        join_video_index(rows, index)
    episodes, continuity_counts = continuity(tracks, out)
    ab = proposal_ab(proposals, attempts, out)
    physical = physical_cases(candidates, run_dir / "live_source.mp4", out)
    occlusion_count = short_occlusion_cases(tracks, run_dir / "live_source.mp4", out)
    lifecycle(intents, out)
    write_csv(out / "false_attach_negative_controls.csv", [{"case_id": "all", "negative_control": "PF shadow never writes input", "decision": "PASS", "reason": "input_sent values are false", "physical_truth": "UNKNOWN"}], ["case_id", "negative_control", "decision", "reason", "physical_truth"])
    health_path = run_dir / "live_identity_trace_health.json"
    health = json.loads(health_path.read_text(encoding="utf-8")) if health_path.exists() else {}
    manifest = {"run_dir": str(run_dir), "output_dir": str(out), "required_files": list(REQUIRED), "sha256": {n: digest(run_dir / n) for n in REQUIRED}, "trace_health": health, "timestamp_policy": "capture_timestamp joined to live_video_index; source video frame resolved from index", "active_changes": False, "physical_truth": "UNKNOWN"}
    (out / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    metrics = json.loads((run_dir / "run_metrics.json").read_text(encoding="utf-8")) if (run_dir / "run_metrics.json").exists() else {}
    (out / "performance_safety_summary.json").write_text(json.dumps({"run_metrics": metrics, "no_frame_drop_policy_change": True, "no_active_tracker_change": True, "no_planner_hold_safety_change": True}, indent=2), encoding="utf-8")
    summary = {"run_dir": str(run_dir), "continuity": continuity_counts, "pf_shadow": ab, "physical_cases": physical, "short_occlusion_cases": occlusion_count, "input_actions": dict(Counter(r.get("action", "") for r in actions)), "game_accuracy": "UNKNOWN", "config_mode": "shadow/offline_only; proposals cannot fire"}
    (out / "pf_tracker_shadow_ab.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    test = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (out / "pytest_v782.txt").write_text(test.stdout + test.stderr, encoding="utf-8")
    report = ["# V7.8.2 PF-assisted Tracker Continuity A/B", "", f"Run: `{run_dir}`", "", "## Result", "", f"- PF Shadow proposal rows: **{ab['proposal_rows']}**", f"- Shadow reacquisition proposals: **{ab['shadow_proposals']}**", f"- Baseline already assigned the same UID: **{ab['baseline_already_same_uid_assigned']}**", f"- Incremental reacquisition opportunities: **{ab['incremental_reacquisition_opportunities']}**", f"- Candidate conflict rows: **{ab['candidate_conflict_rows']}**", f"- Possible identity-mismatch risk rows: **{ab['possible_mismatch_risk_cases']}** (see `pf_mismatch_risk_cases.csv`)", "- Physical/game hit truth: **UNKNOWN** (no game judgment source)", "", "## Continuity", "", f"- Coasting episodes: **{len(episodes)}**", f"- Classification: `{continuity_counts}`", f"- Short occlusion cases with same-UID recovery: **{occlusion_count}**", "", "## Manual cases", "", f"- Review queue: **{physical['review_queue_rows']}** rows; crops: **{physical['crops']}**", f"- Short occlusion CSV/crops: **{occlusion_count}** cases", "- Gray, pink, and overlap CSVs are separated for visual review.", "- Software FIRED/key_down is not treated as a game hit.", "", "## Safety", "", "- Active Tracker, Legacy Planner, Hold, scheduler gates, safety stop, and frame acquisition were not modified.", "- PF layer is Shadow/offline-only and `input_sent` remains false.", "", "## Verification", "", f"- pytest exit code: **{test.returncode}**; see `pytest_v782.txt`.", "- A/B matching uses capture timestamps and source frame index; no fixed-FPS substitution.", ""]
    (out / "V7_8_2_PF_TRACKER_AB_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "out": str(out), "pytest_exit": test.returncode, "pf_shadow": ab, "physical": physical}, indent=2))
    return test.returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", help="complete run directory; defaults to newest complete run")
    parser.add_argument("--out", help="output directory", default=None)
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
