"""Read-only mechanical validation for Geometry Video V1 run outputs.

The only write is the requested validation_summary.json under --root.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
from collections import Counter
import subprocess
import zlib
from pathlib import Path


REQUIRED_OUTPUTS = ("geometry.mp4", "comparison.mp4", "frame_index.csv",
                    "instances.jsonl", "uncertain_candidates.csv", "issue_log.csv",
                    "qc_summary.json", "checksums.json")
FORBIDDEN_NAME_PARTS = ("live", "input", "scheduler", "keyboard", "key_event")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
               "-show_entries", "stream=width,height,duration,nb_frames,nb_read_frames",
               "-of", "json", str(path)]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError("no decodable video stream")
    stream = streams[0]
    frames = int(stream.get("nb_read_frames") or stream.get("nb_frames") or 0)
    return {"width": int(stream["width"]), "height": int(stream["height"]),
            "frames": frames, "duration_s": float(stream["duration"])}


def issue(issues: list[str], text: str) -> None:
    if text not in issues:
        issues.append(text)


def validate_run(item: dict, root: Path, project_root: Path) -> dict:
    run_id = str(item.get("run_id", "<missing-run-id>"))
    issues: list[str] = []
    result: dict = {"run_id": run_id, "status": "NOT_COMPLETE", "issues": issues}
    if item.get("availability") != "AVAILABLE":
        issue(issues, f"inventory availability is {item.get('availability', 'missing')}")

    for label, key, expected_hash in (("source video", "video_path", item.get("video_sha256")),
                                      ("source index", "index_path", item.get("index_sha256"))):
        raw_path = item.get(key)
        if not raw_path or not expected_hash:
            issue(issues, f"inventory lacks {label} path/hash")
            continue
        source_path = Path(raw_path)
        if not source_path.is_absolute():
            source_path = project_root / source_path
        try:
            actual = sha256(source_path)
            result[f"{label.replace(' ', '_')}_sha256"] = actual
            if actual != expected_hash:
                issue(issues, f"{label} SHA-256 differs from inventory")
        except Exception as exc:
            issue(issues, f"{label} unavailable ({type(exc).__name__})")

    dest = root / run_id
    if not dest.is_dir():
        issue(issues, "run output directory is missing")
    for name in REQUIRED_OUTPUTS:
        if not (dest / name).is_file():
            issue(issues, f"missing {name}")
    if dest.is_dir():
        artifacts = [p.name for p in dest.iterdir() if any(token in p.name.lower() for token in FORBIDDEN_NAME_PARTS)]
        if artifacts:
            issue(issues, "unexpected input/Live-related artifact names: " + ", ".join(sorted(artifacts)[:8]))
        # The renderer's defined products must be pure geometry and source|geometry comparison.
        unexpected_videos = [p.name for p in dest.glob("*.mp4") if p.name not in
                             ("geometry.mp4", "comparison.mp4", "diagnostic_overlay.mp4")]
        if unexpected_videos:
            issue(issues, "unexpected video products: " + ", ".join(sorted(unexpected_videos)[:8]))

    geometry = comparison = None
    expected_frames = int(item.get("video", {}).get("nb_read_frames") or
                          item.get("video", {}).get("nb_frames") or 0)
    source_width = int(item.get("video", {}).get("width") or 0)
    source_height = int(item.get("video", {}).get("height") or 0)
    fps_text = item.get("video", {}).get("avg_frame_rate", "0/1")
    try:
        numerator, denominator = map(float, fps_text.split("/"))
        fps = numerator / denominator
    except Exception:
        fps = 0.0
    for name, dimensions in (("geometry.mp4", (source_width, source_height)),
                             ("comparison.mp4", (source_width * 2, source_height))):
        path = dest / name
        if path.is_file():
            try:
                info = probe(path)
                result[name] = info
                if (info["width"], info["height"]) != dimensions:
                    issue(issues, f"{name} dimensions are {info['width']}x{info['height']}, expected {dimensions[0]}x{dimensions[1]}")
                if info["frames"] != expected_frames:
                    issue(issues, f"{name} has {info['frames']} frames, expected {expected_frames}")
                source_duration = float(item.get("video", {}).get("duration", 0) or 0)
                if abs(info["duration_s"] - source_duration) > max(0.05, 1.5 / fps if fps else 0.05):
                    issue(issues, f"{name} duration differs from source")
                if name == "geometry.mp4": geometry = info
                else: comparison = info
            except Exception as exc:
                issue(issues, f"{name} probe failed ({type(exc).__name__})")

    index_rows: list[dict] = []
    index_path = dest / "frame_index.csv"
    if index_path.is_file():
        try:
            with index_path.open("r", newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                required = {"output_frame", "source_video_frame", "source_frame", "source_pts_s",
                            "output_pts_s", "capture_timestamp", "acquired_timestamp"}
                missing = sorted(required - set(reader.fieldnames or []))
                if missing: issue(issues, "frame_index.csv missing columns: " + ", ".join(missing))
                index_rows = list(reader)
            if len(index_rows) != expected_frames:
                issue(issues, f"frame_index.csv has {len(index_rows)} rows, expected {expected_frames}")
            out_ids=[]; source_ids=[]; srcframes=[]; captures=[]; acquired=[]; srcpts=[]; outpts=[]
            for row in index_rows:
                out_ids.append(int(row["output_frame"])); source_ids.append(int(row["source_video_frame"]))
                srcframes.append(int(row["source_frame"])); captures.append(float(row["capture_timestamp"]))
                acquired.append(float(row["acquired_timestamp"])); srcpts.append(float(row["source_pts_s"]))
                outpts.append(float(row["output_pts_s"]))
            if out_ids != list(range(len(index_rows))): issue(issues, "output frame IDs are not contiguous and zero-based")
            if source_ids != list(range(len(index_rows))) or srcframes != list(range(len(index_rows))):
                issue(issues, "source frame mapping is not one-to-one in source order")
            if not all(a < b for a,b in zip(captures,captures[1:])): issue(issues, "capture timestamps are not strictly increasing")
            if not all(a < b for a,b in zip(acquired,acquired[1:])): issue(issues, "acquired timestamps are not strictly increasing")
            if not all(a < b for a,b in zip(srcpts,srcpts[1:])): issue(issues, "source PTS values are not strictly increasing")
            if not all(a < b for a,b in zip(outpts,outpts[1:])): issue(issues, "output PTS values are not strictly increasing")
            pts_truth = item.get("video", {}).get("pts_time_values", [])
            if len(pts_truth) != len(index_rows):
                issue(issues, "inventory PTS count differs from frame index")
            elif any(abs(p-float(row["source_pts_s"])) > 1e-6 for p,row in zip(pts_truth,index_rows)):
                issue(issues, "frame_index source PTS does not map to inventory PTS")
            if fps and any(abs(t-i/fps) > 0.002 for i,t in enumerate(outpts)):
                issue(issues, "output PTS does not follow the source CFR frame mapping")
        except Exception as exc:
            issue(issues, f"frame_index.csv invalid ({type(exc).__name__})")

    instances_path = dest / "instances.jsonl"
    object_ids_all = []
    if instances_path.is_file():
        try:
            records = []
            with instances_path.open("r", encoding="utf-8-sig") as stream:
                for line_no, line in enumerate(stream, 1):
                    if line.strip():
                        records.append(json.loads(line))
            if len(records) != expected_frames:
                issue(issues, f"instances.jsonl has {len(records)} records, expected {expected_frames}")
            ids=[]
            for n, record in enumerate(records):
                if record.get("run_id") != run_id: issue(issues, f"instances run_id mismatch at record {n}")
                frame_id = record.get("frame_id")
                ids.append(frame_id)
                if frame_id != n: issue(issues, f"instances frame order mismatch at record {n}")
                for instance in record.get("instances", []):
                    iid = instance.get("instance_id")
                    if not iid or iid in ids: issue(issues, f"missing or duplicate instance ID at frame {n}")
                    ids.append(iid)
                    if instance.get("class") not in ("TAP", "HOLD"):
                        issue(issues, f"unsupported instance class at frame {n}")
                    evidence = instance.get("pixel_evidence")
                    try:
                        pixels = int(evidence["mask_pixel_count"])
                        bbox = instance["bbox"]
                        spans = evidence["mask_spans_rle"]
                        encoded = zlib.decompress(base64.b64decode(spans["data_base64"], validate=True))
                        if (spans.get("encoding") != "zlib-u16le-triplets-v1" or
                            len(encoded) != int(spans["run_count"])*6):
                            raise ValueError
                        if pixels <= 0 or len(bbox) != 4 or int(bbox[2]) <= 0 or int(bbox[3]) <= 0:
                            raise ValueError
                        if source_width and (int(bbox[0]) < 0 or int(bbox[1]) < 0 or
                            int(bbox[0])+int(bbox[2]) > source_width or int(bbox[1])+int(bbox[3]) > source_height):
                            raise ValueError
                    except Exception:
                        issue(issues, f"instance lacks valid in-frame pixel-supported evidence at frame {n}")
            # Frame IDs are separate from instance IDs; ensure unique object IDs independently.
            object_ids_all=[obj.get("instance_id") for rec in records for obj in rec.get("instances", [])]
            if None in object_ids_all or len(set(object_ids_all)) != len(object_ids_all): issue(issues, "instance IDs are missing or duplicated")
        except Exception as exc:
            issue(issues, f"instances.jsonl invalid ({type(exc).__name__})")

    uncertain_path = dest / "uncertain_candidates.csv"
    if uncertain_path.is_file():
        try:
            with uncertain_path.open("r", newline="", encoding="utf-8-sig") as stream:
                uncertain_rows = list(csv.DictReader(stream))
            uncertain_ids = set()
            for row in uncertain_rows:
                frame_no = int(row["frame_id"])
                bbox = json.loads(row["bbox"])
                confidence = float(row["confidence"])
                pixels = int(row["pixel_count"])
                if not 0 <= frame_no < expected_frames or len(bbox) != 4 or pixels <= 0 or not 0 <= confidence <= 1:
                    raise ValueError("invalid uncertainty evidence bounds")
                uncertain_ids.add(row["instance_id"])
            result["uncertain_candidate_rows"] = len(uncertain_rows)
            result["uncertain_candidate_unique_ids"] = len(uncertain_ids)
        except Exception as exc:
            issue(issues, f"uncertain_candidates.csv invalid ({type(exc).__name__})")

    issue_path = dest / "issue_log.csv"
    if issue_path.is_file():
        try:
            with issue_path.open("r", newline="", encoding="utf-8-sig") as stream:
                issue_rows = list(csv.DictReader(stream))
            reason_counts = Counter()
            for row in issue_rows:
                frame_no = int(row["frame_id"])
                if not 0 <= frame_no < expected_frames or not row.get("issue") or not row.get("instance_id"):
                    raise ValueError("invalid issue row bounds or identity")
                reason_counts[row["issue"]] += 1
            result["issue_log_rows"] = len(issue_rows)
            qc_file = dest / "qc_summary.json"
            if qc_file.is_file():
                qc_summary = json.loads(qc_file.read_text(encoding="utf-8-sig"))
                if dict(reason_counts) != qc_summary.get("uncertainty_reason_counts", {}):
                    issue(issues, "issue_log reason totals differ from qc_summary")
        except Exception as exc:
            issue(issues, f"issue_log.csv invalid ({type(exc).__name__})")

    for name in REQUIRED_OUTPUTS:
        path = dest / name
        if path.is_file() and name not in ("checksums.json",):
            pass
    checksum_path = dest / "checksums.json"
    if checksum_path.is_file():
        try:
            checksums = json.loads(checksum_path.read_text(encoding="utf-8-sig"))
            for name in ("geometry.mp4", "comparison.mp4", "frame_index.csv", "instances.jsonl",
                         "uncertain_candidates.csv", "issue_log.csv", "qc_summary.json"):
                path = dest / name
                if path.is_file() and checksums.get(name) != sha256(path):
                    issue(issues, f"checksums.json mismatch for {name}")
            if checksums.get("source_video_sha256") != item.get("video_sha256"):
                issue(issues, "checksums.json source video hash differs from inventory")
            if checksums.get("source_index_sha256") != item.get("index_sha256"):
                issue(issues, "checksums.json source index hash differs from inventory")
        except Exception as exc:
            issue(issues, f"checksums.json invalid ({type(exc).__name__})")

    qc_path = dest / "qc_summary.json"
    if qc_path.is_file():
        try:
            qc = json.loads(qc_path.read_text(encoding="utf-8-sig"))
            if qc.get("run_id") != run_id: issue(issues, "qc_summary run_id mismatch")
            if qc.get("source_sha256") != item.get("video_sha256"): issue(issues, "qc_summary source hash differs from inventory")
            if int(qc.get("frames", -1)) != expected_frames: issue(issues, "qc_summary frame count differs from inventory")
            if qc.get("decode_failures", 0) != 0: issue(issues, "qc_summary reports decode failures")
            if qc.get("physical_note_precision_recall") != "NOT_EVALUABLE_NO_INDEPENDENT_HUMAN_LABELS":
                issue(issues, "qc_summary overstates physical-note evaluation")
            if qc.get("visual_review") != "AUTO_VISUAL_REVIEWED_PROVISIONAL":
                issue(issues, "qc_summary review status is missing or overstates human review")
        except Exception as exc:
            issue(issues, f"qc_summary.json invalid ({type(exc).__name__})")
    if not issues:
        result["status"] = "PASS_MECHANICAL_PROVISIONAL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("output/geometry_video_v1"))
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    summary = {"validator": "Geometry Video V1 mechanical validator", "status": "NOT_COMPLETE",
               "runs": [], "available_runs": 0}
    inventory_path = root / "inventory.json"
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
        if not isinstance(inventory, list): raise ValueError("inventory root must be an array")
    except Exception as exc:
        summary["issues"] = [f"inventory unavailable or invalid ({type(exc).__name__})"]
        inventory = []
    if inventory:
        available = [item for item in inventory if item.get("availability") == "AVAILABLE"]
        summary["available_runs"] = len(available)
        project_root = root.parent.parent
        summary["runs"] = [validate_run(item, root, project_root) for item in available]
        unavailable = [item.get("run_id", "<unknown>") for item in inventory if item.get("availability") != "AVAILABLE"]
        summary["unavailable_runs"] = unavailable
        if not available:
            summary.setdefault("issues", []).append("inventory contains no AVAILABLE runs")
        elif all(run["status"] == "PASS_MECHANICAL_PROVISIONAL" for run in summary["runs"]):
            summary["status"] = "PASS_MECHANICAL_PROVISIONAL" if not unavailable else "NOT_COMPLETE"
        if unavailable:
            summary.setdefault("issues", []).append(f"{len(unavailable)} inventory run(s) are not AVAILABLE")
    summary["run_count"] = len(summary["runs"])
    summary_path = root / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    failed = sum(run["status"] != "PASS_MECHANICAL_PROVISIONAL" for run in summary["runs"])
    print(f"{summary['status']}: {summary['run_count']} available run(s), {failed} incomplete/failed; summary={summary_path}")
    return 0 if summary["status"] == "PASS_MECHANICAL_PROVISIONAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
