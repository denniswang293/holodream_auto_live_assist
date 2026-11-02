"""Offline V7.14.1 Global ETA profile comparison.

This tool consumes recorded matched observations only.  It never reads PF ETA
fields, never sends input, and never uses an observation after the prediction
timestamp when building a UID hold-out estimate.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
from pathlib import Path
from statistics import median
from collections import defaultdict


TRIGGER_Y = 295.5
EDGES = tuple(TRIGGER_Y * fraction for fraction in (0.0, .30, .55, .78, 1.0))


def _float(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _bbox_y(value):
    try:
        box = ast.literal_eval(value) if isinstance(value, str) else value
        return float(box[1]) + float(box[3]) / 2.0
    except (TypeError, ValueError, SyntaxError, IndexError, KeyError):
        return None


def _segment(y):
    for index in range(len(EDGES) - 1):
        if EDGES[index] <= y < EDGES[index + 1]:
            return index
    return None


def _observations(path):
    groups = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("matched_this_frame", "").lower() not in {"true", "1"} and \
                    row.get("real_observation_this_frame", "").lower() not in {"true", "1"}:
                continue
            uid = row.get("note_uid") or row.get("track_uid")
            timestamp = _float(row.get("capture_timestamp"))
            y = _bbox_y(row.get("bbox", ""))
            if not uid or timestamp is None or y is None:
                continue
            groups.setdefault(uid, []).append((timestamp, y))
    for uid in groups:
        groups[uid] = sorted(set(groups[uid]))
    return groups


def _slopes(observations):
    values = []
    for (t0, y0), (t1, y1) in zip(observations, observations[1:]):
        dt, dy = t1 - t0, y1 - y0
        if 0 < dt <= .2 and 0 < dy <= 35:
            speed = dy / dt
            if 20 <= speed <= 750:
                values.append(((y0 + y1) / 2.0, speed))
    return values


def _profile(samples):
    by_segment = {}
    for y, speed in samples:
        segment = _segment(y)
        if segment is not None:
            by_segment.setdefault(segment, []).append(speed)
    return {segment: (float(median(values)), len(values))
            for segment, values in by_segment.items() if values}


def _integral(observed_y, profile):
    if not profile or observed_y >= TRIGGER_Y:
        return None
    total = 0.0
    for index in range(len(EDGES) - 1):
        left, right = max(observed_y, EDGES[index]), min(TRIGGER_Y, EDGES[index + 1])
        if right <= left:
            continue
        if index in profile:
            speed = profile[index][0]
        else:
            nearest = min(profile, key=lambda item: abs(item - index))
            speed = profile[nearest][0]
        if speed <= 0:
            return None
        total += (right - left) / speed
    return total if math.isfinite(total) else None


def _crossing(observations):
    for (t0, y0), (t1, y1) in zip(observations, observations[1:]):
        if y0 < TRIGGER_Y <= y1 and t1 > t0:
            fraction = (TRIGGER_Y - y0) / (y1 - y0)
            return t0 + fraction * (t1 - t0)
    return None


def run(run_dir: Path):
    identity = run_dir / "live_track_identity.csv"
    if not identity.exists():
        raise FileNotFoundError(identity)
    groups = _observations(identity)
    rows = []
    evidence = defaultdict(list)
    for uid, observations in groups.items():
        if len(observations) < 6:
            continue
        split = max(3, int(len(observations) * .7))
        train, validation = observations[:split], observations[split:]
        if not train or not validation:
            continue
        train_samples = _slopes(train)
        for sample_y, speed in train_samples:
            segment = _segment(sample_y)
            if segment is not None:
                evidence[segment].append((uid, speed))
        baseline_speed = median(speed for _, speed in train_samples) if train_samples else None
        profile = _profile(train_samples)
        observed_cross = _crossing(observations)
        if observed_cross is None:
            continue
        observed_at, observed_y = train[-1]
        baseline_eta = ((TRIGGER_Y - observed_y) / baseline_speed
                        if baseline_speed and observed_y < TRIGGER_Y else None)
        profile_eta = _integral(observed_y, profile)
        rows.append({
            "note_uid": uid,
            "observations": len(observations),
            "train_observations": len(train),
            "profile_segments": len(profile),
            "observed_cross_at": observed_cross,
            "baseline_hit_at": observed_at + baseline_eta if baseline_eta else "",
            "profile_hit_at": observed_at + profile_eta if profile_eta else "",
            "baseline_error_s": (observed_at + baseline_eta - observed_cross
                                  if baseline_eta else ""),
            "profile_error_s": (observed_at + profile_eta - observed_cross
                                if profile_eta else ""),
        })
    global_rows = []
    global_path = run_dir / "global_tap_timing_shadow.csv"
    if global_path.exists():
        with global_path.open(encoding="utf-8-sig", newline="") as stream:
            global_rows = list(csv.DictReader(stream))
    run_json = json.loads((run_dir / "live_run.json").read_text(encoding="utf-8")) \
        if (run_dir / "live_run.json").exists() else {}
    evidence_rows = []
    for segment in range(len(EDGES) - 1):
        values = evidence.get(segment, [])
        speeds = [speed for _, speed in values]
        evidence_rows.append({
            "segment": segment,
            "y_min": EDGES[segment],
            "y_max": EDGES[segment + 1],
            "pair_count": len(values),
            "unique_uid_count": len({uid for uid, _ in values}),
            "speed_median_px_s": median(speeds) if speeds else "",
            "speed_mad_px_s": median([abs(speed - median(speeds)) for speed in speeds]) if speeds else "",
        })
    return rows, global_rows, run_json, evidence_rows


def _summary(rows):
    result = {"eligible_uids": len(rows)}
    for name in ("baseline_error_s", "profile_error_s"):
        values = sorted(abs(float(row[name])) for row in rows if row[name] != "")
        result[f"{name}_p50_s"] = values[len(values) // 2] if values else None
        result[f"{name}_p90_s"] = values[min(len(values) - 1, int(len(values) * .9))] if values else None
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    rows, global_rows, run_json, evidence_rows = run(args.run_dir)
    out = args.out or args.run_dir
    out.mkdir(parents=True, exist_ok=True)
    with (out / "v7141_global_profile_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = list(rows[0]) if rows else ["note_uid"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with (out / "v7141_profile_velocity_evidence.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = list(evidence_rows[0]) if evidence_rows else ["segment"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(evidence_rows)
    summary = _summary(rows)
    ready = sum(row.get("model_status") == "ready" for row in global_rows)
    summary.update({
        "run_dir": str(args.run_dir),
        "global_rows": len(global_rows),
        "recorded_global_ready_frame_rows": ready,
        "recorded_global_ready_ratio": ready / len(global_rows) if global_rows else None,
        "tap_timing_source": run_json.get("tap_timing_source", "UNKNOWN"),
        "accuracy": "UNKNOWN",
    })
    (out / "v7141_global_profile_comparison.md").write_text(
        "# V7.14.1 Global ETA offline comparison\n\n" +
        "This is a capture-time UID hold-out proxy, not game HIT/MISS truth.\n\n" +
        "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n",
        encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
