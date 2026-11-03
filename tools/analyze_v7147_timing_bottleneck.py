"""Measure V7.14.7 Tap deadline amendment bottlenecks from one run.

This is deliberately conservative: explicit transition reasons are counted
separately from inferred earlier-ETA opportunities.  Inferred opportunities
are not treated as proof that the scheduler rejected them or that the game
would have produced a different grade.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def _f(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def _read(path):
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def _write(path, rows):
    fields = list(rows[0].keys()) if rows else ["uid"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(len(values) - 1, int(pos) + 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def analyze(run_dir: Path, out_dir: Path, *, freeze_ms=30.0, max_step_ms=40.0,
            max_total_ms=80.0):
    run_dir = run_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    run = json.loads((run_dir / "live_run.json").read_text(encoding="utf-8-sig")) if (run_dir / "live_run.json").exists() else {}
    intent_rows, intent_fields = _read(run_dir / "tap_intents.csv")
    decision_rows, decision_fields = _read(run_dir / "tap_decisions.csv")
    action_rows, action_fields = _read(run_dir / "input_actions.csv")
    global_rows, global_fields = _read(run_dir / "global_tap_timing_shadow.csv")

    required = {
        "tap_intents.csv": {"event_id", "state", "timestamp"},
        "tap_decisions.csv": {"note_uid", "timestamp", "reason"},
        "input_actions.csv": {"action", "event_id", "timestamp"},
        "global_tap_timing_shadow.csv": {"note_uid", "capture_timestamp", "press_at"},
    }
    missing = {}
    for filename, fields in required.items():
        actual = {"tap_intents.csv": set(intent_fields),
                  "tap_decisions.csv": set(decision_fields),
                  "input_actions.csv": set(action_fields),
                  "global_tap_timing_shadow.csv": set(global_fields)}[filename]
        missing[filename] = sorted(fields - actual)

    actions_by_uid = defaultdict(list)
    for row in action_rows:
        uid = row.get("event_id", "")
        if uid and row.get("action") in {"scheduled", "amended", "key_down", "canceled"}:
            actions_by_uid[uid].append(row)
    for rows in actions_by_uid.values():
        rows.sort(key=lambda row: _f(row.get("timestamp"), math.inf))
    global_by_uid = defaultdict(list)
    for row in global_rows:
        uid = row.get("note_uid", "")
        if uid:
            global_by_uid[uid].append(row)
    for rows in global_by_uid.values():
        rows.sort(key=lambda row: _f(row.get("capture_timestamp"), math.inf))
    intent_by_uid = defaultdict(list)
    for row in intent_rows:
        uid = row.get("note_uid") or row.get("event_id") or ""
        if uid:
            intent_by_uid[uid].append(row)
    decision_by_uid = defaultdict(list)
    for row in decision_rows:
        uid = row.get("note_uid", "")
        if uid:
            decision_by_uid[uid].append(row)

    amendment_reason_counts = Counter(row.get("reason", "") for row in intent_rows
                                      if "amend" in row.get("reason", "").lower())
    explicit_earlier = [row for row in intent_rows if row.get("reason") == "amend_earlier_disabled"]
    rows_out = []
    inferred_examples = []
    early_deltas = []
    safe_early_deltas = []
    key_offsets = []
    categories = Counter()
    amendment_deltas = []

    all_uids = sorted(set(actions_by_uid) | set(global_by_uid) | set(intent_by_uid))
    for uid in all_uids:
        history = actions_by_uid.get(uid, [])
        deadlines = [row for row in history if row.get("action") in {"scheduled", "amended"}
                      and _f(row.get("scheduled_hit")) is not None]
        keydowns = [row for row in history if row.get("action") == "key_down"]
        first_deadline = _f(deadlines[0].get("scheduled_hit")) if deadlines else None
        final_deadline = _f(deadlines[-1].get("scheduled_hit")) if deadlines else None
        first_deadline_at = _f(deadlines[0].get("timestamp")) if deadlines else None
        final_deadline_at = _f(deadlines[-1].get("timestamp")) if deadlines else None
        first_key = deadlines[0].get("key", "") if deadlines else ""
        amendment_count = sum(row.get("action") == "amended" for row in history)
        for old, new in zip(deadlines, deadlines[1:]):
            old_hit, new_hit = _f(old.get("scheduled_hit")), _f(new.get("scheduled_hit"))
            if old_hit is not None and new_hit is not None:
                amendment_deltas.append((new_hit - old_hit) * 1000.0)

        explicit = [row for row in intent_by_uid.get(uid, [])
                    if row.get("reason") == "amend_earlier_disabled"]
        inferred = []
        safe_inferred = []
        available_press = []
        for proposal in global_by_uid.get(uid, []):
            press = _f(proposal.get("press_at"))
            capture = _f(proposal.get("capture_timestamp"))
            if (press is None or capture is None or first_deadline is None or
                    first_deadline_at is None or capture < first_deadline_at):
                continue
            if proposal.get("eta_status") == "AVAILABLE":
                available_press.append(press)
            current = first_deadline
            for action in deadlines:
                at = _f(action.get("timestamp"))
                if at is not None and at <= capture:
                    current = _f(action.get("scheduled_hit"), current)
            delta_ms = (press - current) * 1000.0
            if delta_ms >= -1e-6:
                continue
            inferred.append({"capture": capture, "press": press, "old_deadline": current,
                             "delta_ms": delta_ms,
                             "key": proposal.get("planner_key", ""),
                             "speed_epoch": proposal.get("speed_epoch", ""),
                             "eta_status": proposal.get("eta_status", ""),
                             "uncertainty": _f(proposal.get("uncertainty_s"))})
            early_deltas.append(delta_ms)
            within_freeze = capture >= current - freeze_ms / 1000.0
            step_ok = abs(delta_ms) <= max_step_ms
            initial_delta = (press - first_deadline) * 1000.0
            total_ok = abs(initial_delta) <= max_total_ms
            future_ok = press > capture
            key_ok = not proposal.get("planner_key") or not first_key or proposal.get("planner_key") == first_key
            available = proposal.get("eta_status") == "AVAILABLE" and proposal.get("model_status") in {"ready", ""}
            epoch_ok = True
            if proposal.get("speed_epoch"):
                epochs = {r.get("speed_epoch") for r in global_by_uid.get(uid, []) if r.get("speed_epoch")}
                epoch_ok = proposal.get("speed_epoch") in epochs
            safe = (not within_freeze and step_ok and total_ok and future_ok and key_ok and available and epoch_ok)
            if safe:
                safe_inferred.append(inferred[-1])
                safe_early_deltas.append(delta_ms)

        actual = _f(keydowns[-1].get("timestamp")) if keydowns else None
        if actual is not None and final_deadline is not None:
            key_offsets.append((actual - final_deadline) * 1000.0)
        reasons = [row.get("reason", "") for row in intent_by_uid.get(uid, []) if row.get("reason")]
        reason_blob = "|".join(sorted(set(reasons)))
        if not deadlines and any("hold" in str(r).lower() for r in reasons):
            category = "HOLD_CONFLICT"
        elif deadlines and actual is None:
            category = "NO_INPUT"
        elif deadlines and actual is not None:
            category = "SCHEDULED_BUT_SLOW_UNKNOWN"
        elif any(r in {"press_time_not_future", "eta_outside_horizon"} for r in reasons):
            category = "LATE_ESTIMATE"
        else:
            category = "UNRESOLVED"
        categories[category] += 1
        rows_out.append({
            "uid": uid,
            "first_deadline": first_deadline or "",
            "final_deadline": final_deadline or "",
            "first_deadline_timestamp": first_deadline_at or "",
            "final_deadline_timestamp": final_deadline_at or "",
            "last_available_press_at": available_press[-1] if available_press else "",
            "actual_key_down": actual or "",
            "key_down_minus_final_ms": (actual - final_deadline) * 1000.0 if actual is not None and final_deadline is not None else "",
            "amendment_count": amendment_count,
            "amendment_deltas_ms": ";".join(f"{v:.3f}" for v in [
                (_f(new.get("scheduled_hit")) - _f(old.get("scheduled_hit"))) * 1000.0
                for old, new in zip(deadlines, deadlines[1:])
                if _f(old.get("scheduled_hit")) is not None and _f(new.get("scheduled_hit")) is not None]),
            "explicit_earlier_disabled_count": len(explicit),
            "inferred_earlier_proposal_count": len(inferred),
            "inferred_safe_earlier_count": len(safe_inferred),
            "inferred_earliest_delta_ms": min((x["delta_ms"] for x in inferred), default=""),
            "reason": reason_blob,
            "classification": category,
            "game_grade": "UNKNOWN",
        })
        for item in safe_inferred or inferred:
            inferred_examples.append({"uid": uid, "capture_timestamp": item["capture"],
                                      "old_deadline": item["old_deadline"],
                                      "proposed_press_at": item["press"],
                                      "proposed_delta_ms": item["delta_ms"],
                                      "planner_key": item["key"],
                                      "speed_epoch": item["speed_epoch"],
                                      "eta_status": item["eta_status"],
                                      "uncertainty_s": item["uncertainty"],
                                      "reason": ("INFERRED_SAFE_EARLIER_CANDIDATE" if item in safe_inferred
                                                 else "INFERRED_EARLIER_NOT_FULLY_VERIFIED")})

    rows_out.sort(key=lambda row: (row["classification"], row["uid"]))
    _write(out_dir / "v7147_amend_baseline.csv", rows_out)
    safe_examples = [row for row in inferred_examples
                     if row["reason"] == "INFERRED_SAFE_EARLIER_CANDIDATE"]
    other_examples = [row for row in inferred_examples
                      if row["reason"] != "INFERRED_SAFE_EARLIER_CANDIDATE"]
    examples = (sorted(safe_examples, key=lambda row: (row["proposed_delta_ms"], row["uid"]))[:10] +
                sorted(other_examples, key=lambda row: (row["proposed_delta_ms"], row["uid"]))[:10])
    _write(out_dir / "v7147_earlier_examples.csv", examples)

    explicit_proposal_count = len(explicit_earlier)
    safe_uids = {row["uid"] for row in inferred_examples if row["reason"] == "INFERRED_SAFE_EARLIER_CANDIDATE"}
    report = [
        "# V7.14.7 timing bottleneck baseline", "",
        f"Run: `{run_dir}`", "Scope: offline diagnostics; no Active config was changed.", "",
        "## Input/schema audit",
        f"- Missing required columns: `{missing}`",
        "- All timestamps are parsed as the run's monotonic capture/processing seconds; blank or non-finite values are not converted to zero.",
        "",
        "## H1 evidence",
        f"- Explicit `amend_earlier_disabled` transition events: **{explicit_proposal_count}**.",
        f"- Explicit event UIDs: **{len({r.get('note_uid') for r in explicit_earlier})}**.",
        f"- Inferred earlier ETA candidates (not explicit rejections): **{len(inferred_examples)} rows / {len({r['uid'] for r in inferred_examples})} UIDs**.",
        f"- Inferred candidates passing future/epoch/key/availability/freeze/step/total checks: **{len([r for r in inferred_examples if r['reason']=='INFERRED_SAFE_EARLIER_CANDIDATE'])} rows / {len(safe_uids)} UIDs**.",
        f"- Inferred earlier delta P50/P90: **{_percentile(early_deltas,.5)} / {_percentile(early_deltas,.9)} ms**.",
        f"- Inferred safe earlier delta P50/P90: **{_percentile(safe_early_deltas,.5)} / {_percentile(safe_early_deltas,.9)} ms**.",
        "These inferred rows show that a newer ETA was earlier than the recorded deadline; they do not prove the live manager rejected it, because this run predates the new diagnostic fields.",
        "",
        "## Deadline and input timing",
        f"- Amendment actions: **{sum(1 for r in action_rows if r.get('action') == 'amended')}**; amendment delta P50/P90: **{_percentile(amendment_deltas,.5)} / {_percentile(amendment_deltas,.9)} ms**.",
        f"- Tap key-down minus final deadline P50/P90: **{_percentile(key_offsets,.5)} / {_percentile(key_offsets,.9)} ms** (execution offset, not game grade).",
        f"- UID classifications: `{dict(categories)}`.",
        "- `press_time_not_future` and `eta_outside_horizon` are gate/estimate counts; they are not MISS counts.",
        "",
        "## Go / No-Go",
        ("**NO-GO for Active enablement from this run alone.** Explicit earlier-disabled rows are absent, and no game-grade truth exists. "
         "The inferred candidates justify a controlled Shadow/A-B experiment, but not a claim of improvement."),
        "",
        "## Example cases",
        f"`v7147_earlier_examples.csv` contains {len(examples)} timestamped UID examples (up to 20), including old deadline, proposed press time, delta, key and epoch.",
        "",
        "## Interpretation",
        "A/B group B can be prepared with allow_earlier_amend=true, but it must remain opt-in. Compare only identical song segments with human one-to-one game grades; otherwise report UNKNOWN/INSUFFICIENT_GROUND_TRUTH.",
    ]
    (out_dir / "v7147_bottleneck_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"uids": len(rows_out), "explicit_earlier": explicit_proposal_count,
            "inferred_earlier": len(inferred_examples), "safe_uids": len(safe_uids),
            "categories": dict(categories), "missing": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("output/analysis_v7147"))
    parser.add_argument("--freeze-window-ms", type=float, default=30.0)
    parser.add_argument("--max-amend-step-ms", type=float, default=40.0)
    parser.add_argument("--max-total-amend-ms", type=float, default=80.0)
    args = parser.parse_args()
    print(json.dumps(analyze(args.run_dir, args.out_dir,
                              freeze_ms=args.freeze_window_ms,
                              max_step_ms=args.max_amend_step_ms,
                              max_total_ms=args.max_total_amend_ms), indent=2))


if __name__ == "__main__":
    main()
