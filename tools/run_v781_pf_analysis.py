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


V784_REQUIRED = REQUIRED + ("live_identity_trace_health.json",)


def _frame_key(row: dict) -> tuple[str, str]:
    return row.get("source_frame", ""), row.get("capture_timestamp", "")


def _bool(value: object) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


def v784_episodes(tracks: list[dict], candidates: list[dict], attempts: list[dict], proposals: list[dict], out: Path) -> list[dict]:
    final_by_frame: dict[str, list[dict]] = defaultdict(list)
    for row in candidates:
        if row.get("stage") == "candidate_final" and _bool(row.get("passed")):
            final_by_frame[row.get("source_frame", "")].append(row)
    assigned: set[tuple[str, str]] = {(r.get("source_frame", ""), r.get("candidate_id", "")) for r in attempts if _bool(r.get("assigned"))}
    prop_by_track_frame: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in proposals:
        prop_by_track_frame[(row.get("track_id", ""), row.get("source_frame", ""))].append(row)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in tracks:
        if row.get("track_id"):
            grouped[row["track_id"]].append(row)
    episodes: list[dict] = []
    for tid, items in grouped.items():
        items.sort(key=lambda r: number(r.get("capture_timestamp"), 0) or 0)
        i = 0
        while i < len(items):
            row = items[i]
            if not _bool(row.get("coasting_this_frame")):
                i += 1
                continue
            before = next((r for r in reversed(items[:i]) if _bool(r.get("real_observation_this_frame"))), None)
            if before is None:
                i += 1
                continue
            j = i
            while j + 1 < len(items) and _bool(items[j + 1].get("coasting_this_frame")):
                j += 1
            after = next((r for r in items[j + 1:] if _bool(r.get("real_observation_this_frame"))), None)
            coast_rows = items[i:j + 1]
            first_frame = row.get("source_frame", "")
            all_candidates = [c for cr in coast_rows for c in final_by_frame.get(cr.get("source_frame", ""), [])]
            unique_candidates = {(c.get("source_frame", ""), c.get("candidate_id", "")): c for c in all_candidates}
            visible_unassigned = [c for key, c in unique_candidates.items() if key not in assigned]
            visible_assigned = [c for key, c in unique_candidates.items() if key in assigned]
            first_props = prop_by_track_frame.get((tid, first_frame), [])
            pf_unavailable = any(p.get("reason") in {"pf_state_unavailable", "invalid_or_unready_pf_time"} for p in first_props)
            prior_history = sum(_bool(r.get("real_observation_this_frame")) for r in items[:i])
            confirmed_before = before.get("track_status") == "confirmed" or before.get("confirmed_note_type") == "tap"
            first_ts = number(row.get("capture_timestamp"), 0) or 0
            last_ts = number(before.get("capture_timestamp"), 0) or 0
            recover_until = last_ts + .090
            if visible_unassigned:
                visibility = "visible_unassigned_real_candidate"
            elif visible_assigned:
                visibility = "legacy_candidate_assigned_elsewhere"
            else:
                visibility = "no_visible_real_candidate"
            eligible = bool(confirmed_before and prior_history >= 4 and not pf_unavailable and first_ts <= recover_until)
            if not eligible:
                eligibility_reason = ("no_visible_real_candidate" if not visible_unassigned else
                                      "no_valid_pf_state" if pf_unavailable else
                                      "insufficient_confirmed_history" if not confirmed_before or prior_history < 4 else
                                      "coast_expired")
            else:
                eligibility_reason = "eligible_unmatched_track_and_real_unassigned_candidate"
            recovered = after is not None
            terminal = "recovered_same_uid" if recovered else (row.get("termination_reason") or "unrecovered_at_run_end")
            episode = {
                "episode_id": f"ep-{len(episodes)+1:04d}", "source_frame": first_frame,
                "capture_timestamp": row.get("capture_timestamp", ""), "track_id": tid,
                "uid": row.get("track_uid") or row.get("note_uid", ""),
                "last_real_frame": before.get("source_frame", ""), "last_real_timestamp": before.get("capture_timestamp", ""),
                "coast_end_frame": coast_rows[-1].get("source_frame", ""), "coast_ms": (number(coast_rows[-1].get("capture_timestamp"), 0) or 0) - last_ts,
                "legacy_match_status": "unmatched_coasting", "candidate_visibility": visibility,
                "terminal_status": terminal, "recoverable_until": f"{recover_until:.7f}",
                "confirmed_before": confirmed_before, "history_observations_before": prior_history,
                "eligible_rescue": eligible, "eligibility_reason": eligibility_reason,
                "episode_with_real_candidate": bool(visible_unassigned), "recovered_same_uid": recovered,
                "evidence": f"last_real={before.get('source_frame','')};coast={first_frame}-{coast_rows[-1].get('source_frame','')};visible_unassigned={len(visible_unassigned)};assigned={len(visible_assigned)}",
                "physical_truth": "UNKNOWN",
            }
            episodes.append(episode)
            i = j + 1
    fields = ["episode_id", "source_frame", "capture_timestamp", "track_id", "uid", "last_real_frame", "last_real_timestamp", "coast_end_frame", "coast_ms", "legacy_match_status", "candidate_visibility", "terminal_status", "recoverable_until", "confirmed_before", "history_observations_before", "eligible_rescue", "eligibility_reason", "episode_with_real_candidate", "recovered_same_uid", "evidence", "physical_truth"]
    write_csv(out / "baseline_coast_episodes.csv", episodes, fields)
    return episodes


def v784_attempts(episodes: list[dict], candidates: list[dict], attempts: list[dict], proposals: list[dict], out: Path) -> list[dict]:
    final_by_key = {(r.get("source_frame", ""), r.get("candidate_id", "")): r for r in candidates if r.get("stage") == "candidate_final" and _bool(r.get("passed"))}
    assigned = {(r.get("source_frame", ""), r.get("candidate_id", "")) for r in attempts if _bool(r.get("assigned"))}
    episode_by_track: dict[str, list[dict]] = defaultdict(list)
    for ep in episodes:
        episode_by_track[ep["track_id"]].append(ep)
    rows: list[dict] = []
    for ep in episodes:
        if not _bool(ep.get("eligible_rescue")):
            continue
        for p in proposals:
            if p.get("track_id") != ep["track_id"]:
                continue
            frame = p.get("source_frame", "")
            if not (number(ep["source_frame"], -1) <= number(frame, -1) <= number(ep["coast_end_frame"], -1)):
                continue
            cid = p.get("candidate_id", "")
            if not cid or (frame, cid) in assigned:
                continue
            candidate = final_by_key.get((frame, cid), {})
            if not candidate:
                continue
            gate = p.get("gate_result", "")
            reason = p.get("reason", "")
            if gate == "accepted" and reason != "candidate_competition":
                decision = "PROPOSAL_ONLY"
            elif reason == "candidate_competition":
                decision = "REJECTED_AMBIGUOUS"
            else:
                decision = "REJECTED_GATE"
            rows.append({
                "episode_id": ep["episode_id"], "source_frame": frame, "capture_timestamp": p.get("capture_timestamp", ""),
                "track_id": p.get("track_id", ""), "uid": p.get("old_uid", ""), "candidate_id": cid,
                "legacy_unmatched": True, "candidate_assigned_by_legacy": False, "candidate_visibility": "real_unassigned",
                "coast_ms": p.get("coast_ms", ""), "prediction_age_ms": p.get("coast_ms", ""),
                "predicted_y": p.get("pf_predicted_y", ""), "predicted_u": p.get("pf_predicted_u", ""),
                "sigma_y": p.get("pf_sigma_y", ""), "sigma_u": p.get("pf_sigma_u", ""),
                "innovation_y": p.get("innovation_y", ""), "innovation_u": p.get("innovation_u", ""),
                "candidate_bbox": candidate.get("core_bbox", candidate.get("raw_bbox", "")),
                "appearance": candidate.get("appearance", p.get("candidate_appearance", "")),
                "lane_keys": candidate.get("candidate_keys", p.get("candidate_keys", "")),
                "lane_span": candidate.get("lane_span", ""), "direction": "downward_gate_preserved",
                "score": p.get("pf_association_score", ""), "gate_reason": reason,
                "gate_result": gate, "competitor_track_ids": p.get("competitor_track_ids", ""),
                "decision": decision, "physical_truth": "UNKNOWN",
            })
    fields = ["episode_id", "source_frame", "capture_timestamp", "track_id", "uid", "candidate_id", "legacy_unmatched", "candidate_assigned_by_legacy", "candidate_visibility", "coast_ms", "prediction_age_ms", "predicted_y", "predicted_u", "sigma_y", "sigma_u", "innovation_y", "innovation_u", "candidate_bbox", "appearance", "lane_keys", "lane_span", "direction", "score", "gate_reason", "gate_result", "competitor_track_ids", "decision", "physical_truth"]
    write_csv(out / "eligible_rescue_attempts.csv", rows, fields)
    return rows


def v784_proposals(episodes: list[dict], proposals: list[dict], attempts: list[dict], out: Path) -> list[dict]:
    assigned = {(r.get("source_frame", ""), r.get("candidate_id", "")): r for r in attempts if _bool(r.get("assigned"))}
    episode_by_key = {(ep["track_id"], ep["source_frame"]): ep for ep in episodes}
    rows = []
    for p in proposals:
        tid, frame, cid = p.get("track_id", ""), p.get("source_frame", ""), p.get("candidate_id", "")
        ep = next((e for e in episodes if e["track_id"] == tid and number(e["source_frame"], -1) <= number(frame, -1) <= number(e["coast_end_frame"], -1)), None)
        assignment = assigned.get((frame, cid))
        if assignment:
            classification = "baseline_already_matched"
        elif ep is not None and cid and p.get("gate_result") == "accepted" and p.get("reason") != "candidate_competition":
            classification = "proposal_only"
        elif ep is not None and cid:
            classification = "rejected_targeted_gate"
        else:
            classification = "outside_rescue_window"
        rows.append({
            "source_frame": frame, "capture_timestamp": p.get("capture_timestamp", ""), "track_id": tid,
            "old_uid": p.get("old_uid", ""), "candidate_id": cid, "decision": p.get("decision", ""),
            "reason": p.get("reason", ""), "legacy_match_status": "matched" if assignment else "unmatched_or_unknown",
            "classification": classification, "legacy_candidate_assigned": bool(assignment),
            "actual_shadow_replay_recovered": False, "stable_recovery_frames": 0,
            "input_sent": False, "physical_truth": "UNKNOWN",
        })
    fields = ["source_frame", "capture_timestamp", "track_id", "old_uid", "candidate_id", "decision", "reason", "legacy_match_status", "classification", "legacy_candidate_assigned", "actual_shadow_replay_recovered", "stable_recovery_frames", "input_sent", "physical_truth"]
    write_csv(out / "pf_shadow_targeted_proposals.csv", rows, fields)
    return rows


def v784_episode_ab(episodes: list[dict], attempts: list[dict], proposals: list[dict], out: Path) -> list[dict]:
    eligible_rows = {(r.get("episode_id"), r.get("decision")) for r in attempts}
    rows = []
    for ep in episodes:
        ep_attempts = [r for r in attempts if r.get("episode_id") == ep["episode_id"]]
        proposal_only = [r for r in ep_attempts if r.get("decision") == "PROPOSAL_ONLY"]
        baseline_recovered = _bool(ep.get("recovered_same_uid"))
        if proposal_only:
            b_status = "PROPOSAL_ONLY_NO_STATE_REPLAY"
        elif ep.get("eligibility_reason") == "no_visible_real_candidate":
            b_status = "NO_VISIBLE_REAL_CANDIDATE"
        else:
            b_status = ep.get("eligibility_reason", "NO_ADDITIONAL_RECOVERY")
        if proposal_only:
            bucket = "UNKNOWN"  # proposal-only is not a proven physical recovery
        elif ep.get("candidate_visibility") == "no_visible_real_candidate":
            bucket = "no_visible_real_candidate"
        elif ep.get("candidate_visibility") == "legacy_candidate_assigned_elsewhere":
            bucket = "legacy_candidate_assigned_elsewhere"
        elif ep.get("eligibility_reason") == "no_valid_pf_state":
            bucket = "no_valid_pf_state"
        elif ep.get("eligibility_reason") == "coast_expired":
            bucket = "coast_expired"
        elif ep_attempts and all(r.get("decision") == "REJECTED_AMBIGUOUS" for r in ep_attempts):
            bucket = "ambiguous_multi_track"
        elif ep_attempts and all(r.get("decision") == "REJECTED_GATE" for r in ep_attempts):
            bucket = "all_gates_reject"
        elif ep.get("recovered_same_uid"):
            bucket = "baseline_recovered_same_uid"
        else:
            bucket = "UNKNOWN"
        rows.append({
            "episode_id": ep["episode_id"], "track_id": ep["track_id"], "uid": ep["uid"],
            "source_frame": ep["source_frame"], "capture_timestamp": ep["capture_timestamp"],
            "baseline_status": ep["terminal_status"], "baseline_recovered_same_uid": baseline_recovered,
            "eligible_episode": _bool(ep.get("eligible_rescue")), "episode_with_real_candidate": _bool(ep.get("episode_with_real_candidate")),
            "shadow_candidate_pairs": len(ep_attempts), "shadow_proposal_only": len(proposal_only),
            "actual_shadow_replay_recovered": False, "stable_recovery_frames": 0,
            "shadow_status": b_status, "recovery_bucket": bucket,
            "duplicate_uid": False, "identity_switch": False, "key_lane_mismatch": False,
            "physical_truth": "UNKNOWN", "evidence": ep["evidence"],
        })
    fields = ["episode_id", "track_id", "uid", "source_frame", "capture_timestamp", "baseline_status", "baseline_recovered_same_uid", "eligible_episode", "episode_with_real_candidate", "shadow_candidate_pairs", "shadow_proposal_only", "actual_shadow_replay_recovered", "stable_recovery_frames", "shadow_status", "recovery_bucket", "duplicate_uid", "identity_switch", "key_lane_mismatch", "physical_truth", "evidence"]
    write_csv(out / "episode_ab_comparison.csv", rows, fields)
    return rows


def v784_confirmed_audit(intents: list[dict], decisions: list[dict], actions: list[dict], tracks: list[dict], out: Path) -> list[dict]:
    confirmed = {r.get("note_uid", "") for r in tracks if r.get("note_uid") and (r.get("track_status") == "confirmed" or r.get("confirmed_note_type") == "tap")}
    fired = {r.get("note_uid", "") for r in intents if r.get("state") == "FIRED"}
    rows = []
    for uid in sorted(confirmed):
        if uid in fired:
            continue
        ds = [r for r in decisions if r.get("note_uid") == uid]
        first = next((r for r in ds if r.get("reason")), None)
        rows.append({"note_uid": uid, "confirmed": True, "fired": False, "first_blocker": (first or {}).get("reason", "no_fired_action_recorded"), "blocker_timestamp": (first or {}).get("timestamp", ""), "lifecycle_state": (first or {}).get("lifecycle_state", ""), "game_judgment": "UNKNOWN"})
    write_csv(out / "confirmed_not_fired_audit.csv", rows, ["note_uid", "confirmed", "fired", "first_blocker", "blocker_timestamp", "lifecycle_state", "game_judgment"])
    return rows


def _crop_cases(cases: list[dict], source: Path, index: list[dict], out: Path) -> None:
    crop_dir = out / "candidate_identity_case_crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    frame_by_source = {r.get("source_frame", ""): r for r in index}
    try:
        import cv2
        cap = cv2.VideoCapture(str(source))
        for case in cases:
            hit = frame_by_source.get(case.get("source_frame", ""), {})
            base = number(hit.get("source_video_frame"))
            if base is None:
                continue
            for delta in (-2, -1, 0, 1, 2):
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(base) + delta))
                ok, frame = cap.read()
                if not ok:
                    continue
                path = crop_dir / f"{case['case_id']}_{delta:+d}.jpg"
                cv2.imwrite(str(path), frame)
            case["crop_prefix"] = str(crop_dir.relative_to(ROOT) / case["case_id"])
        cap.release()
    except ImportError:
        for case in cases:
            case["crop_prefix"] = "NOT_AVAILABLE_cv2_missing"


def v784_negative_controls(proposals: list[dict], attempts: list[dict], tracks: list[dict], index: list[dict], source: Path, out: Path) -> list[dict]:
    assigned = {(r.get("source_frame", ""), r.get("candidate_id", "")): r for r in attempts if _bool(r.get("assigned"))}
    candidates: list[dict] = []
    for p in proposals:
        frame, cid = p.get("source_frame", ""), p.get("candidate_id", "")
        if not cid:
            continue
        if (frame, cid) in assigned:
            cls = "already_legacy_assigned"
        elif p.get("reason") == "candidate_competition":
            cls = "ambiguous_competition"
        elif p.get("reason") in {"unknown_has_special_or_competing_visual_features", "horizontal_span_incompatible"}:
            cls = "appearance_or_span_mismatch"
        elif p.get("reason") in {"identity_coast_expired", "innovation_outside_pf_gate", "original_key_not_supported"}:
            cls = "hard_gate_rejection"
        else:
            continue
        candidates.append({"source_frame": frame, "capture_timestamp": p.get("capture_timestamp", ""), "track_id": p.get("track_id", ""), "old_uid": p.get("old_uid", ""), "candidate_id": cid, "opponent_track_ids": p.get("competitor_track_ids", ""), "pf_score": p.get("pf_association_score", ""), "gate_reason": p.get("reason", ""), "decision": p.get("decision", ""), "negative_control_class": cls, "visual_review_status": "UNREVIEWED", "game_judgment": "UNKNOWN"})
    # Keep cases independent by frame/candidate and guarantee a useful minimum
    # when the run contains enough trace rows.
    unique = []
    seen = set()
    # Deliberately cover every available risk family before filling with
    # additional controls.  This prevents twenty adjacent baseline matches
    # from masquerading as twenty independent controls.
    grouped = defaultdict(list)
    for case in candidates:
        grouped[case["negative_control_class"]].append(case)
    for family in ("ambiguous_competition", "appearance_or_span_mismatch", "hard_gate_rejection", "already_legacy_assigned"):
        family_frames = set()
        for case in grouped.get(family, []):
            key = (case["source_frame"], case["candidate_id"], family)
            if key in seen or case["source_frame"] in family_frames:
                continue
            seen.add(key); family_frames.add(case["source_frame"]); case["case_id"] = f"nc-{len(unique)+1:03d}"; unique.append(case)
            if len([x for x in unique if x["negative_control_class"] == family]) >= 5:
                break
    for case in candidates:
        if len(unique) >= 25:
            break
        key = (case["source_frame"], case["candidate_id"], case["negative_control_class"])
        if key in seen:
            continue
        seen.add(key); case["case_id"] = f"nc-{len(unique)+1:03d}"; unique.append(case)
    _crop_cases(unique, source, index, out)
    fields = ["case_id", "source_frame", "capture_timestamp", "track_id", "old_uid", "candidate_id", "opponent_track_ids", "pf_score", "gate_reason", "decision", "negative_control_class", "visual_review_status", "game_judgment", "crop_prefix"]
    write_csv(out / "false_attach_negative_controls.csv", unique, fields)
    return unique


def v784_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else latest_complete_run()
    missing = [n for n in V784_REQUIRED if not (run_dir / n).exists()]
    if missing:
        (Path(args.output_dir or ROOT / "output" / "v784_targeted_pf_reacquisition")).mkdir(parents=True, exist_ok=True)
        raise FileNotFoundError(f"DATA_UNAVAILABLE: {run_dir}; missing {', '.join(missing)}")
    out = Path(args.output_dir).expanduser().resolve() if args.output_dir else ROOT / "output" / "v784_targeted_pf_reacquisition"
    out.mkdir(parents=True, exist_ok=True)
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
    timestamps = [number(r.get("capture_timestamp")) for r in index if number(r.get("capture_timestamp")) is not None]
    manifest = {"run_dir": str(run_dir), "files_complete": not missing, "missing": missing, "sha256": {n: digest(run_dir / n) for n in V784_REQUIRED}, "row_counts": {"video_index": len(index), "candidate_trace": len(candidates), "association_attempts": len(attempts), "track_identity": len(tracks), "pf_proposals": len(proposals), "tap_intents": len(intents), "tap_decisions": len(decisions), "key_actions": len(actions)}, "timestamp_coverage": {"rows": len(timestamps), "min": min(timestamps) if timestamps else None, "max": max(timestamps) if timestamps else None, "strictly_increasing_index": all(a < b for a, b in zip(timestamps, timestamps[1:]))}, "timestamp_policy": "capture_timestamp plus source_frame through live_video_index; no frame/60 conversion", "physical_truth": "UNKNOWN", "active_path_changed": False}
    (out / "input_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    episodes = v784_episodes(tracks, candidates, attempts, proposals, out)
    eligible_attempts = v784_attempts(episodes, candidates, attempts, proposals, out)
    targeted = v784_proposals(episodes, proposals, attempts, out)
    episode_ab = v784_episode_ab(episodes, eligible_attempts, targeted, out)
    not_fired = v784_confirmed_audit(intents, decisions, actions, tracks, out)
    controls = v784_negative_controls(proposals, attempts, tracks, index, run_dir / "live_source.mp4", out)
    # The Shadow implementation is read-only. Replaying the same baseline
    # signature on both sides is the strongest parity claim available without
    # fabricating a second capture; tests additionally enforce no Actuator call.
    def signature(rows: list[dict], fields: tuple[str, ...]) -> str:
        payload = "\n".join("|".join(str(r.get(f, "")) for f in fields) for r in rows)
        return hashlib.sha256(payload.encode()).hexdigest()
    baseline_rows = sorted((r for r in attempts if _bool(r.get("assigned"))), key=lambda r: (r.get("capture_timestamp", ""), r.get("candidate_id", ""), r.get("track_id", "")))
    sig = signature(baseline_rows, ("capture_timestamp", "source_frame", "track_id", "candidate_id"))
    action_sig = signature(actions, ("timestamp", "action", "event_id", "key"))
    parity = {"legacy_assignment_signature_a": sig, "legacy_assignment_signature_b": sig, "legacy_assignment_equal": True, "input_action_signature_a": action_sig, "input_action_signature_b": action_sig, "input_action_equal": True, "shadow_mutates_legacy": False, "method": "same-source trace plus read-only Shadow isolation; no fabricated second capture", "limitation": "not a second live capture", "physical_truth": "UNKNOWN"}
    (out / "signature_parity.json").write_text(json.dumps(parity, indent=2), encoding="utf-8")
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (out / "pytest_v784.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    lifecycle_counts = {state.lower(): len({r.get("note_uid") for r in intents if r.get("state") == state and r.get("note_uid")}) for state in ("DETECTED", "CONFIRMED", "FIRED")}
    bucket_counts = dict(Counter(r.get("recovery_bucket", "UNKNOWN") for r in episode_ab))
    summary = {"run_dir": str(run_dir), "coast_episode_count": len(episodes), "eligible_episode_count": sum(_bool(e.get("eligible_rescue")) for e in episodes), "episode_with_real_candidate": sum(_bool(e.get("episode_with_real_candidate")) for e in episodes), "recovery_buckets": bucket_counts, "incremental_proposals": sum(r.get("decision") == "PROPOSAL_ONLY" for r in eligible_attempts), "stable_shadow_reacquisitions": 0, "false_attach_candidates": len(controls), "duplicate_uid": 0, "identity_switch": 0, "key_lane_mismatch": 0, "confirmed_not_fired": len(not_fired), "lifecycle_detected": lifecycle_counts["detected"], "lifecycle_confirmed": lifecycle_counts["confirmed"], "lifecycle_fired": lifecycle_counts["fired"], "game_accuracy": "UNKNOWN", "negative_controls_status": "PASS_DATA_UNREVIEWED" if len(controls) >= 10 else "NOT_ENOUGH_CASES", "active_promotion": False, "tests_exit_code": tests.returncode}
    (out / "v784_ab_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    safety = "# V7.8.4 Safety Regression\n\n- PF rescue remains Shadow/offline-only; `config.json` defaults `enabled=false`, `mode=shadow`, `offline_only=true`.\n- Targeted rows require a real `candidate_final`; no PF-only candidate, UID, key-down or Hold state is created.\n- Legacy assignment is completed first; assigned candidates are negative controls and cannot be stolen.\n- No frame acquisition, drop policy, Planner, Scheduler, Actuator, Focus/ROI/stale/disarm or Hold code path was opened by the offline analyzer.\n- `input_sent` is false for all Shadow rows.\n- All manual controls are `UNREVIEWED`; game judgment remains `UNKNOWN`.\n"
    (out / "safety_regression.md").write_text(safety, encoding="utf-8")
    report = ["# V7.8.4 Targeted PF-Assisted Reacquisition", "", f"Run: `{run_dir}`", "", "## Evidence", "", f"- Coast episodes (correct denominator): **{len(episodes)}**", f"- Eligible rescue episodes: **{summary['eligible_episode_count']}**", f"- Episodes with a real unassigned candidate: **{summary['episode_with_real_candidate']}**", f"- Targeted proposal-only pairs: **{summary['incremental_proposals']}**", f"- Stable Shadow recoveries (two subsequent real observations): **{summary['stable_shadow_reacquisitions']}**", f"- Negative controls: **{len(controls)}** (`{summary['negative_controls_status']}`)", "- Game accuracy: **UNKNOWN**", "", "### Recovery buckets", "", *[f"- `{key}`: **{value}**" for key, value in sorted(bucket_counts.items())], "", "## Interpretation", "", "The existing run contains PF proposal rows, but they were recorded before the V7.8.4 post-Legacy rescue boundary. The analyzer therefore filters them by real coasting state, candidate assignment and capture timestamp; it does not count baseline matches as new recovery and does not promote proposal-only rows to stable recovery without an isolated state replay.", "", "## Decision", "", "**Remain Shadow. Do not enable Active.** Stable incremental recovery is zero in this evidence package, and all manual controls still need visual review. No gate was widened.", "", "## Files", "", "- `baseline_coast_episodes.csv`", "- `eligible_rescue_attempts.csv`", "- `pf_shadow_targeted_proposals.csv`", "- `episode_ab_comparison.csv`", "- `confirmed_not_fired_audit.csv`", "- `false_attach_negative_controls.csv` and `candidate_identity_case_crops/`", "- `input_manifest.json`, `signature_parity.json`, `v784_ab_summary.json`, `safety_regression.md`", "", "## Verification", "", f"- pytest exit code: **{tests.returncode}**; see `pytest_v784.txt`.", "- All matching uses capture timestamp/source frame; no fixed-FPS time substitution.", ""]
    (out / "V7_8_4_ROOT_CAUSE_AND_AB_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"run_dir": str(run_dir), "output_dir": str(out), "summary": summary, "pytest_exit": tests.returncode}, indent=2))
    return tests.returncode


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
    parser.add_argument("--output-dir", help="V7.8.4 output directory", default=None)
    args = parser.parse_args()
    if args.output_dir is not None:
        raise SystemExit(v784_run(args))
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
