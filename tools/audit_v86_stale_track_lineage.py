#!/usr/bin/env python3
"""Audit last-observed component lineage for stale v86 candidate tracks.

This links recorded tracker input pixels to the corresponding segmentation
conversion row. It does not infer physical identity or causal root.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

TOLERANCE_SECONDS = 0.001
COMPONENT_FIELDS = ("component_id", "role", "color", "bbox", "area", "conversion",
                    "reason", "connection_group_id")


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def make_index(trace):
    tracker_rows = {}
    component_rows = {}
    for item in trace:
        if item.get("candidate_stage") == "tracker_input":
            tracker_rows.setdefault((item.get("provider"), item.get("tracker_uid")), []).append(item)
        elif item.get("candidate_stage") == "segmentation_to_detector":
            component_rows.setdefault((item.get("provider"), item.get("video_frame"), item.get("component_id")), []).append(item)
    return tracker_rows, component_rows


def resolve(row, trace, tolerance=TOLERANCE_SECONDS, index=None):
    """Resolve only a unique same-provider/UID, near-time observation at/before reference."""
    provider = row.get("provider", "")
    uid = row.get("candidate_tracker_uid_provider_local", "")
    ref_time = num(row.get("capture_timestamp"))
    obs_time = num(row.get("candidate_track_last_observation"))
    base = {"lineage_status": "unmatched", "matched_video_frame": "",
            "matched_source_frame": "", "matched_capture_timestamp": "",
            "stale_age_ms": row.get("last_observation_age_ms", "")}
    base.update({f"component_{field}": "" for field in COMPONENT_FIELDS})
    if not provider or not uid or ref_time is None or obs_time is None:
        return base
    # A last observation may be older, but must never come from after the reference.
    if obs_time > ref_time + 1e-12:
        base["lineage_status"] = "future_only_rejected"
        return base
    tracker_index, component_index = index if index is not None else make_index(trace)
    candidates = tracker_index.get((provider, uid), [])
    matches = []
    for t in candidates:
        ts = num(t.get("capture_timestamp"))
        if ts is not None and ts <= ref_time + 1e-12 and abs(ts - obs_time) <= tolerance:
            matches.append(t)
    if not matches:
        future_matches = []
        for t in candidates:
            ts = num(t.get("capture_timestamp"))
            if ts is not None and ts > ref_time + 1e-12 and abs(ts - obs_time) <= tolerance:
                future_matches.append(t)
        if future_matches:
            base["lineage_status"] = "future_only_rejected"
        return base
    if len(matches) > 1:
        base["lineage_status"] = "ambiguous_tracker_input"
        return base
    tracker = matches[0]
    frame = tracker.get("video_frame", "")
    comp_id = tracker.get("component_id", "")
    base.update(matched_video_frame=frame, matched_source_frame=tracker.get("source_frame", ""),
                matched_capture_timestamp=tracker.get("capture_timestamp", ""))
    if not comp_id:
        base["lineage_status"] = "missing_component_id"
        return base
    comps = component_index.get((provider, frame, comp_id), [])
    if not comps:
        base["lineage_status"] = "missing_component_conversion"
        base["component_component_id"] = comp_id
        return base
    if len(comps) > 1:
        base["lineage_status"] = "ambiguous_component_conversion"
        base["component_component_id"] = comp_id
        return base
    comp = comps[0]
    base["lineage_status"] = "matched"
    for field in COMPONENT_FIELDS:
        base[f"component_{field}"] = comp.get(field, "")
    return base


def build(audit_rows, trace_rows):
    index = make_index(trace_rows)
    rows = []
    for row in audit_rows:
        result = dict(row)
        result.update(resolve(row, trace_rows, index=index))
        rows.append(result)
    return rows


def summary(rows, audit_path, trace_path):
    by_provider = {}
    providers = sorted({r.get("provider", "") for r in rows})
    for provider in providers:
        group = [r for r in rows if r.get("provider") == provider]
        by_provider[provider] = {"rows": len(group),
            "exact_component_link_count": sum(r["lineage_status"] == "matched" for r in group),
            "missing_count": sum(r["lineage_status"] in ("unmatched", "missing_component_id", "missing_component_conversion", "future_only_rejected") for r in group),
            "ambiguous_count": sum(r["lineage_status"].startswith("ambiguous") for r in group)}
    return {"scope": "last observed pixel lineage only; no physical identity or causal root claim",
            "timestamp_tolerance_ms": 1,
            "inputs": {"unverified_trace_link_audit": {"path": str(audit_path), "sha256": sha256(audit_path)},
                       "candidate_trace": {"path": str(trace_path), "sha256": sha256(trace_path)}},
            "total_rows": len(rows), "exact_component_link_counts_by_provider": by_provider,
            "missing_count": sum(r["lineage_status"] in ("unmatched", "missing_component_id", "missing_component_conversion", "future_only_rejected") for r in rows),
            "ambiguous_count": sum(r["lineage_status"].startswith("ambiguous") for r in rows),
            "role_distribution": dict(sorted(Counter(r.get("component_role", "") or "(missing)" for r in rows if r["lineage_status"] == "matched").items())),
            "status_counts": dict(sorted(Counter(r["lineage_status"] for r in rows).items()))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit", type=Path, required=True)
    p.add_argument("--trace", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    args = p.parse_args()
    audit = read_csv(args.audit)
    trace = read_csv(args.trace)
    rows = build(audit, trace)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "stale_track_lineage_audit.csv"
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary_path = args.out_dir / "stale_track_lineage_summary.json"
    summary_path.write_text(json.dumps(summary(rows, args.audit, args.trace), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {csv_path} ({len(rows)} rows)")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
