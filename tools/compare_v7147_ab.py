"""Compare opt-in V7.14.7 A/B runs without claiming game accuracy."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def _read(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_summary(run_dir: Path, group: str):
    run = json.loads((run_dir / "live_run.json").read_text(encoding="utf-8-sig")) if (run_dir / "live_run.json").exists() else {}
    actions = _read(run_dir / "input_actions.csv")
    intents = _read(run_dir / "tap_intents.csv")
    baseline_path = run_dir / "v7147_amend_baseline.csv"
    if not baseline_path.exists():
        baseline_path = run_dir / "v7147_analysis" / "v7147_amend_baseline.csv"
    baseline = _read(baseline_path)
    grades_path = run_dir / "tap_game_grade_review.csv"
    if not grades_path.exists():
        grades_path = run_dir / "v7147_analysis" / "tap_game_grade_review.csv"
    grades = _read(grades_path)
    if not grades:
        # A run without manual review is still a valid internal timing run;
        # keep the grade denominator explicitly zero/UNKNOWN.
        grades = []
    tap_downs = [r for r in actions if r.get("action") == "key_down" and r.get("note_type") == "tap"]
    amend = [r for r in actions if r.get("action") == "amended"]
    accepted_earlier = 0
    accepted_later = 0
    amendment_deltas = []
    by_event = {}
    for row in actions:
        if row.get("event_id") and row.get("action") in {"scheduled", "amended"} and _f(row.get("scheduled_hit")) is not None:
            by_event.setdefault(row["event_id"], []).append(row)
    for history in by_event.values():
        history.sort(key=lambda r: _f(r.get("timestamp")) or 0.0)
        current = None
        for row in history:
            new_hit = _f(row.get("scheduled_hit"))
            if new_hit is None:
                continue
            if row.get("action") == "scheduled" and current is None:
                current = new_hit
                continue
            if row.get("action") != "amended" or current is None:
                # Multiple initial scheduled records can occur during a
                # lifecycle; they are not amendment direction evidence.
                current = new_hit if row.get("action") == "scheduled" else current
                continue
            delta = (new_hit - current) * 1000.0
            current = new_hit
            amendment_deltas.append(delta)
            if delta < 0:
                accepted_earlier += 1
            elif delta > 0:
                accepted_later += 1
    explicit = sum(1 for r in baseline if r.get("explicit_earlier_disabled_count", "0") not in {"", "0"})
    known = [r for r in grades if r.get("grade", "").upper() in {"PERFECT", "GREAT", "GOOD", "BAD", "MISS"}]
    slow = [r for r in known if r.get("grade", "").upper() == "SLOW" or r.get("direction", "").upper() == "SLOW"]
    # The review format can encode grade=GOOD and direction=SLOW; only this
    # manually labelled subset is eligible for a rate.
    slow_rate = len(slow) / len(known) if known else None
    experiment = run.get("experiment_id", "none")
    variant = run.get("variant", group)
    if variant == group and run.get("config"):
        variant = (((run.get("config") or {}).get("live") or {}).get("experiment") or {}).get("variant", variant)
    return {
        "run_dir": str(run_dir), "group": group, "variant": variant, "experiment_id": experiment,
        "input_lead_ms": run.get("experiment_input_lead_ms", (run.get("tap_timing_calibration") or {}).get("input_lead_ms", "")),
        "allow_earlier_amend": run.get("experiment_allow_earlier_amend", "UNKNOWN"),
        "processed_frames": run.get("processed_frames", ""), "capture_fps": run.get("capture_fps", ""),
        "processing_fps": run.get("wall_processing_fps", ""), "tap_key_downs": len(tap_downs),
        "hold_key_downs": sum(1 for r in actions if r.get("action") == "key_down" and r.get("note_type") == "hold"),
        "amend_actions": len(amend), "amend_uids": len({r.get("event_id") for r in amend}),
        "accepted_earlier_amend_actions": accepted_earlier,
        "accepted_later_amend_actions": accepted_later,
        "amend_delta_p50_ms": sorted(amendment_deltas)[len(amendment_deltas)//2] if amendment_deltas else "UNKNOWN",
        "explicit_earlier_disabled_uids": explicit, "grade_rows": len(grades),
        "known_grade_rows": len(known), "slow_grade_rows": len(slow),
        "slow_rate": slow_rate if slow_rate is not None else "UNKNOWN",
        "accuracy_status": "COMPARABLE" if len(known) >= 30 else "INSUFFICIENT_GROUND_TRUTH",
    }, grades


def compare(baseline_dirs, experiment_dirs, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries, grade_rows = [], []
    for group, dirs in (("baseline", baseline_dirs), ("experiment", experiment_dirs)):
        for run_dir in dirs:
            summary, grades = _run_summary(Path(run_dir), group)
            summaries.append(summary)
            for row in grades:
                grade_rows.append({"group": group, "run_dir": str(run_dir), **row})
    fields = list(summaries[0].keys()) if summaries else ["run_dir", "group", "variant", "accuracy_status"]
    with (out_dir / "v7147_ab_per_run.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(summaries)
    grade_fields = list(grade_rows[0].keys()) if grade_rows else ["group", "run_dir", "uid", "grade", "direction", "confidence"]
    with (out_dir / "v7147_grade_review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=grade_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(grade_rows)
    if not summaries:
        status = "AWAITING_USER_RUNS"
    elif any(row["accuracy_status"] != "COMPARABLE" for row in summaries):
        status = "INSUFFICIENT_GROUND_TRUTH"
    else:
        status = "COMPARABLE"
    report = [
        "# V7.14.7 A/B comparison", "", f"Status: **{status}**", "",
        "This comparison separates internal timing metrics from manually labelled game grades. key_down/FIRED/Combo are not game accuracy.",
        "The experiment differs from baseline only by `allow_earlier_amend`; lead remains 60 ms and all safety limits remain unchanged.", "",
        "## Runs",
    ]
    if summaries:
        for row in summaries:
            report.append(f"- {row['group']}: `{row['run_dir']}`; variant `{row['variant']}`; lead `{row['input_lead_ms']} ms`; earlier `{row['allow_earlier_amend']}`; Tap key-down {row['tap_key_downs']}; amendments {row['amend_actions']} (earlier {row['accepted_earlier_amend_actions']}, later {row['accepted_later_amend_actions']}, P50 delta {row['amend_delta_p50_ms']} ms); grades {row['known_grade_rows']}/{row['grade_rows']}; SLOW rate `{row['slow_rate']}`.")
    else:
        report.append("- No baseline or experiment runs supplied. Use the commands in the implementation report.")
    report += [
        "", "## Acceptance rule", 
        "Only if the same song segment has at least 30 one-to-one trusted labels per group may SLOW/MISS/FAST rates be compared. Otherwise the result stays INSUFFICIENT_GROUND_TRUTH and only internal timing metrics are reported.",
        "A failed or unsafe experiment must keep the baseline config; do not write the experiment setting into config/live_assist.json.",
    ]
    (out_dir / "v7147_ab_comparison.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"status": status, "runs": len(summaries), "output": str(out_dir)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="append", type=Path, default=[])
    parser.add_argument("--experiment", action="append", type=Path, default=[])
    parser.add_argument("--out-dir", type=Path, default=Path("output/analysis_v7147"))
    args = parser.parse_args()
    print(json.dumps(compare(args.baseline, args.experiment, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
