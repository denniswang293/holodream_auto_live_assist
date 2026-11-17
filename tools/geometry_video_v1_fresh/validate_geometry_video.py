from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.geometry_v1_fresh.inventory import inventory_recordings


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_entries", "stream=width,height,avg_frame_rate,nb_read_frames,duration",
               "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"no video stream in {path}")
    s = streams[0]
    return {"width": int(s["width"]), "height": int(s["height"]),
            "fps": s["avg_frame_rate"], "frames": int(s["nb_read_frames"]),
            "duration_s": float(s["duration"])}


def pts_values(path: Path) -> list[float]:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
               "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return [float(row["best_effort_timestamp_time"]) for row in json.loads(result.stdout).get("frames", [])]


def is_causal_instance_record(obj: dict) -> bool:
    """Accept the renderer's causal mode label and reject explicit lookahead."""
    return (str(obj.get("offline_mode", "")).startswith("CURRENT_FRAME_CAUSAL") and
            obj.get("future_frames_used", False) is False)


def validate_run(row: dict, root: Path, recording_root: Path) -> tuple[dict, list[dict]]:
    run_id = row["run"]
    source = recording_root / run_id
    target = root / run_id
    errors: list[str] = []
    issues: list[dict] = []
    video, index = source / "live_source.mp4", source / "live_video_index.csv"
    if sha256(video) != row["video_sha256"]: errors.append("source_video_hash_mismatch")
    if sha256(index) != row["index_sha256"]: errors.append("source_index_hash_mismatch")
    try:
        src_pts = pts_values(video)
        with index.open("r", newline="", encoding="utf-8-sig") as f:
            source_index = list(csv.DictReader(f))
        frame_path = target / "frame_index.csv"
        with frame_path.open("r", newline="", encoding="utf-8-sig") as f:
            frame_index = list(csv.DictReader(f))
        if len(src_pts) != row["decoded_video_frames"] or len(source_index) != len(src_pts):
            errors.append("source_pts_index_frame_count_mismatch")
        if len(frame_index) != len(src_pts): errors.append("output_frame_join_not_100_percent")
        for i, out in enumerate(frame_index):
            if i >= len(source_index) or i >= len(src_pts):
                errors.append("output_has_extra_frame_mapping"); break
            si = source_index[i]
            if int(out["output_frame"]) != i or int(out["source_frame"]) != int(float(si["source_frame"])):
                errors.append(f"frame_order_mismatch_at_{i}"); break
            if abs(float(out["video_pts_s"]) - src_pts[i]) > 1e-6:
                errors.append(f"source_pts_mismatch_at_{i}"); break
            for key in ("capture_timestamp", "acquired_timestamp", "elapsed_s", "encoded_at_host"):
                if abs(float(out[key]) - float(si[key])) > 1e-8:
                    errors.append(f"index_{key}_mismatch_at_{i}"); break
        if any(float(b["capture_timestamp"]) <= float(a["capture_timestamp"])
               for a, b in zip(frame_index, frame_index[1:])):
            errors.append("capture_timestamp_not_strictly_increasing")
        if any(float(b["video_pts_s"]) <= float(a["video_pts_s"])
               for a, b in zip(frame_index, frame_index[1:])):
            errors.append("source_pts_not_strictly_increasing")

        instance_path = target / "instances.jsonl"
        unknown_count = renderable_count = frame_count = 0
        with instance_path.open("r", encoding="utf-8") as f:
            for expected, line in enumerate(f):
                obj = json.loads(line); frame_count += 1
                if expected >= len(source_index):
                    errors.append("instances_have_extra_frame"); break
                if obj.get("frame") != expected or obj.get("source_frame") != int(float(source_index[expected]["source_frame"])):
                    errors.append(f"instances_frame_join_mismatch_at_{expected}"); break
                # The renderer's schema predates the redundant boolean and
                # records causality through offline_mode. Treat an omitted
                # future_frames_used as false, but reject an explicit true.
                if not is_causal_instance_record(obj):
                    errors.append(f"noncausal_instance_record_at_{expected}")
                for candidate in obj.get("candidates", []):
                    kind = candidate.get("type")
                    if kind not in ("TAP", "HOLD", "UNKNOWN"):
                        errors.append(f"invalid_candidate_type_at_{expected}"); continue
                    shape = candidate.get("pixel_mask_shape", [])
                    try:
                        packed = zlib.decompress(base64.b64decode(candidate["pixel_mask"]))
                        pixel_count = shape[0] * shape[1]
                        if len(packed) * 8 < pixel_count:
                            errors.append(f"short_pixel_evidence_at_{expected}")
                    except Exception:
                        errors.append(f"invalid_pixel_evidence_at_{expected}")
                    x, y, w, h = map(int, candidate["bbox"])
                    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1280 or y + h > 720:
                        errors.append(f"candidate_bounds_invalid_at_{expected}")
                    if kind == "UNKNOWN": unknown_count += 1
                    elif candidate.get("confidence", 0) >= .62 and candidate.get("pixel_evidence", {}).get("pixel_count", candidate.get("area_px", 0)) > 0:
                        renderable_count += 1
        if frame_count != len(src_pts): errors.append("instances_frame_count_mismatch")
        if not (target / "uncertain_candidates.csv").is_file(): errors.append("uncertain_review_queue_missing")
        if not (target / "independent_horizontal_audit.csv").is_file(): errors.append("independent_source_audit_missing")

        geom_meta = probe(target / "geometry.mp4")
        comp_meta = probe(target / "comparison.mp4")
        expected_n = len(src_pts)
        if geom_meta["frames"] != expected_n or (geom_meta["width"], geom_meta["height"]) != (1280, 720):
            errors.append("geometry_video_shape_or_count_mismatch")
        if comp_meta["frames"] != expected_n or (comp_meta["width"], comp_meta["height"]) != (2560, 720):
            errors.append("comparison_video_shape_or_count_mismatch")
        if not (target / "manifest.json").is_file() or not (target / "checksums.json").is_file():
            errors.append("manifest_or_checksums_missing")
        else:
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8-sig"))
            if manifest.get("source_video_sha256") != row["video_sha256"] or manifest.get("source_index_sha256") != row["index_sha256"]:
                errors.append("run_manifest_source_hash_mismatch")
            checksum_data = json.loads((target / "checksums.json").read_text(encoding="utf-8-sig"))
            for rel, digest in checksum_data.get("files", {}).items():
                path = target / rel
                if not path.is_file() or sha256(path) != digest:
                    errors.append(f"output_checksum_mismatch:{rel}")
                    break
    except Exception as exc:
        errors.append(f"validation_exception:{type(exc).__name__}:{exc}")

    try:
        with (target / "independent_horizontal_audit.csv").open("r", newline="", encoding="utf-8-sig") as f:
            for audit in csv.DictReader(f):
                if audit["status"] == "independent_unmatched_horizontal_evidence":
                    issues.append({"run_id": run_id, "source_frame": audit["source_frame"],
                                   "capture_timestamp": audit["capture_timestamp"],
                                   "issue_type": "independent_horizontal_panel_or_effect_unmatched",
                                   "source_crop_bbox": audit["bbox"], "geometry_crop_bbox": "",
                                   "confidence": "UNKNOWN", "root_cause": "possible visible panel/effect lacks overlapping color candidate",
                                   "fix": "", "rerun_status": "REVIEW_REQUIRED"})
    except Exception:
        pass

    qc = json.loads((target / "qc_summary.json").read_text(encoding="utf-8-sig")) if (target / "qc_summary.json").is_file() else {}
    result = {"run_id": run_id, "source_frames": int(row["decoded_video_frames"]),
              "output_frames": len(frame_index) if "frame_index" in locals() else 0,
              "geometry_frames": geom_meta["frames"] if "geom_meta" in locals() else 0,
              "comparison_frames": comp_meta["frames"] if "comp_meta" in locals() else 0,
              "mechanical_status": "PASS" if not errors else "FAIL",
              "errors": json.dumps(sorted(set(errors))),
              "tap_instances": qc.get("type_counts", {}).get("TAP", 0),
              "hold_instances": qc.get("type_counts", {}).get("HOLD", 0),
              "unknown_instances": qc.get("type_counts", {}).get("UNKNOWN", 0),
              "physical_note_precision_recall": "NOT_EVALUABLE_NO_INDEPENDENT_HUMAN_LABELS"}
    return result, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Independent mechanical validation for the fresh Geometry V1 pipeline")
    parser.add_argument("--root", type=Path, default=Path("output/geometry_video_v1/fresh_20261117"))
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    args = parser.parse_args()
    root = args.root.resolve(strict=True); recordings = args.recording_root.resolve(strict=True)
    inventory_path = root / "source_inventory" / "inventory.json"
    if not inventory_path.is_file(): raise SystemExit("fresh source inventory is missing")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))["runs"]
    if any(not row["frame_index_cardinality_matches"] or not all(row["index_monotonic"].values()) for row in inventory):
        raise SystemExit("source inventory has incomplete or nonmonotonic run/index rows")
    validation = root / "validation"; validation.mkdir(exist_ok=True)
    results, issues = [], []
    for row in inventory:
        if row.get("availability", "AVAILABLE") != "AVAILABLE":
            continue
        result, run_issues = validate_run(row, root, recordings)
        results.append(result); issues.extend(run_issues)
        print(f"{result['run_id']}: {result['mechanical_status']} ({result['output_frames']}/{result['source_frames']})")
    result_path = validation / "validation_results.csv"
    with result_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]) if results else ["run_id", "mechanical_status"])
        writer.writeheader(); writer.writerows(results)
    issue_path = validation / "issue_log.csv"
    fields = ["run_id", "source_frame", "capture_timestamp", "issue_type", "source_crop_bbox",
              "geometry_crop_bbox", "confidence", "root_cause", "fix", "rerun_status"]
    with issue_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(issues)
    metrics = json.loads((root / "geometry_calibration_metrics.json").read_text(encoding="utf-8-sig"))
    holdout_lines = ["# Fresh Geometry V1 holdout report", "",
                     "Status: `AUTO_VISUAL_REVIEWED_PROVISIONAL`; no independent human annotations exist.",
                     "The final two Runs were not used to fit rail geometry or detector thresholds.", ""]
    for item in metrics.get("holdout_results", []):
        holdout_lines += [f"## {item['run_id']}", "",
                          f"Boundary Hough inlier counts: `{item['boundary_inlier_counts']}`.",
                          f"Median absolute source-edge residuals (px): `{item['boundary_median_abs_error_px']}`.",
                          f"P95 absolute source-edge residuals (px): `{item['boundary_p95_abs_error_px']}`.", ""]
    (validation / "holdout_report.md").write_text("\n".join(holdout_lines), encoding="utf-8")
    failures = sum(r["mechanical_status"] != "PASS" for r in results)
    status = "PASS_MECHANICAL_PROVISIONAL" if results and failures == 0 else "NOT_COMPLETE_OR_FAILED"
    summary = {"status": status, "runs": len(results), "failed_runs": failures,
               "total_source_frames": sum(r["source_frames"] for r in results),
               "review_queue_independent_edge_rows": len(issues),
               "human_ground_truth": "NONE", "overall_acceptance": "REVIEW_REQUIRED",
               "source_recordings_modified": False, "live_or_keyboard_used": False}
    (validation / "validation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if status == "PASS_MECHANICAL_PROVISIONAL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
