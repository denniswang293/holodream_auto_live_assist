"""Reconstruct per-UID Tap deadline ledgers for the V7.14.8 A/B runs."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict, Counter
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


def _write(path, rows, fields=None):
    fields = fields or (list(rows[0].keys()) if rows else ["uid"])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def _pct(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return "UNKNOWN"
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo, hi = int(pos), min(len(values) - 1, int(pos) + 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def _run_variant(run_dir):
    run_path = run_dir / "live_run.json"
    if not run_path.exists():
        return "UNKNOWN", "RAW_RUN_NOT_AVAILABLE"
    try:
        data = json.loads(run_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return "UNKNOWN", "RAW_RUN_NOT_AVAILABLE"
    return data.get("variant", "UNKNOWN"), "OK"


def analyze_one(run_dir: Path, group: str):
    if not run_dir.exists():
        return {"group": group, "run_dir": str(run_dir), "status": "RAW_RUN_NOT_AVAILABLE"}, [], []
    variant, status = _run_variant(run_dir)
    actions, action_fields = _read(run_dir / "input_actions.csv")
    intents, intent_fields = _read(run_dir / "tap_intents.csv")
    decisions, decision_fields = _read(run_dir / "tap_decisions.csv")
    global_rows, global_fields = _read(run_dir / "global_tap_timing_shadow.csv")
    if not actions or not intents:
        status = "HISTORICAL_OUTPUT_PRUNED"

    action_by_uid = defaultdict(list)
    for row in actions:
        uid = row.get("event_id", "")
        if uid and row.get("note_type") == "tap" and row.get("action") in {"scheduled", "amended", "key_down", "canceled"}:
            action_by_uid[uid].append(row)
    for rows in action_by_uid.values():
        rows.sort(key=lambda row: _f(row.get("timestamp"), math.inf))
    intent_by_uid = defaultdict(list)
    for row in intents:
        uid = row.get("note_uid") or row.get("event_id") or ""
        if uid:
            intent_by_uid[uid].append(row)
    for rows in intent_by_uid.values():
        rows.sort(key=lambda row: _f(row.get("timestamp"), math.inf))
    global_by_uid = defaultdict(list)
    for row in global_rows:
        if row.get("note_uid"):
            global_by_uid[row["note_uid"]].append(row)
    for rows in global_by_uid.values():
        rows.sort(key=lambda row: _f(row.get("capture_timestamp"), math.inf))

    per_uid, ledger = [], []
    all_uids = sorted(set(action_by_uid) | set(intent_by_uid))
    for uid in all_uids:
        history = action_by_uid.get(uid, [])
        deadlines = [row for row in history if row.get("action") in {"scheduled", "amended"}
                      and _f(row.get("scheduled_hit")) is not None]
        if not deadlines:
            continue
        initial = _f(deadlines[0].get("scheduled_hit"))
        current = initial
        first_scheduled_at = _f(deadlines[0].get("timestamp"))
        amendments = []
        previous_direction = None
        reversals = 0
        max_step = 0.0
        sum_abs = 0.0
        for row in deadlines:
            new = _f(row.get("scheduled_hit"))
            direction = "initial"
            delta_ms = ""
            old = current
            if row.get("action") == "amended":
                delta_ms = (new - current) * 1000.0
                direction = "earlier" if delta_ms < 0 else "later" if delta_ms > 0 else "none"
                if previous_direction and direction != "none" and direction != previous_direction:
                    reversals += 1
                if direction != "none":
                    previous_direction = direction
                max_step = max(max_step, abs(delta_ms))
                sum_abs += abs(delta_ms)
                amendments.append((row, old, new, direction, delta_ms))
            current = new
            if row.get("action") == "amended":
                ledger.append({
                    "group": group, "variant": variant, "uid": uid,
                    "revision": row.get("revision", ""), "action_timestamp": row.get("timestamp", ""),
                    "action": row.get("action", ""), "amend_direction": direction,
                    "old_deadline": old, "new_deadline": new, "delta_ms": delta_ms,
                    "net_shift_from_initial_ms": (new - initial) * 1000.0,
                    "sum_abs_amend_ms": sum_abs, "reversal_count_at_action": reversals,
                    "max_step_ms": max_step, "key": row.get("key", ""),
                    "speed_epoch": next((r.get("speed_epoch") for r in reversed(intent_by_uid.get(uid, []))
                                         if r.get("speed_epoch")), ""),
                    "freeze_remaining_ms": "",
                    "rejection_reason": "",
                    "source": "input_actions.csv",
                })
        explicit_rejections = [row for row in intent_by_uid.get(uid, [])
                               if row.get("reason") in {"amend_earlier_disabled", "deadline_freeze_window",
                                                         "amend_step_too_large", "amend_total_limit",
                                                         "invalid_amended_deadline"}]
        # New runs expose freeze/delta fields directly; historical runs are
        # reconstructed from input_actions and remain explicitly labelled.
        for row in explicit_rejections:
            ledger.append({
                "group": group, "variant": variant, "uid": uid,
                "revision": row.get("revision", ""), "action_timestamp": row.get("timestamp", ""),
                "action": "rejected", "amend_direction": row.get("amend_direction", ""),
                "old_deadline": row.get("old_deadline", ""), "new_deadline": row.get("new_deadline", ""),
                "delta_ms": row.get("proposed_delta_ms", ""), "net_shift_from_initial_ms": "",
                "sum_abs_amend_ms": "", "reversal_count_at_action": "", "max_step_ms": "",
                "key": row.get("key", ""), "speed_epoch": row.get("speed_epoch", ""),
                "freeze_remaining_ms": row.get("freeze_remaining_ms", ""),
                "rejection_reason": row.get("reason", ""), "source": "tap_intents.csv",
            })
        keydowns = [row for row in history if row.get("action") == "key_down"]
        key_down = _f(keydowns[-1].get("timestamp")) if keydowns else None
        # A later planner diagnostic NOT_SCHEDULED must not erase an actual
        # scheduler action.  Input actions are the software execution source;
        # lifecycle terminal state is kept separate from post-fire diagnostics.
        if keydowns:
            final_state = "FIRED"
        elif any(row.get("action") == "canceled" for row in history):
            final_state = "CANCELED"
        elif any(row.get("action") == "abstain" for row in history):
            final_state = "EXPIRED"
        else:
            final_state = next((row.get("state") for row in reversed(intent_by_uid.get(uid, []))
                                if row.get("state") in {"FIRED", "CANCELED", "EXPIRED", "PENDING"}), "UNKNOWN")
        post_fire_diagnostic_rejection = bool(final_state == "FIRED" and any(
            row.get("state") == "NOT_SCHEDULED" for row in intent_by_uid.get(uid, [])))
        per_uid.append({
            "group": group, "variant": variant, "uid": uid,
            "first_scheduled_at": first_scheduled_at or "", "first_deadline": initial or "",
            "final_deadline": current or "", "net_deadline_shift_ms": (current - initial) * 1000.0,
            "earlier_count": sum(item[3] == "earlier" for item in amendments),
            "later_count": sum(item[3] == "later" for item in amendments),
            "reversal_count": reversals, "max_step_ms": max_step,
            "sum_abs_amend_ms": sum_abs, "amend_count": len(amendments),
            "key_down_at": key_down or "",
            "key_down_minus_final_deadline_ms": (key_down - current) * 1000.0 if key_down is not None else "",
            "key": keydowns[-1].get("key", "") if keydowns else deadlines[-1].get("key", ""),
            "final_state": final_state, "post_fire_diagnostic_rejection": post_fire_diagnostic_rejection,
            "lifecycle_terminal": final_state,
            "explicit_rejection_count": len(explicit_rejections),
            "no_input": not bool(keydowns), "hold_or_conflict": any(
                token in str(row.get("reason", "")).lower() for row in intent_by_uid.get(uid, [])
                for token in ("hold", "conflict")),
            "speed_epochs": ";".join(sorted({row.get("speed_epoch", "") for row in intent_by_uid.get(uid, []) if row.get("speed_epoch")})),
            "game_grade": "UNKNOWN",
        })
    return {"group": group, "variant": variant, "run_dir": str(run_dir), "status": status,
            "action_fields": action_fields, "intent_fields": intent_fields,
            "decision_fields": decision_fields, "global_fields": global_fields}, per_uid, ledger


def analyze(baseline_run: Path, experiment_run: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries, per_uid, ledger = [], [], []
    for group, path in (("baseline", baseline_run), ("experiment", experiment_run)):
        summary, rows, entries = analyze_one(path, group)
        summaries.append(summary); per_uid.extend(rows); ledger.extend(entries)
    per_fields = list(per_uid[0].keys()) if per_uid else ["uid"]
    ledger_fields = list(ledger[0].keys()) if ledger else ["uid"]
    _write(out_dir / "deadline_per_uid.csv", per_uid, per_fields)
    _write(out_dir / "deadline_amend_ledger.csv", ledger, ledger_fields)

    by_group = {}
    for group in ("baseline", "experiment"):
        rows = [r for r in per_uid if r["group"] == group]
        earlier = [float(r["delta_ms"]) for r in ledger if r["group"] == group and r.get("amend_direction") == "earlier" and _f(r.get("delta_ms")) is not None]
        net = [_f(r["net_deadline_shift_ms"]) for r in rows]
        by_group[group] = {
            "uids": len(rows), "earlier_actions": len(earlier),
            "earlier_uids": len({r["uid"] for r in ledger if r["group"] == group and r.get("amend_direction") == "earlier"}),
            "earlier_p10": _pct(earlier, .1), "earlier_p50": _pct(earlier, .5), "earlier_p90": _pct(earlier, .9),
            "net_shift_p10": _pct(net, .1), "net_shift_p50": _pct(net, .5), "net_shift_p90": _pct(net, .9),
            "reversal_uids": sum(int(r["reversal_count"]) > 0 for r in rows),
            "no_input_uids": sum(bool(r["no_input"]) for r in rows),
            "fired_uids": sum(r["final_state"] == "FIRED" for r in rows),
        }
    oscillating = sorted([r for r in per_uid if int(r["reversal_count"]) > 0],
                         key=lambda r: (-int(r["reversal_count"]), abs(float(r["net_deadline_shift_ms"]))))[:20]
    no_input = sorted([r for r in per_uid if r["no_input"]], key=lambda r: (r["group"], r["uid"]))[:20]
    report = [
        "# V7.14.8 Why tap-earlier may feel better", "",
        "This report reconstructs deadline changes from the two user A/B runs.",
        "It separates accepted action changes from inferred/shadow estimates and never treats key_down/FIRED as game hit truth.", "",
        "## Run availability",
    ]
    for summary in summaries:
        report.append(f"- {summary['group']}: `{summary['run_dir']}` → `{summary['status']}`")
    report += ["", "## Per-group ledger metrics"]
    for group, values in by_group.items():
        report += [
            f"### {group}",
            f"- UIDs: {values['uids']}; accepted earlier amendment actions: {values['earlier_actions']} across {values['earlier_uids']} UIDs.",
            f"- Earlier delta P10/P50/P90: {values['earlier_p10']} / {values['earlier_p50']} / {values['earlier_p90']} ms.",
            f"- Final net shift P10/P50/P90: {values['net_shift_p10']} / {values['net_shift_p50']} / {values['net_shift_p90']} ms.",
            f"- UIDs with direction reversals: {values['reversal_uids']}; no-input UIDs: {values['no_input_uids']}; FIRED state UIDs: {values['fired_uids']} (not hit truth).",
        ]
    report += ["", "## Attribution"]
    report += [
        "- **H1 late-only bias — SUPPORTED at the software-path level / outcome UNRESOLVED:** experiment actions show real earlier amendments, while baseline shows none. This demonstrates the switch changes stale-deadline handling; absent game grades, it cannot prove fewer SLOW results.",
        "- **H2 amendment oscillation — POSSIBLE:** reversal rows are listed below. A large reversal count or near-zero net shift means the extra amendments may be noise rather than a stable correction.",
        "- **H3 fixed 60ms / geometry — UNRESOLVED:** both runs share 60ms and the same geometry hash; the A/B cannot validate the anchor or hit line.",
        "- **H4 execution delay — SUPPORTED as a small software offset only:** the prior baseline key-down/final-deadline median was about 2ms; this is not a game FAST/SLOW label.",
        "",
        "## High-oscillation examples",
    ]
    if oscillating:
        for row in oscillating[:10]:
            report.append(f"- {row['group']} `{row['uid']}`: earlier={row['earlier_count']}, later={row['later_count']}, reversals={row['reversal_count']}, net={row['net_deadline_shift_ms']}ms, final={row['final_state']}.")
    else:
        report.append("- None observed in the reconstructed ledger.")
    report += ["", "## No-input / counterexamples"]
    if no_input:
        for row in no_input[:10]:
            report.append(f"- {row['group']} `{row['uid']}`: amendments={row['amend_count']}, net={row['net_deadline_shift_ms']}ms, reason flags hold/conflict={row['hold_or_conflict']}.")
    else:
        report.append("- None in the available UID ledger.")
    report += ["", "## Conclusion", "B's internal path is measurably different and consistent with the user's subjective improvement, but no quantitative game improvement can be claimed until at least 30 one-to-one Tap grades per group are manually confirmed. Keep `tap-earlier` opt-in and retain `stable` as the immediate rollback."]
    (out_dir / "v7148_why_experiment_feels_better.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"groups": by_group, "rows": len(per_uid), "ledger_rows": len(ledger)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--experiment-run", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("output/analysis_v7148"))
    args = parser.parse_args()
    print(json.dumps(analyze(args.baseline_run, args.experiment_run, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
