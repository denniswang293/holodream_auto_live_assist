"""Capture-time timing calibration helper for V7.14.2.

This tool compares explicit input-lead candidates against the visual physical
line crossing proxy in an existing run.  It never treats a key_down as a game
judgement and never sends input.  If a source video or labelled FAST/SLOW
result is unavailable, the report remains UNKNOWN.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path


def _rows(path):
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _center_y(raw_bbox):
    try:
        x, y, w, h = json.loads(raw_bbox)
        return float(y) + float(h) / 2.0
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _percentile(values, q):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * q
    lower, upper = math.floor(index), math.ceil(index)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (index - lower)


def crossing_time(observations, target_y):
    observations = sorted(observations)
    for (t0, y0), (t1, y1) in zip(observations, observations[1:]):
        if y0 <= target_y <= y1 and t1 > t0 and y1 > y0:
            fraction = (target_y - y0) / (y1 - y0)
            return t0 + fraction * (t1 - t0)
    # The Simple tracker normally retires a Tap before the physical line is
    # rendered.  A bounded last-segment extrapolation is useful as a visual
    # proxy, but is explicitly labelled as such rather than treated as truth.
    if len(observations) >= 3 and observations[-1][1] < target_y:
        recent = observations[-3:]
        speeds = [(y1 - y0) / (t1 - t0)
                  for (t0, y0), (t1, y1) in zip(recent, recent[1:])
                  if t1 > t0 and y1 > y0]
        if speeds:
            speed = sorted(speeds)[len(speeds) // 2]
            if speed > 0 and target_y - observations[-1][1] <= 60:
                t_last, y_last = observations[-1]
                return t_last + (target_y - y_last) / speed
    return None


def analyze(run_dir: Path, *, physical_y=325.5, trigger_y=295.5,
            leads=(0.0, 30.0, 60.0, 90.0)):
    identity_path = run_dir / "live_track_identity.csv"
    action_path = run_dir / "input_actions.csv"
    if not identity_path.exists():
        raise FileNotFoundError(identity_path)
    identity = _rows(identity_path)
    actions = _rows(action_path) if action_path.exists() else []
    by_uid = defaultdict(list)
    for row in identity:
        if str(row.get("matched_this_frame", "")).lower() != "true":
            continue
        if row.get("confirmed_note_type") not in {"tap", ""} and row.get("track_status") not in {"confirmed", "tentative"}:
            continue
        ts, y = _float(row.get("capture_timestamp")), _center_y(row.get("bbox", ""))
        if ts is not None and y is not None:
            by_uid[row.get("note_uid") or row.get("track_uid")].append((ts, y))
    crossings = {}
    for uid, observations in by_uid.items():
        physical = crossing_time(observations, physical_y)
        trigger = crossing_time(observations, trigger_y)
        if physical is not None:
            crossings[uid] = {"physical_cross_at": physical,
                              "trigger_cross_at": trigger,
                              "observations": len(observations)}
    downs = {}
    for row in actions:
        if row.get("action") != "key_down" or row.get("note_type") not in {"tap", ""}:
            continue
        uid = row.get("event_id", "")
        ts = _float(row.get("timestamp"))
        if uid and ts is not None and uid not in downs:
            downs[uid] = {"key_down_at": ts, "key": row.get("key", "")}
    result_rows = []
    for uid, data in crossings.items():
        action = downs.get(uid, {})
        for lead_ms in leads:
            expected_press = data["physical_cross_at"] - lead_ms / 1000.0
            key_down_at = action.get("key_down_at")
            result_rows.append({
                "note_uid": uid,
                "observations": data["observations"],
                "physical_cross_at": data["physical_cross_at"],
                "trigger_cross_at": data["trigger_cross_at"] or "",
                "physical_crossing_basis": ("observed_or_interpolated"
                    if max(y for _, y in by_uid[uid]) >= physical_y
                    else "bounded_last_segment_extrapolation"),
                "lead_ms": lead_ms,
                "expected_press_at": expected_press,
                "key_down_at": key_down_at or "",
                "key_down_minus_expected_ms": ((key_down_at - expected_press) * 1000
                    if key_down_at is not None else ""),
                "key": action.get("key", ""),
                "game_judgement": "UNKNOWN",
            })
    output_csv = run_dir / "v7142_timing_lead_comparison.csv"
    fields = list(result_rows[0]) if result_rows else [
        "note_uid", "observations", "physical_cross_at", "trigger_cross_at",
        "physical_crossing_basis", "lead_ms", "expected_press_at", "key_down_at",
        "key_down_minus_expected_ms", "key", "game_judgement"]
    with output_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result_rows)
    errors = defaultdict(list)
    for row in result_rows:
        value = _float(row.get("key_down_minus_expected_ms"))
        if value is not None:
            errors[float(row["lead_ms"])].append(value)
    report = run_dir / "v7142_timing_calibration.md"
    lines = ["# V7.14.2 timing calibration", "", f"Run: `{run_dir}`", "",
             f"Physical crossing proxy Y: `{physical_y}`; legacy trigger Y: `{trigger_y}`",
             "", f"UIDs with capture-time physical crossing proxy: **{len(crossings)}**",
             "", "No independent FAST/SLOW/game judgement labels were available; game result is **UNKNOWN**.", "",
             "| lead_ms | paired key-down rows | median key-down minus expected (ms) | P90 absolute (ms) |",
             "|---:|---:|---:|---:|"]
    for lead in leads:
        values = errors[float(lead)]
        absolute = [abs(value) for value in values]
        lines.append(f"| {lead:g} | {len(values)} | "
                     f"{(_percentile(values, .5) if values else 'UNKNOWN')} | "
                     f"{(_percentile(absolute, .9) if absolute else 'UNKNOWN')} |")
    lines += ["", "These are visual/capture-time proxy comparisons only, not game accuracy.",
              f"Output CSV: `{output_csv.name}`"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"run_dir": str(run_dir), "physical_crossing_uids": len(crossings),
            "rows": len(result_rows), "csv": str(output_csv), "report": str(report)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--physical-y", type=float, default=325.5)
    parser.add_argument("--trigger-y", type=float, default=295.5)
    parser.add_argument("--leads-ms", type=float, nargs="+", default=[0.0, 30.0, 60.0, 90.0])
    args = parser.parse_args()
    print(json.dumps(analyze(args.run_dir, physical_y=args.physical_y,
                              trigger_y=args.trigger_y, leads=args.leads_ms), indent=2))


if __name__ == "__main__":
    main()
