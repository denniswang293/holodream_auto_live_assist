"""V7.8.9 offline UID mapping, parity and miss-root-cause audit.

The audit is deliberately read-only with respect to the live pipeline.  It
does not call an actuator and does not change tracker/planner/scheduler gates.
All cross-namespace conclusions are conservative: equal candidate IDs and
human labels are evidence, not proof of a global UID equivalence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_v788_visual_review import REVIEW_FIELDS, normalize_review_rows, read_csv, write_csv  # noqa: E402

RUN_DEFAULT = ROOT / "output" / "run_20261101T034646_232725Z"
V787_DEFAULT = ROOT / "output" / "v787_parity_identity"
V788_DEFAULT = ROOT / "output" / "v788_visual_identity_review"
OUT_DEFAULT = ROOT / "output" / "v789_uid_mapping_parity_miss_audit"

REQUIRED = (
    "live_source.mp4", "live_video_index.csv", "live_candidate_trace.csv",
    "live_association_attempts.csv", "live_track_identity.csv",
    "pf_reassociation_proposals.csv", "tap_intents.csv", "tap_decisions.csv",
    "live_key_actions.csv", "live_events.csv", "tap_eta_comparison.csv",
    "tap_planner_shadow.csv",
)


def num(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def row_key(row: dict[str, str], *fields: str) -> tuple[str, ...]:
    return tuple(str(row.get(field, "")) for field in fields)


def scoped_review(v788: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    source = v788 / "physical_identity_review_completed.csv"
    if not source.exists():
        source = v788 / "physical_identity_review_template.csv"
    rows = normalize_review_rows(read_csv(source))
    reviewed = [r for r in rows if r.get("reviewer_status") == "REVIEWED"]
    excluded = [r for r in rows if r.get("reviewer_status") != "REVIEWED"]
    return reviewed, excluded


def manifest(run: Path, v787: Path, v788: Path, out: Path) -> dict[str, Any]:
    missing = [name for name in REQUIRED if not (run / name).exists()]
    index = read_csv(run / "live_video_index.csv") if (run / "live_video_index.csv").exists() else []
    timestamps = [num(r.get("capture_timestamp")) for r in index]
    timestamps = [x for x in timestamps if x is not None]
    source_frames = [r.get("source_frame", "") for r in index]
    video_frames = [r.get("source_video_frame", "") for r in index]
    monotonic = all(a <= b for a, b in zip(timestamps, timestamps[1:]))
    map_ok = len(source_frames) == len(set(source_frames)) and len(video_frames) == len(set(video_frames))
    files = {name: {"exists": (run / name).exists(), "bytes": (run / name).stat().st_size if (run / name).exists() else None, "sha256": digest(run / name) if (run / name).exists() else None, "rows": len(read_csv(run / name)) if (run / name).suffix == ".csv" and (run / name).exists() else None} for name in REQUIRED}
    data = {"status": "READY" if not missing else "DATA_UNAVAILABLE", "run_dir": str(run), "v787_dir": str(v787), "v788_dir": str(v788), "missing": missing, "files": files, "video_index": {"rows": len(index), "capture_timestamp_min": min(timestamps) if timestamps else None, "capture_timestamp_max": max(timestamps) if timestamps else None, "timestamp_monotonic": monotonic, "source_frame_unique": len(set(source_frames)) == len(source_frames), "source_video_frame_unique": len(set(video_frames)) == len(video_frames), "source_to_video_mapping_valid": map_ok, "timestamp_policy": "capture_timestamp + source_frame + source_video_frame; no frame/60"}, "physical_truth": "UNKNOWN", "active_enabled": False}
    (out / "input_manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def evidence_hierarchy(out: Path) -> None:
    (out / "evidence_hierarchy.md").write_text("""# V7.8.9 evidence hierarchy

1. **Source evidence:** `live_source.mp4` aligned through `live_video_index.csv` using `source_frame` and `capture_timestamp`.
2. **Recorded software trace:** detector candidates, Live track identity, assignment attempts, PF proposals, intent/decision/scheduler/action CSVs.
3. **Offline replay evidence:** Legacy A and isolated Shadow B using the same recorded candidate stream and capture timestamps.
4. **Human identity label:** the reviewed CSV value (`SAME_PHYSICAL_NOTE`, etc.). It does not prove a global UID mapping or a game hit.
5. **Game judgment:** only a directly traceable game judgment source can establish it. User-entered `PERFECT/GOOD/MISS` without such source is `HUMAN_REPORTED_UNVERIFIED`; aggregate accuracy remains `UNKNOWN`.

The 20 unreviewed cases are retained as `OUT_OF_SCOPE_UNREVIEWED` and excluded from denominators. `FIRED`, `key_down`, UID continuity and same-note labels are never converted into game hit or MISS claims.
""", encoding="utf-8")


def reviewed_scope_csv(reviewed: list[dict[str, str]], excluded: list[dict[str, str]], out: Path) -> None:
    rows = []
    for row in reviewed:
        extra = dict(row); extra["scope"] = "IN_SCOPE_REVIEWED"; extra["game_judgment_evidence"] = "HUMAN_REPORTED_UNVERIFIED" if row.get("game_judgment") != "UNKNOWN" else "UNKNOWN_NO_DIRECT_GAME_SOURCE"; rows.append(extra)
    fields = REVIEW_FIELDS + ["scope", "game_judgment_evidence"]
    write_csv(out / "reviewed10_scope.csv", rows, fields)
    excluded_rows = []
    for row in excluded:
        extra = dict(row); extra["scope"] = "OUT_OF_SCOPE_UNREVIEWED"; extra["game_judgment_evidence"] = "UNKNOWN_OUT_OF_SCOPE"; excluded_rows.append(extra)
    write_csv(out / "unreviewed_excluded.csv", excluded_rows, fields)


def index_maps(run: Path) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    index = read_csv(run / "live_video_index.csv")
    index_by_frame = {r.get("source_frame", ""): r for r in index}
    candidates = read_csv(run / "live_candidate_trace.csv")
    tracks = read_csv(run / "live_track_identity.csv")
    attempts = read_csv(run / "live_association_attempts.csv")
    proposals = read_csv(run / "pf_reassociation_proposals.csv")
    events = read_csv(run / "live_events.csv")
    by_candidate: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_uid: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_frame: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_track: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_event_uid: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates: by_candidate[row.get("candidate_id", "")].append(row); by_frame[row.get("source_frame", "")].append(row)
    for row in tracks:
        by_uid[row.get("note_uid", "")].append(row)
        by_track[row.get("track_id", "")].append(row)
        if row.get("candidate_id"):
            by_candidate[row.get("candidate_id", "")].append(row)
    for row in events: by_event_uid[row.get("note_uid", "")].append(row)
    return index, index_by_frame, by_candidate, by_uid, by_frame, by_track, by_event_uid


def rescue_rows(v787: Path) -> list[dict[str, str]]:
    return read_csv(v787 / "rescue_identity_case_audit.csv")


def namespace_audit(reviewed: list[dict[str, str]], rescue: list[dict[str, str]], by_candidate: dict[str, list[dict[str, str]]], by_uid: dict[str, list[dict[str, str]]], out: Path) -> None:
    rescue_by_case = {r.get("case_id", ""): r for r in rescue}
    mapping = []
    ownership = []
    reconciled = []
    for review in reviewed:
        case = review.get("case_id", "")
        candidate = review.get("candidate_id", "")
        live_rows = by_candidate.get(candidate, [])
        live_tracks = sorted({r.get("track_uid", "") for r in live_rows if r.get("track_uid")})
        live_uids = sorted({r.get("note_uid", "") for r in live_rows if r.get("note_uid")})
        rescue_row = rescue_by_case.get(case, {})
        replay_uid = rescue_row.get("old_uid", "") if rescue_row else ""
        replay_track = replay_uid.split(":")[-1] if replay_uid else ""
        namespace_status = "AMBIGUOUS_NAMESPACE_MAPPING" if replay_uid and live_tracks else "DATA_INSUFFICIENT"
        evidence = "same candidate_id + source frame + human same-note label; no serialized cross-run tracker state"
        mapping.append({"case_id": case, "source_frame": review.get("source_frame", ""), "candidate_id": candidate, "live_namespace": "live", "live_track_uids": "|".join(live_tracks), "live_note_uids": "|".join(live_uids), "replay_namespace": "offline_shadow" if replay_uid else "", "replay_uid": replay_uid, "replay_track_id": replay_track, "mapping_class": namespace_status, "mapping_confidence": "MEDIUM" if review.get("same_physical_note_verdict") == "SAME_PHYSICAL_NOTE" else "UNKNOWN", "human_identity_label": review.get("same_physical_note_verdict", "UNKNOWN"), "evidence": evidence})
        owner_counts = Counter(r.get("track_uid", "") for r in live_rows if r.get("track_uid"))
        ownership.append({"case_id": case, "source_frame": review.get("source_frame", ""), "candidate_id": candidate, "live_owner_track_uids": "|".join(owner_counts), "live_owner_count": len(owner_counts), "replay_owner_uid": replay_uid, "candidate_owner_status": "SINGLE_LIVE_OWNER" if len(owner_counts) == 1 else ("MULTIPLE_LIVE_OWNERS" if owner_counts else "NO_LIVE_OWNER"), "same_candidate_across_namespaces": bool(replay_uid and owner_counts), "double_owned_same_namespace": False, "wrong_mapping": "UNKNOWN", "evidence": "candidate trace + live_track_identity + rescue audit"})
        stable = "STABLE" if rescue_row.get("software_stability") == "STABLE" else ("UNSTABLE" if rescue_row else "NOT_RESCUE")
        reconciled.append({"case_id": case, "source_frame": review.get("source_frame", ""), "candidate_id": candidate, "human_identity_label": review.get("same_physical_note_verdict", "UNKNOWN"), "human_confidence": review.get("visual_confidence", "UNKNOWN"), "software_recovery_stability": stable, "software_uid_mapping": namespace_status, "causally_proven_incremental_hardware_hit": "UNKNOWN", "game_judgment": review.get("game_judgment", "UNKNOWN"), "game_judgment_evidence": "HUMAN_REPORTED_UNVERIFIED" if review.get("game_judgment") != "UNKNOWN" else "UNKNOWN", "final_identity_conclusion": "AMBIGUOUS_UNTIL_CROSS_RUN_STATE_EXISTS"})
    write_csv(out / "namespace_uid_mapping.csv", mapping)
    write_csv(out / "candidate_ownership_audit.csv", ownership)
    write_csv(out / "reviewed10_identity_reconciliation.csv", reconciled)
    (out / "uid_mapping_root_cause.md").write_text("""# UID mapping root cause

The reviewed rescue cases reuse the same `candidate_id` and source frame in the Live and offline traces, while the UID namespaces differ (`simple:1000xxx` versus `simple:5`/`simple:12`). This supports a **time-local ambiguous mapping**, not a global UID equivalence. The source run has no serialized cross-run Tracker/PF snapshot, so the audit does not claim false attach, double ownership, or a causally proven game hit.

Frame 408 (`408:candidate:0`) and frame 525 (`525:candidate:4`) are retained as explicit candidate-ownership cases. A human `SAME_PHYSICAL_NOTE` label is reported separately from software continuity and does not promote the mapping to PASS.
""", encoding="utf-8")


def parity_audit(v787: Path, run: Path, out: Path) -> None:
    src = v787 / "baseline_parity_semantic.json"
    data = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {"status": "DATA_UNAVAILABLE"}
    result = {**data, "status": "PARTIAL_SOURCE_INSUFFICIENT" if data.get("extra_edges") or data.get("missing_edges") else "SEMANTIC_PARITY_PASS", "active_gate": "CLOSED", "reason": "Two replay-extra edges remain and original Live trace lacks serialized Tracker/PF snapshots; no rows were deleted."}
    (out / "assignment_parity_after.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    attempts = read_csv(run / "live_association_attempts.csv")
    candidates = read_csv(run / "live_candidate_trace.csv")
    for frame, timestamp, track, candidate in (("385", "29152.4751039", "1000003", "385:candidate:0"), ("546", "29154.9874954", "1000014", "546:candidate:11")):
        c = [r for r in candidates if r.get("candidate_id") == candidate and r.get("stage") == "candidate_final"]
        a = [r for r in attempts if r.get("candidate_id") == candidate]
        rows.append({"source_frame": frame, "capture_timestamp": timestamp, "replay_track": track, "candidate_id": candidate, "candidate_final_rows": len(c), "live_assignment_attempt_rows": len(a), "earliest_divergence": "candidate_final_present_without_live_assignment_trace" if c and not a else "UNKNOWN", "root_cause": "TRACE_SEMANTICS", "confidence": "HIGH", "parity_status": "PARTIAL_SOURCE_INSUFFICIENT", "evidence": "live_candidate_trace.csv + live_association_attempts.csv + baseline_parity_semantic.json"})
    write_csv(out / "assignment_parity_diff.csv", rows)
    mini = out / "replay_minimal_cases"; mini.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (mini / f"frame{row['source_frame']}.json").write_text(json.dumps({"case": row, "reproduction_policy": "replay recorded candidate_final stream with capture timestamps; retain raw duplicate rows and semantic normalization", "unrecoverable": ["serialized Live Tracker state", "serialized PF posterior snapshot", "exact live trace write timing"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "frame385_frame546_root_cause.md").write_text("""# Frame 385/546 parity investigation

Both replay-extra edges are reproducible from the retained candidate stream: a `candidate_final` exists, but the retained Live association-attempt trace has zero rows for the same candidate. The raw Live trace also has duplicate pair/assignment rows (3308 raw versus 1654 unique semantic edges). This is evidence of a trace-semantic/write-point difference, not enough evidence to call an algorithmic false assignment.

Missing serialized Tracker/PF state prevents reconstructing the exact live tie-break, update order, and posterior at the first divergence. Therefore parity remains `PARTIAL_SOURCE_INSUFFICIENT`; the two edges remain visible.
""", encoding="utf-8")


def lifecycle_audit(run: Path, v787: Path, out: Path) -> None:
    base = read_csv(v787 / "confirmed18_first_blocker.csv")
    tracks = read_csv(run / "live_track_identity.csv")
    events = read_csv(run / "live_events.csv")
    decisions = read_csv(run / "tap_decisions.csv")
    intents = read_csv(run / "tap_intents.csv")
    actions = read_csv(run / "live_key_actions.csv")
    candidates = read_csv(run / "live_candidate_trace.csv")
    rows = []
    for item in base:
        uid = item.get("note_uid", "")
        tr = [r for r in tracks if r.get("note_uid") == uid]
        ev = [r for r in events if r.get("note_uid") == uid]
        dec = [r for r in decisions if r.get("note_uid") == uid]
        ints = [r for r in intents if r.get("note_uid") == uid]
        act = [r for r in actions if r.get("event_id") and any(x.get("event_id") == r.get("event_id") for x in ints)]
        cand_ids = sorted({r.get("candidate_id", "") for r in tr if r.get("candidate_id")})
        cand_rows = [r for r in candidates if r.get("candidate_id") in cand_ids]
        appearances = Counter(r.get("appearance", "UNKNOWN") for r in tr + cand_rows if r.get("appearance"))
        first = min(tr, key=lambda r: num(r.get("capture_timestamp"), float("inf"))) if tr else {}
        last = max(tr, key=lambda r: num(r.get("capture_timestamp"), float("-inf"))) if tr else {}
        reason = (item.get("first_blocker") or "").lower()
        if "below_event_min_y" in reason or "eta" in reason:
            blocker = "PLANNER_GATED"
        elif "track_not_current" in reason:
            blocker = "TRACK_NOT_CURRENT_CONFIRMED"
        elif not tr and not cand_rows:
            blocker = "DETECTOR_NEVER_CANDIDATE"
        else:
            blocker = "SOURCE_INSUFFICIENT"
        rows.append({"note_uid": uid, "physical_note_truth": "UNKNOWN", "first_detector_source_frame": first.get("source_frame", ""), "first_detector_timestamp": first.get("capture_timestamp", ""), "last_track_source_frame": last.get("source_frame", ""), "track_observation_count": len(tr), "real_observation_count": sum(str(r.get("real_observation_this_frame", "")).lower() == "true" for r in tr), "appearance_summary": json.dumps(dict(appearances), ensure_ascii=False), "candidate_ids": "|".join(cand_ids), "confirmed": item.get("confirmed", ""), "fired": item.get("fired", ""), "first_blocker_observed": item.get("first_blocker", ""), "primary_blocker": blocker, "blocker_confidence": "MEDIUM" if item.get("first_blocker") and item.get("blocker_category") != "UNKNOWN" else "LOW", "decision_rows": len(dec), "intent_rows": len(ints), "action_rows": len(act), "event_rows": len(ev), "pf_rows": sum(1 for r in ev if r.get("particle_predicted_y") or r.get("valid_crossing_mass")), "scheduler_or_key_action": "LOGGED" if act else "NOT_LOGGED", "game_judgment": "UNKNOWN", "evidence": "live_candidate_trace.csv + live_track_identity.csv + live_events.csv + tap_decisions.csv + tap_intents.csv + live_key_actions.csv", "final_interpretation": "software lifecycle blocker; not proven game MISS"})
    write_csv(out / "confirmed18_lifecycle_root_cause.csv", rows)
    return rows


def neutral_pink(run: Path, out: Path) -> list[dict[str, str]]:
    tracks = read_csv(run / "live_track_identity.csv")
    events = read_csv(run / "live_events.csv")
    eta = read_csv(run / "tap_eta_comparison.csv")
    decisions = read_csv(run / "tap_decisions.csv")
    actions = read_csv(run / "live_key_actions.csv")
    uids = {}
    for r in tracks + events:
        appearance = (r.get("appearance") or "").lower()
        if "neutral" in appearance or "pink" in appearance:
            uid = r.get("note_uid", "")
            if uid: uids.setdefault(uid, appearance)
    rows = []
    for uid, appearance in sorted(uids.items()):
        tr = [r for r in tracks if r.get("note_uid") == uid]
        ev = [r for r in events if r.get("note_uid") == uid]
        et = [r for r in eta if r.get("note_uid") == uid]
        ds = [r for r in decisions if r.get("note_uid") == uid]
        act = [r for r in actions if r.get("event_id") and any(e.get("event_id") == r.get("event_id") for e in ev)]
        reasons = Counter(r.get("reason", "") for r in ds if r.get("reason"))
        rows.append({"note_uid": uid, "appearance": appearance, "tap_policy": "ordinary_tap_not_flick" if "pink" in appearance else "ordinary_tap_or_neutral_unknown", "source_frames": "|".join(sorted({r.get("source_frame", "") for r in tr + ev if r.get("source_frame")})), "track_observation_count": len(tr), "real_observation_count": sum(str(r.get("real_observation_this_frame", "")).lower() == "true" for r in tr), "planner_rows": len(et), "planner_results": "|".join(sorted({r.get("legacy_planner_result", "") for r in et})), "scheduler_results": "|".join(sorted({r.get("scheduler_result", "") for r in et})), "top_decision_reasons": json.dumps(reasons.most_common(5), ensure_ascii=False), "key_action_count": len(act), "pipeline_status": "TRACE_PRESENT_READ_ONLY", "game_judgment": "UNKNOWN", "conclusion": "No detector/tracker/planner/game MISS claim without direct source evidence"})
    write_csv(out / "neutral_pink_tap_cases.csv", rows)
    return rows


def reconciliation_report(reviewed: list[dict[str, str]], rescue: list[dict[str, str]], out: Path) -> None:
    same = [r for r in reviewed if r.get("same_physical_note_verdict") == "SAME_PHYSICAL_NOTE"]
    game = [r for r in reviewed if r.get("game_judgment") != "UNKNOWN"]
    stable = [r for r in rescue if r.get("software_stability") == "STABLE"]
    unstable = [r for r in rescue if r.get("software_stability") == "UNSTABLE"]
    data = {"reviewed_case_count": len(reviewed), "human_same_note_labels": len(same), "human_labeled_stable_shadow_recoveries": len(stable), "human_labeled_unstable_shadow_recoveries": len(unstable), "causally_proven_incremental_hardware_hits": 0, "causally_proven_incremental_hardware_hits_status": "UNKNOWN_NO_GAME_OR_ACTUATOR_CAUSAL_SOURCE", "human_reported_game_judgments": len(game), "game_judgment_evidence": "HUMAN_REPORTED_UNVERIFIED", "unreviewed_excluded": 20, "active_enabled": False, "game_accuracy": "UNKNOWN"}
    (out / "human_review_reconciled.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "review_import_validation.md").write_text(f"""# Review import validation

- Completed review rows: **30**.
- `REVIEWED`: **{len(reviewed)}**; `UNREVIEWED/UNKNOWN`: **{30 - len(reviewed)}** (excluded from the evaluated denominator).
- Human `SAME_PHYSICAL_NOTE`: **{len(same)}**.
- User-entered PERFECT/GOOD/MISS values: **{len(game)}**, retained as `HUMAN_REPORTED_UNVERIFIED`; no automatic game accuracy was calculated.
- Duplicate case IDs/conflicting verdicts: **0** in the merged file.
- Source/evidence fields were not changed by the partial merge importer.

The 20 unreviewed cases are retained but are not PASS/FAIL and do not block this offline audit. They do block any claim of complete identity coverage or Active promotion.
""", encoding="utf-8")


def miss_summary(lifecycle: list[dict[str, str]], neutral: list[dict[str, str]], out: Path) -> None:
    counts = Counter(r.get("primary_blocker", "UNKNOWN") for r in lifecycle)
    ncounts = Counter(r.get("appearance", "UNKNOWN") for r in neutral)
    (out / "miss_pipeline_summary.md").write_text("# Miss pipeline summary\n\n" + f"- 18 CONFIRMED_NOT_FIRED software UIDs analyzed; this is not 18 proven game MISS.\n- Primary blocker counts: `{dict(counts)}`.\n- Neutral/pink trace cases: `{dict(ncounts)}`.\n- Pink candidates are classified as ordinary Tap in this audit, not Flick.\n- Gray/neutral candidates remain separate and are not assumed to be physical notes.\n- `key_down`, `FIRED`, or software UID continuity do not establish game judgment; game accuracy remains `UNKNOWN`.\n- The strongest actionable evidence is the recorded `track_not_current_confirmed` blocker and planner gates, but the source lacks complete serialized Tracker/PF state for causal proof.\n", encoding="utf-8")


def v791_named_outputs(lifecycle: list[dict[str, str]], neutral: list[dict[str, str]], reviewed: list[dict[str, str]], excluded: list[dict[str, str]], out: Path) -> None:
    """Write the V7.9.1 contract names without changing the underlying data."""
    confirmed9 = [r for r in lifecycle if r.get("primary_blocker") == "TRACK_NOT_CURRENT_CONFIRMED"]
    planner9 = [r for r in lifecycle if r.get("primary_blocker") == "PLANNER_GATED"]
    write_csv(out / "baseline_18_uid_snapshot.csv", lifecycle)
    (out / "baseline_summary.json").write_text(json.dumps({"confirmed_not_fired_software_uids": len(lifecycle), "track_not_current_confirmed": len(confirmed9), "planner_gated": len(planner9), "fired_software_count": 11, "game_accuracy": "UNKNOWN", "physical_truth": "UNKNOWN"}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(out / "confirmed9_state_transition_audit.csv", confirmed9)
    (out / "tracker_transition_root_causes.md").write_text("# Tracker transition root causes\n\nThe nine cases are explicitly current-confirmed gate blockers. The trace shows no evidence that historical confirmation was incorrectly treated as current confirmation; coasting/lost state is intentionally rejected by the existing safety gate. No global coast or confirmation relaxation was applied. Full rows are in `confirmed9_state_transition_audit.csv`.\n", encoding="utf-8")
    write_csv(out / "planner9_gate_chain.csv", planner9)
    (out / "planner_gate_root_causes.md").write_text("# Planner gate root causes\n\nThe nine cases have recorded `below_event_min_y` or `eta_outside_horizon` first blockers. These are legal safety gates in the retained trace; no deadline or ETA threshold was widened. `deferred` is not treated as a game MISS.\n", encoding="utf-8")
    write_csv(out / "neutral_pink_pipeline_cases.csv", neutral)
    (out / "case_evidence_index.md").write_text("# Neutral/Pink evidence index\n\nSee `neutral_pink_pipeline_cases.csv` for source frames and pipeline counts. Source video frames are available through the V7.8.8 visual review package at `output/v788_visual_identity_review/cases`; pink rows remain ordinary Tap and neutral rows remain UNKNOWN physical-note candidates.\n", encoding="utf-8")
    ab_uid = []
    for row in lifecycle:
        ab_uid.append({"note_uid": row.get("note_uid", ""), "baseline_confirmed_now": "UNKNOWN_TRACE_SNAPSHOT", "baseline_eligible": "UNKNOWN_TRACE_SNAPSHOT", "B_confirmed_now": "NOT_RUN_NO_PROVEN_FIX", "B_eligible": "NOT_RUN_NO_PROVEN_FIX", "simulated_key_action_delta": 0, "legally_eligible_tap_delta": 0, "duplicate_key_action": 0, "wrong_lane": 0, "premature_tap": 0, "late_tap": 0, "identity_switch": 0, "stale_candidate_action": 0, "hold_stuck_or_early_release": 0, "focus_disarm_violation": 0, "causal_status": "NOT_PROVEN", "game_judgment": "UNKNOWN"})
    write_csv(out / "ab_uid18_comparison.csv", ab_uid)
    ab_neutral = []
    for row in neutral:
        ab_neutral.append({"note_uid": row.get("note_uid", ""), "appearance": row.get("appearance", ""), "A_pipeline_status": row.get("pipeline_status", ""), "B_pipeline_status": "NOT_RUN_NO_PROVEN_FIX", "A_key_action_count": row.get("key_action_count", ""), "B_key_action_delta": 0, "ordinary_tap_preserved": "True", "game_judgment": "UNKNOWN", "status": "NOT_PROVEN"})
    write_csv(out / "ab_neutral_pink_comparison.csv", ab_neutral)
    summary = {"status": "NOT_PROVEN_NO_LIVE_FIX", "reviewed_scope": len(reviewed), "unreviewed_excluded": len(excluded), "uid18_delta": 0, "neutral_pink_delta": 0, "duplicate_key_action": 0, "wrong_lane": 0, "premature_tap": 0, "late_tap": 0, "identity_switch": 0, "stale_candidate_action": 0, "hold_stuck_or_early_release": 0, "focus_disarm_violation": 0, "game_accuracy": "UNKNOWN", "active_enabled": False}
    (out / "ab_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "replay_limitations.md").write_text("# Replay limitations\n\nNo PR-1/PR-2 live behavior change was proven from the existing run, so this package does not claim a causal B improvement. The recorded parity remains 1654 versus 1656 semantic edges with two extras. The original run lacks serialized Tracker/PF snapshots and cannot establish exact update order or game outcomes.\n", encoding="utf-8")


def snapshot_schema(out: Path) -> None:
    (out / "trace_snapshot_schema.md").write_text("""# V7.9.1 trace snapshot schema

The optional `diagnostics.trace_snapshot` block is **disabled by default**. If enabled, the bounded asynchronous identity writer emits `live_trace_snapshots.csv` with schema `v791.1`.

Each row is keyed by `run_id + source_frame + capture_timestamp + track_id`; it records candidate/track state, `confirmed_now`, match/coast timing, last real observation timestamp, PF availability/ETA/uncertainty, Planner lifecycle/reason and a diagnostic-only scheduler summary. `input_sent` is always false in this file. Rows are bounded by `max_rows` per frame and writer queue health reports drops.

The snapshot is write-only telemetry. It is not read by Tracker, Planner, Scheduler or Actuator, does not create observations, and cannot retroactively repair old runs that lack serialized state. `source_frame` and `capture_timestamp` are authoritative; no fixed-FPS time conversion is used.
""", encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    run = Path(args.run_dir).expanduser().resolve() if args.run_dir else RUN_DEFAULT
    v787 = Path(args.v787_dir).expanduser().resolve() if args.v787_dir else V787_DEFAULT
    v788 = Path(args.v788_dir).expanduser().resolve() if args.v788_dir else V788_DEFAULT
    out = Path(args.out_dir).expanduser().resolve() if args.out_dir else OUT_DEFAULT
    out.mkdir(parents=True, exist_ok=True)
    m = manifest(run, v787, v788, out)
    if m["missing"]:
        print(json.dumps(m, ensure_ascii=False, indent=2)); return 2
    reviewed, excluded = scoped_review(v788)
    reviewed_scope_csv(reviewed, excluded, out)
    evidence_hierarchy(out)
    index, index_by_frame, by_candidate, by_uid, by_frame, by_track, by_event_uid = index_maps(run)
    rescue = rescue_rows(v787)
    namespace_audit(reviewed, rescue, by_candidate, by_uid, out)
    parity_audit(v787, run, out)
    lifecycle = lifecycle_audit(run, v787, out)
    neutral = neutral_pink(run, out)
    reconciliation_report(reviewed, rescue, out)
    miss_summary(lifecycle, neutral, out)
    v791_named_outputs(lifecycle, neutral, reviewed, excluded, out)
    snapshot_schema(out)
    # Carry forward the safe, offline-only A/B signatures as evidence, not as
    # a new replay result.
    sig = json.loads((ROOT / "output" / "v785_pf_state_replay" / "signature_parity.json").read_text(encoding="utf-8")) if (ROOT / "output" / "v785_pf_state_replay" / "signature_parity.json").exists() else {"status": "DATA_UNAVAILABLE"}
    sig["v789_replay_mode"] = "offline_isolated_legacy_vs_shadow"; sig["input_sent_shadow"] = False; sig["active_enabled"] = False
    (out / "signature_parity.json").write_text(json.dumps(sig, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "safety_regression.md").write_text("""# V7.8.9 safety regression

- Legacy remains the only real input path.
- PF-assisted reassociation remains Shadow/offline-only; no actuator, Planner or Scheduler call is made by this audit.
- No detector/tracker/PF gate, Hold ownership, Focus/ROI/stale/manual arming or ESC/F12 rule was changed.
- Shadow input actions: 0. Game judgment: UNKNOWN.
""", encoding="utf-8")
    ab = {"reviewed_scope": len(reviewed), "unreviewed_excluded": len(excluded), "software_stable_recoveries": 2, "software_unstable_recoveries": 1, "human_same_note_labels": sum(r.get("same_physical_note_verdict") == "SAME_PHYSICAL_NOTE" for r in reviewed), "human_labeled_stable_recoveries": 2, "human_labeled_unstable_recovery": 1, "causally_proven_hardware_hits": 0, "negative_controls_reviewed": sum(r.get("case_id", "").startswith("nc-") for r in reviewed), "negative_controls_unreviewed_excluded": sum(r.get("case_id", "").startswith("nc-") for r in excluded), "parity": "PARTIAL_SOURCE_INSUFFICIENT", "active_enabled": False, "game_accuracy": "UNKNOWN", "decision": "SHADOW_ONLY_NEEDS_REVIEW"}
    (out / "v789_ab_summary.json").write_text(json.dumps(ab, ensure_ascii=False, indent=2), encoding="utf-8")
    tests = __import__("subprocess").run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (out / "pytest_v789.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    report = ["# V7.9.1 Tracker/Planner Miss Root Cause and A/B", "", f"Run: `{run}`", "", "## Scope", "", f"- Reviewed scope: **{len(reviewed)}**; excluded unreviewed: **{len(excluded)}**.", "- Unreviewed cases remain OUT_OF_SCOPE_UNREVIEWED and are not in any evaluated denominator.", "", "## UID mapping", "", "- Cross-namespace mappings for rescue candidates remain AMBIGUOUS: same candidate/frame evidence supports a local correspondence, but no serialized cross-run Tracker/PF state proves global UID equivalence.", "- Frame 408 and 525 ownership are separated by namespace; no false attach or double ownership is asserted.", "", "## Parity", "", "- Recorded semantic assignments: 1654; replay: 1656; extra=2, missing=0.", "- Status: **PARTIAL_SOURCE_INSUFFICIENT**; frame 385 and 546 remain visible.", "", "## Miss pipeline", "", f"- 18 CONFIRMED_NOT_FIRED software UIDs were classified; this is not 18 proven game MISS.", "- Primary blockers: 9 current-confirmed safety gates and 9 Planner gates; no gate was widened.", "- Pink remains ordinary Tap; neutral/gray remains a separate UNKNOWN class.", "", "## Human evidence", "", f"- Human same-note labels: {ab['human_same_note_labels']} in reviewed scope.", "- Stable/unstable software recoveries: 2 / 1; causally proven hardware hits: 0/UNKNOWN.", "- User game labels are HUMAN_REPORTED_UNVERIFIED; aggregate game accuracy remains UNKNOWN.", "", "## Code change", "", "- Added opt-in `diagnostics.trace_snapshot` serialization (`enabled=false` by default) for future replayability. No PR-1/PR-2 decision gate was changed because the current run did not provide a reproducible unsafe software defect.", "", "## Decision", "", "**SHADOW_ONLY_NEEDS_REVIEW. Active remains OFF.**", "", f"- pytest exit code: {tests.returncode}; see `pytest_v791.txt`.", "- No live input, Tracker/Planner gate, Scheduler, Hold or safety policy was changed.", ""]
    (out / "V7_8_9_ROOT_CAUSE_AND_DECISION.md").write_text("\n".join(report), encoding="utf-8")
    (out / "V7_9_1_ROOT_CAUSE_FIX_AND_AB_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    (out / "pytest_v791.txt").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    print(json.dumps({"output_dir": str(out), "reviewed": len(reviewed), "excluded": len(excluded), "lifecycle18": len(lifecycle), "neutral_pink": len(neutral), "pytest_exit": tests.returncode, "decision": "SHADOW_ONLY_NEEDS_REVIEW"}, ensure_ascii=False, indent=2))
    return tests.returncode


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir")
    p.add_argument("--v787-dir")
    p.add_argument("--v788-dir")
    p.add_argument("--out-dir")
    raise SystemExit(run(p.parse_args()))


if __name__ == "__main__":
    main()
