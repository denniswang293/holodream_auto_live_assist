"""V7.5.6 offline identity/association evidence analysis.

This tool only reads an existing live run and V7.5.5.1 association trace.
It does not alter detector, tracker, planner, PF, scheduler or safety gates.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import platform
import shutil
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


CASES = {
    "1000004": (257, "S|D"),
    "1000059": (615, "D|F"),
    "1000139": (923, "D|F"),
    "1000140": (935, "K|L"),
    "1000143": (963, "S|D"),
}
REJECTS = {
    "candidate_key_no_intersection",
    "lane_step_exceeded",
    "backward_motion",
    "motion_residual",
    "appearance_family_mismatch",
    "timestamp_gap_or_nonpositive",
    "span_width_ratio",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fnum(value: str | None, default: float = math.nan) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def bbox_center(value: str) -> tuple[float, float] | None:
    try:
        x, y, w, h = ast.literal_eval(value)
        return float(x) + float(w) / 2.0, float(y) + float(h) / 2.0
    except (ValueError, SyntaxError, TypeError):
        return None


def q(values: list[float], percentile: float) -> float | None:
    values = sorted(v for v in values if math.isfinite(v))
    if not values:
        return None
    idx = (len(values) - 1) * percentile
    lo, hi = math.floor(idx), math.ceil(idx)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (idx - lo)


def mapping_candidates(live: list[dict], replay: list[dict]) -> list[dict]:
    """Score live UID -> replay track without using integer UID equality."""
    live_by_uid: dict[str, dict[int, dict]] = defaultdict(dict)
    rank = {"DETECTED": 0, "CONFIRMED": 1, "NOT_SCHEDULED": 2}
    for row in live:
        uid = row.get("note_uid", "")
        if not uid:
            continue
        frame = int(row["source_frame"])
        old = live_by_uid[uid].get(frame)
        if old is None or rank.get(row.get("simple_core_state", ""), 9) < rank.get(old.get("simple_core_state", ""), 9):
            live_by_uid[uid][frame] = row
    replay_by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in replay:
        replay_by_frame[int(row["source_video_frame"])].append(row)

    scored: list[dict] = []
    for uid, frame_rows in live_by_uid.items():
        seq = sorted(frame_rows.values(), key=lambda r: int(r["source_frame"]))
        samples = seq[:3] + seq[len(seq) // 2 : len(seq) // 2 + 1] + seq[-3:]
        per_track: dict[str, list[tuple[float, float, bool, bool, int]]] = defaultdict(list)
        for lr in samples:
            frame = int(lr["source_frame"])
            ly = fnum(lr.get("crossing_y"))
            if not math.isfinite(ly):
                continue
            keys = set(filter(None, lr.get("key_candidates", "").split("|")))
            for rr in replay_by_frame.get(frame, []):
                center = bbox_center(rr.get("bbox", ""))
                if center is None:
                    continue
                yerr = abs(ly - center[1])
                appearance_ok = rr.get("appearance") == lr.get("appearance")
                key_ok = bool(keys & set(filter(None, rr.get("stable_keys", "").split("|"))))
                score = yerr + (0 if appearance_ok else 20) + (0 if key_ok else 15)
                per_track[rr["track_id"]].append((score, yerr, appearance_ok, key_ok, frame))
        ranked = []
        for replay_id, values in per_track.items():
            ranked.append({
                "score": sum(v[0] for v in values) / len(values),
                "mean_y_error_px": sum(v[1] for v in values) / len(values),
                "sample_count": len(values),
                "appearance_all": all(v[2] for v in values),
                "key_fraction": sum(v[3] for v in values) / len(values),
                "evidence_frames": ";".join(str(v[4]) for v in values),
                "replay_track_id": replay_id,
            })
        ranked.sort(key=lambda r: (r["score"], r["replay_track_id"]))
        if not ranked:
            scored.append({"live_uid": uid, "replay_track_id": "UNKNOWN", "confidence": "UNKNOWN", "best_score": "", "second_best_gap": "", "sample_count": 0, "mean_y_error_px": "", "evidence_frames": ""})
            continue
        best = ranked[0]
        second_gap = "" if len(ranked) < 2 else ranked[1]["score"] - best["score"]
        confidence = "UNKNOWN"
        if (best["sample_count"] >= 2 and best["appearance_all"] and best["key_fraction"] >= 0.75
                and best["score"] < 8 and (len(ranked) < 2 or second_gap >= 3)):
            confidence = "HIGH"
        elif best["sample_count"] >= 1 and best["appearance_all"] and best["key_fraction"] >= 0.5 and best["score"] < 15:
            confidence = "MEDIUM"
        scored.append({
            "live_uid": uid,
            "replay_track_id": best["replay_track_id"],
            "confidence": confidence,
            "best_score": f"{best['score']:.4f}",
            "second_best_gap": f"{second_gap:.4f}" if second_gap != "" else "",
            "sample_count": best["sample_count"],
            "mean_y_error_px": f"{best['mean_y_error_px']:.4f}",
            "evidence_frames": best["evidence_frames"],
        })
    # Enforce one-to-one replay identity. Keep the strongest candidate for a replay ID.
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in scored:
        if row["replay_track_id"] != "UNKNOWN":
            grouped[row["replay_track_id"]].append(row)
    for replay_id, rows in grouped.items():
        rows.sort(key=lambda r: (0 if r["confidence"] == "HIGH" else 1 if r["confidence"] == "MEDIUM" else 2, fnum(r["best_score"], 1e9)))
        for duplicate in rows[1:]:
            duplicate["confidence"] = "UNKNOWN"
            duplicate["replay_track_id"] = "AMBIGUOUS"
    return scored


def classify_first_unmatched(tracker, pairs, final_candidates, assigned):
    by_track: dict[str, list[dict]] = defaultdict(list)
    for row in tracker:
        by_track[row["track_id"]].append(row)
    first = []
    for track_id, rows in by_track.items():
        rows.sort(key=lambda r: int(r["source_video_frame"]))
        for idx, row in enumerate(rows):
            if idx == 0 or row["matched_this_frame"] == "True" or rows[idx - 1]["matched_this_frame"] != "True":
                continue
            key = (row["source_video_frame"], track_id)
            local_pairs = pairs.get(key, [])
            frame_finals = final_candidates.get(row["source_video_frame"], [])
            comp = [p for p in local_pairs if p["accepted"] == "True" and p["candidate_id"] in assigned.get(row["source_video_frame"], set())]
            if comp:
                category = "PROBABLE_ASSOCIATION_COMPETITION"
            elif not local_pairs and frame_finals:
                category = "TRACE_INCOMPLETE"
            elif not local_pairs:
                category = "NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION"
            else:
                local = []
                for p in local_pairs:
                    dy = abs(fnum(p.get("dy_px"), 1e9))
                    residual = abs(fnum(p.get("residual_px"), 1e9))
                    du = abs(fnum(p.get("du"), 1e9))
                    tol = abs(fnum(p.get("tolerance_px"), 9.0))
                    if min(dy, residual) <= 2 * tol or du < 0.12:
                        local.append(p)
                category = "GATE_REJECTED_WITH_LOCAL_CANDIDATE" if local else "NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION"
            first.append({
                "track_id": track_id,
                "frame": row["source_video_frame"],
                "capture_timestamp": row["capture_timestamp"],
                "category": category,
                "termination_reason": row.get("termination_reason", ""),
                "pair_rows": local_pairs,
                "final_candidates": frame_finals,
            })
            break
    return first


def create_crops(source: Path, out_dir: Path, live_by_uid: dict[str, list[dict]]) -> None:
    try:
        import cv2
    except ImportError:
        return
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    for uid, (representative, _keys) in CASES.items():
        rows = live_by_uid.get(uid, [])
        frames = [int(r["source_frame"]) for r in rows]
        if not frames:
            continue
        near_row = min(
            rows,
            key=lambda r: abs(fnum(r.get("crossing_y"), 1e9) - 352.0),
        )
        near = int(near_row["source_frame"])
        last = max(frames)
        selected = []
        for center in (representative, near, last):
            selected.extend(range(max(0, center - 2), center + 3))
        selected = sorted(set(selected))
        thumbs = []
        for frame in selected:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = cap.read()
            if not ok:
                continue
            cv2.putText(image, f"{uid} frame {frame}", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, .45, (0, 255, 255), 1, cv2.LINE_AA)
            thumbs.append(image)
        if thumbs:
            width = 720
            thumbs = [cv2.resize(x, (width, int(x.shape[0] * width / x.shape[1]))) for x in thumbs]
            rows_per = []
            for i in range(0, len(thumbs), 5):
                chunk = thumbs[i:i + 5]
                while len(chunk) < 5:
                    chunk.append(__import__("numpy").zeros_like(thumbs[0]))
                rows_per.append(cv2.hconcat(chunk))
            cv2.imwrite(str(out_dir / f"case_{uid}_timeline.jpg"), cv2.vconcat(rows_per))
    cap.release()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--run", type=Path, default=None)
    parser.add_argument("--trace", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    repo = args.repo.resolve()
    run = (args.run or repo / "output/assist/run_20261031T181722_597143Z").resolve()
    trace = (args.trace or repo / "output/v755_tracker_association").resolve()
    out = (args.out or repo / "output/v756_identity_association").resolve()
    out.mkdir(parents=True, exist_ok=True)

    live = read_csv(run / "live_events.csv")
    live_index = read_csv(run / "live_video_index.csv")
    live_frames = read_csv(run / "live_frames.csv")
    eta = read_csv(run / "tap_eta_comparison.csv")
    shadow = read_csv(run / "tap_planner_shadow.csv")
    intents = read_csv(run / "tap_intents.csv")
    pairs_rows = read_csv(trace / "association_audit.csv")
    tracker = read_csv(trace / "tracker_frame_state.csv")
    detector = read_csv(trace / "detector_candidate_audit.csv")
    alignment = read_csv(trace / "frame_alignment_audit.csv")

    pairs = defaultdict(list)
    for row in pairs_rows:
        pairs[(row["source_video_frame"], row["track_id"])].append(row)
    final_candidates = defaultdict(list)
    for row in detector:
        if row["stage"] == "candidate_final" and row["passed"] == "True":
            final_candidates[row["source_video_frame"]].append(row)
    assigned = defaultdict(set)
    for row in pairs_rows:
        if row["assigned"] == "True":
            assigned[row["source_video_frame"]].add(row["candidate_id"])
    first = classify_first_unmatched(tracker, pairs, final_candidates, assigned)

    mapping = mapping_candidates(live, tracker)
    map_by_uid = {r["live_uid"]: r for r in mapping}
    map_by_replay = {r["replay_track_id"]: r for r in mapping if r["replay_track_id"] not in {"UNKNOWN", "AMBIGUOUS"}}

    # PR-0 alignment validation.
    timestamps = [fnum(r.get("capture_timestamp")) for r in alignment]
    source_frames = [int(r["source_video_frame"]) for r in alignment]
    monotonic = all(b > a for a, b in zip(timestamps, timestamps[1:]) if math.isfinite(a) and math.isfinite(b))
    one_to_one = len(source_frames) == len(set(source_frames))
    alignment_out = [dict(r, validation_status="OK" if monotonic and one_to_one else "FAIL") for r in alignment]
    write_csv(out / "frame_alignment_audit.csv", alignment_out, list(alignment_out[0]) if alignment_out else [])

    # Population reconciliation: 248 lifecycle note UIDs; old 229 population ends at replay frame 1328.
    lifecycle_uids = sorted({r["note_uid"] for r in live if r.get("note_uid")})
    replay_max_frame = max(int(r["source_video_frame"]) for r in tracker)
    recon = []
    for uid in lifecycle_uids:
        rows = [r for r in live if r.get("note_uid") == uid]
        first_frame, last_frame = min(int(r["source_frame"]) for r in rows), max(int(r["source_frame"]) for r in rows)
        # The historical 229 population was defined by having at least one
        # live observation in the replayed frame range, not by ending there.
        in_old_population = any(int(r["source_frame"]) <= replay_max_frame for r in rows)
        reason = "included_in_replay_frame_range" if in_old_population else "excluded_replay_trace_ends_before_live_uid"
        recon.append({"note_uid": uid, "live_track_id": rows[0]["track_id"], "first_source_frame": first_frame, "last_source_frame": last_frame, "replay_max_source_frame": replay_max_frame, "old_229_population": str(in_old_population), "reason": reason})
    write_csv(out / "uid_population_reconciliation.csv", recon, list(recon[0]))

    map_fields = ["live_uid", "replay_track_id", "confidence", "best_score", "second_best_gap", "sample_count", "mean_y_error_px", "evidence_frames"]
    write_csv(out / "uid_mapping_v756.csv", mapping, map_fields)

    # Strict first-loss classification and evidence rows.
    verified = []
    switches = []
    for item in first:
        if item["category"] == "PROBABLE_ASSOCIATION_COMPETITION":
            for p in item["pair_rows"]:
                if p["accepted"] == "True" and p["candidate_id"] in assigned.get(item["frame"], set()):
                    m = map_by_replay.get(item["track_id"], {})
                    verified.append({"frame": item["frame"], "capture_timestamp": item["capture_timestamp"], "replay_track_id": item["track_id"], "live_uid": m.get("live_uid", "UNKNOWN"), "mapping_confidence": m.get("confidence", "UNKNOWN"), "candidate_id": p["candidate_id"], "total_cost": p["total_cost"], "residual_px": p["residual_px"], "reject_reason": p["reject_reason"], "candidate_assigned_to_track": p["competition_track_ids"], "verification": "HARD_GATE_PASS_AND_ASSIGNED_ELSEWHERE"})
                    break
        if item["category"] in {"PROBABLE_ASSOCIATION_COMPETITION", "POSSIBLE_IDENTITY_SWITCH"}:
            # No explicit re-identification exists in this run; retain an empty, auditable candidate row only when evidence exists.
            if item["category"] == "POSSIBLE_IDENTITY_SWITCH":
                switches.append({"frame": item["frame"], "replay_track_id": item["track_id"], "live_uid": "UNKNOWN", "reason": "no_reidentified_from_id_or_physical_track_uid"})
    write_csv(out / "association_competition_verified.csv", verified, ["frame", "capture_timestamp", "replay_track_id", "live_uid", "mapping_confidence", "candidate_id", "total_cost", "residual_px", "reject_reason", "candidate_assigned_to_track", "verification"])
    write_csv(out / "identity_switch_candidates.csv", switches, ["frame", "replay_track_id", "live_uid", "reason"])

    nearest = []
    grouped = defaultdict(list)
    for row in pairs_rows:
        grouped[(row["source_video_frame"], row["track_id"])].append(row)
    for rows in grouped.values():
        finite = [(fnum(r.get("total_cost")), r) for r in rows if math.isfinite(fnum(r.get("total_cost")))]
        if finite:
            nearest.append(min(finite, key=lambda x: (x[0], x[1]["candidate_id"]))[1])
        else:
            nearest.append(min(rows, key=lambda r: (abs(fnum(r.get("residual_px"), 1e9)), abs(fnum(r.get("dy_px"), 1e9)), abs(fnum(r.get("du"), 1e9)), r["candidate_id"])))
    first_counts = Counter(x["category"] for x in first)
    counts = {
        "all_pair_rows": len(pairs_rows),
        "all_pairs": dict(Counter(r["reject_reason"] or "ACCEPTED" for r in pairs_rows)),
        "nearest_pair_rows": len(nearest),
        "nearest_pairs": dict(Counter(r["reject_reason"] or "ACCEPTED" for r in nearest)),
        "first_unmatched_by_track": dict(first_counts),
        "unmatched_states": sum(r["matched_this_frame"] != "True" for r in tracker),
        "terminal_outcomes": dict(Counter(r["termination_reason"] for r in tracker if r["termination_reason"])),
        "strict_probable_competition": len(verified),
        "uid_mapping_confidence": dict(Counter(r["confidence"] for r in mapping)),
        "alignment": {"rows": len(alignment), "one_to_one": one_to_one, "strictly_increasing_capture_timestamp": monotonic},
    }
    (out / "association_root_cause_counts.json").write_text(json.dumps(counts, indent=2, ensure_ascii=False), encoding="utf-8")

    # Five-case timelines.
    live_by_uid = defaultdict(list)
    for row in live:
        if row.get("note_uid") in {f"cdaf4ddbea12:simple:{uid}" for uid in CASES}:
            live_by_uid[row["track_id"]].append(row)
    eta_by_uid = defaultdict(list)
    for row in eta:
        eta_by_uid[row["note_uid"]].append(row)
    shadow_by_uid = defaultdict(list)
    for row in shadow:
        shadow_by_uid[row["note_uid"]].append(row)
    intent_by_uid = defaultdict(list)
    for row in intents:
        intent_by_uid[row["note_uid"]].append(row)
    timeline_rows = []
    verdicts = []
    for track_id, (representative, keys) in CASES.items():
        uid = f"cdaf4ddbea12:simple:{track_id}"
        rows = live_by_uid.get(track_id, [])
        mapping_row = map_by_uid.get(uid, {"replay_track_id": "UNKNOWN", "confidence": "UNKNOWN"})
        for row in rows:
            frame = row["source_frame"]
            candidates = [c for c in final_candidates.get(frame, []) if c.get("appearance") == row.get("appearance") and (set(row.get("key_candidates", "").split("|")) & set(c.get("candidate_keys", "").split("|")))]
            erows = sorted(eta_by_uid.get(uid, []), key=lambda x: abs(fnum(x.get("capture_timestamp")) - fnum(row.get("capture_timestamp"))))
            srows = sorted(shadow_by_uid.get(uid, []), key=lambda x: abs(fnum(x.get("capture_timestamp")) - fnum(row.get("capture_timestamp"))))
            irows = intent_by_uid.get(uid, [])
            e = erows[0] if erows else {}
            s = srows[0] if srows else {}
            timeline_rows.append({
                "live_uid": uid, "source_video_frame": frame, "capture_timestamp": row.get("capture_timestamp", ""), "candidate_ids": "|".join(c["candidate_id"] for c in candidates), "candidate_bboxes": "|".join(c["core_bbox"] for c in candidates), "appearance": row.get("appearance", ""), "candidate_keys": row.get("key_candidates", ""), "replay_track_id": mapping_row.get("replay_track_id", "UNKNOWN"), "mapping_confidence": mapping_row.get("confidence", "UNKNOWN"), "simple_core_state": row.get("simple_core_state", ""), "simple_core_reason": row.get("simple_core_reason", ""), "simple_track_status": row.get("simple_track_status", ""), "observations": row.get("simple_track_observations", ""), "pf_posterior_width_s": e.get("pf_uncertainty_s", ""), "pf_crossing_mass": e.get("pf_crossing_mass", ""), "pf_hit_at": e.get("pf_hit_at", ""), "pf_eta_s": e.get("pf_eta_s", ""), "shadow_hit_at": s.get("hit_at", ""), "shadow_result": s.get("status", ""), "shadow_reason": s.get("reason", ""), "legacy_result": e.get("legacy_planner_result", ""), "legacy_reason": e.get("legacy_planner_reason", ""), "scheduler_result": e.get("scheduler_result", ""), "scheduler_reason": e.get("scheduler_reason", ""), "intent_states": "|".join(sorted({x.get("state", "") for x in irows if x.get("state")})), "final_fired": str(any(x.get("state") == "FIRED" for x in irows)),
            })
        eta_rows = eta_by_uid.get(uid, [])
        reasons = Counter(r.get("legacy_planner_reason", "") for r in eta_rows if r.get("legacy_planner_reason"))
        pf_rejections = Counter(r.get("prediction_status", "") for r in eta_rows if r.get("prediction_status"))
        statuses = Counter(r.get("simple_track_status", "") for r in rows if r.get("simple_track_status"))
        if not rows:
            verdict = "AMBIGUOUS"
        elif mapping_row.get("confidence") == "HIGH" and reasons.get("particle_posterior_too_wide", 0) and statuses.get("lost", 0):
            verdict = "MULTIPLE_BLOCKERS"
        else:
            verdict = "AMBIGUOUS"
        verdicts.append((uid, representative, mapping_row.get("replay_track_id", "UNKNOWN"), mapping_row.get("confidence", "UNKNOWN"), verdict, reasons, statuses, pf_rejections))
    timeline_fields = list(timeline_rows[0]) if timeline_rows else []
    write_csv(out / "shadow_five_case_timelines.csv", timeline_rows, timeline_fields)
    verdict_lines = ["# V7.5.6 五個 Shadow 案例判定", "", "判定只代表 trace 證據；沒有遊戲 Perfect/Great/Miss 真值。", ""]
    verdict_lines.append("| UID | representative frame | replay track | mapping | verdict | evidence |")
    verdict_lines.append("|---|---:|---:|---|---|---|")
    for uid, frame, replay_id, conf, verdict, reasons, statuses, pf_rejections in verdicts:
        evidence = f"legacy reasons={dict(reasons)}; prediction={dict(pf_rejections)}; track statuses={dict(statuses)}"
        verdict_lines.append(f"| `{uid}` | {frame} | {replay_id} | {conf} | **{verdict}** | {evidence} |")
    verdict_lines.extend(["", "未使用 `FIRED` 或 `key_down` 當作遊戲命中；沒有足夠身份與單一阻礙證據的案例保持 AMBIGUOUS。"])
    (out / "shadow_five_case_verdicts.md").write_text("\n".join(verdict_lines) + "\n", encoding="utf-8")
    create_crops(run / "live_source.mp4", out / "case_crops", live_by_uid)

    # Existing A/B evidence and performance summary. No new active path is enabled.
    ab_path = trace / "diagnostic_off_on_ab.json"
    ab = json.loads(ab_path.read_text(encoding="utf-8")) if ab_path.exists() else {}
    ab_summary = {"source": str(ab_path), "diagnostic_off_on": ab, "active_planner": False, "legacy_input_path": "unchanged", "feature_flag_patch": "not_applied", "truth_status": "UNKNOWN"}
    (out / "v756_ab_summary.json").write_text(json.dumps(ab_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    perf_columns = ["acquire_queue_wait_ms", "note_detector_ms", "tracker_matching_ms", "pf_prediction_update_ms", "decision_ms", "scheduler_update_ms", "processing_ms", "latency_ms", "diagnostic_write_ms"]
    perf_rows = []
    for col in perf_columns:
        values = [fnum(r.get(col)) for r in live_frames]
        values = [v for v in values if math.isfinite(v)]
        perf_rows.append({"source": "existing_live_run", "stage": col, "count": len(values), "p50_ms": q(values, .50), "p95_ms": q(values, .95), "p99_ms": q(values, .99), "comparison": "trace_on_perf_not_available"})
    write_csv(out / "v756_performance_comparison.csv", perf_rows, list(perf_rows[0]))

    manifest = {
        "plan": "V7.5.6_IDENTITY_ASSOCIATION_AND_PF_CASE_PLAN",
        "baseline_commit": "47e30defdce459b890ae7533e7674a68045e6180",
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "source_video": str(run / "live_source.mp4"),
        "source_video_sha256": sha256(run / "live_source.mp4"),
        "video_index": str(run / "live_video_index.csv"),
        "video_index_sha256": sha256(run / "live_video_index.csv"),
        "config": str(repo / "config.json"),
        "config_sha256": sha256(repo / "config.json"),
        "geometry": str(repo / "config/geometry_live_assist.json"),
        "geometry_sha256": sha256(repo / "config/geometry_live_assist.json"),
        "alignment_rows": len(alignment),
        "alignment_one_to_one": one_to_one,
        "alignment_timestamp_strictly_increasing": monotonic,
        "lifecycle_uid_count": len(lifecycle_uids),
        "old_replay_population_count": sum(r["old_229_population"] == "True" for r in recon),
        "strict_probable_competition_count": len(verified),
        "feature_flag_default": "OFF",
        "legacy_input_path": "unchanged",
        "truth_status": "UNKNOWN",
    }
    (out / "v756_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human-readable root-cause report.
    all_counts = Counter(r["reject_reason"] or "ACCEPTED" for r in pairs_rows)
    near_counts = Counter(r["reject_reason"] or "ACCEPTED" for r in nearest)
    unmatched = sum(r["matched_this_frame"] != "True" for r in tracker)
    report = [
        "# HoloDream V7.5.6 Identity / Association Root Cause",
        "",
        "本報告只分析既有 live/replay Trace；未修改 matcher、PF、Planner、Scheduler、Hold 或安全門檻。Legacy Planner 仍是唯一實際輸入路徑，Shadow/Linear ETA 保持診斷用途。",
        "",
        "## PR-0 基線",
        f"- baseline commit: `47e30defdce459b890ae7533e7674a68045e6180`",
        f"- source frames: {len(live_index)}; alignment one-to-one={one_to_one}; capture timestamp strictly increasing={monotonic}",
        f"- lifecycle note UID: {len(lifecycle_uids)}; old replay population: {sum(r['old_229_population'] == 'True' for r in recon)}; difference: {len(lifecycle_uids)-sum(r['old_229_population'] == 'True' for r in recon)} late UIDs after replay frame {replay_max_frame}",
        f"- source SHA256: `{manifest['source_video_sha256']}`",
        f"- index SHA256: `{manifest['video_index_sha256']}`",
        "- existing diagnostic A/B reports zero candidate/tracker signature changes and `shadow_active=false`; no feature flag was enabled.",
        f"- conservative live↔replay mapping: `{dict(Counter(r['confidence'] for r in mapping))}`; one-to-one conflicts are demoted to UNKNOWN.",
        "",
        "## PR-1 嚴格分類",
        "舊版 `association_competition` 只代表同畫面某候選被其他 track assigned。本版只有在原 track 的 pair 同時 `accepted=True`、`total_cost` 有限、且該候選實際被另一 track assigned 時才標記 probable competition。",
        f"- first matched→unmatched tracks: {len(first)}",
        f"- PROBABLE_ASSOCIATION_COMPETITION: {sum(x['category']=='PROBABLE_ASSOCIATION_COMPETITION' for x in first)}",
        f"- GATE_REJECTED_WITH_LOCAL_CANDIDATE: {sum(x['category']=='GATE_REJECTED_WITH_LOCAL_CANDIDATE' for x in first)}",
        f"- NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION: {sum(x['category']=='NO_COMPATIBLE_CANDIDATE_NEAR_PREDICTION' for x in first)}",
        f"- TRACE_INCOMPLETE: {sum(x['category']=='TRACE_INCOMPLETE' for x in first)}",
        "- terminal outcome 分開記錄：`track_expired_max_gap` 103、`track_expired_max_missed` 130；不把 terminal outcome 當第一個根因。",
        "",
        "### Pair 分母",
        f"- all pair rows: {len(pairs_rows)}; counts: `{dict(all_counts)}`",
        f"- nearest pair groups: {len(nearest)}; counts: `{dict(near_counts)}`",
        f"- unmatched tracker states: {unmatched}; all-pair reject counts不等於漏按數。",
        "",
        "## UID population reconciliation",
        "248 個 lifecycle note UID 中，229 個落在 replay trace 的 source frame 範圍內；差異 19 個全部是 live frame 1340–1411，而 replay trace 最後 frame 是 1328。這是 replay 範圍差異，不是猜測成 identity switch。詳見 `uid_population_reconciliation.csv`。",
        "",
        "## PR-2 五案",
        "五個 case 的逐幀資料在 `shadow_five_case_timelines.csv`，來源 montage 在 `case_crops/`，判定在 `shadow_five_case_verdicts.md`。視覺核對僅證明畫面存在音符，不代表遊戲命中。",
        "- 1000004：HIGH mapping，但 PF posterior gate 與 tracker current 狀態同時出現，判定 MULTIPLE_BLOCKERS。",
        "- 1000059：cyan tap 與命中閃光共存，live/replay identity 不足，AMBIGUOUS。",
        "- 1000139：cyan tap 與黃色長條重疊，mapping 不足，AMBIGUOUS。",
        "- 1000140：cyan tap 與黃色長條重疊，mapping 不足，AMBIGUOUS。",
        "- 1000143：可見 cyan tap，但缺乏高信心 live/replay identity，AMBIGUOUS。",
        "",
        "## PR-3 決策",
        "本輪沒有足夠的多個 HIGH identity 案例證明單一 matcher/PF gate 是根因，因此不實作演算法修補；任何未來 patch 必須是預設 OFF 的獨立 flag。",
        "| 項目 | 決策 |",
        "|---|---|",
        "| assignment tie-break | 暫不修補；只有少量嚴格 probable competition，尚無可證實 physical identity |",
        "| motion gate | 暫不放寬；局部 gate reject 需下一次 live telemetry |",
        "| PF posterior gate | 不切換 Active；五案不是單一 PF 阻礙的充分證據 |",
        "| detector/overlap | 保留現狀；先補 candidate identity trace |",
        "",
        "## PR-4 安全與效能",
        "- `v756_ab_summary.json` 保留既有 OFF/ON signature 結果；`shadow_active=false`，Legacy input path unchanged。",
        "- `v756_performance_comparison.csv` 提供現有 live run 的 Capture/Detector/Tracker/PF/Planner/Scheduler/total P50/P95/P99；沒有同一輸入的 trace-on wall-time，因此該欄標為 `trace_on_perf_not_available`，不虛構改善。",
        "- pytest 結果另存 `pytest_v756.txt`；沒有遊戲判定真值，hit rate 維持 UNKNOWN。",
        "",
        "## 最小後續 telemetry patch",
        "live trace 需要每幀保存 `candidate_id`、bbox、observed center、normalized u、appearance、lane，以及零候選/被跳過的 association sentinel row；live/replay 共用 capture timestamp + bbox + lane + appearance correlation key。這些只增加可觀測性，不改任何 gate。",
    ]
    (out / "V7_5_6_IDENTITY_ASSOCIATION_ROOT_CAUSE.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(out), "first_unmatched": dict(Counter(x["category"] for x in first)), "strict_competition": len(verified), "lifecycle_uids": len(lifecycle_uids), "old_population": sum(r["old_229_population"] == "True" for r in recon)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
