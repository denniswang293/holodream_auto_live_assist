"""Read-only inventory and SHA-256 verification for geometry video sources."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def video_info(path: Path) -> dict:
    command = [
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,time_base,nb_frames,nb_read_frames,duration,pix_fmt",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    streams = json.loads(completed.stdout).get("streams", [])
    if not streams:
        raise RuntimeError("No decodable video stream")
    info = streams[0]
    pts_command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
                   "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path)]
    pts_completed = subprocess.run(pts_command, check=True, capture_output=True, text=True)
    pts = [float(frame["best_effort_timestamp_time"])
           for frame in json.loads(pts_completed.stdout).get("frames", [])
           if "best_effort_timestamp_time" in frame]
    intervals = [b-a for a, b in zip(pts, pts[1:])]
    median_interval = sorted(intervals)[len(intervals)//2] if intervals else None
    info["pts_frame_count"] = len(pts)
    info["pts_first_last"] = [pts[0], pts[-1]] if pts else None
    info["pts_strictly_increasing"] = all(a < b for a, b in zip(pts, pts[1:]))
    info["pts_median_interval_s"] = median_interval
    info["pts_cfr_within_1ms"] = bool(intervals) and all(abs(delta-median_interval) <= .001 for delta in intervals)
    info["pts_time_values"] = pts
    return info


def index_info(path: Path) -> dict:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        rows = list(reader)
    required = {"video_frame", "source_frame", "capture_timestamp", "acquired_timestamp"}
    missing = sorted(required.difference(fields))
    indices = [int(row["video_frame"]) for row in rows]
    source_frames = [int(row["source_frame"]) for row in rows]
    capture = [float(row["capture_timestamp"]) for row in rows]
    acquired = [float(row["acquired_timestamp"]) for row in rows]
    return {
        "rows": len(rows), "fields": fields, "missing_fields": missing,
        "video_frame_first_last": [indices[0], indices[-1]] if indices else None,
        "video_frame_contiguous_zero_based": indices == list(range(len(indices))),
        "source_frame_first_last": [source_frames[0], source_frames[-1]] if source_frames else None,
        "capture_timestamp_first_last": [capture[0], capture[-1]] if capture else None,
        "capture_timestamp_strictly_increasing": all(a < b for a, b in zip(capture, capture[1:])),
        "acquired_timestamp_strictly_increasing": all(a < b for a, b in zip(acquired, acquired[1:])),
        "max_capture_interval_s": max((b - a for a, b in zip(capture, capture[1:])), default=None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, default=Path("output/geometry_video_v1"))
    args = parser.parse_args()
    root = args.input_root.resolve(strict=True)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for run in sorted(root.glob("run_*")):
        if not run.is_dir():
            continue
        video = run / "live_source.mp4"
        index = run / "live_video_index.csv"
        session_path = run / "session.json"
        item = {"run_id": run.name, "video_path": str(video.relative_to(root.parent.parent)),
                "index_path": str(index.relative_to(root.parent.parent))}
        try:
            item["video"] = video_info(video)
            item["index"] = index_info(index)
            item["session"] = json.loads(session_path.read_text(encoding="utf-8-sig"))
            item["source_files"] = [
                {"path": str(path.relative_to(root.parent.parent)), "bytes": path.stat().st_size,
                 "sha256": sha256(path)}
                for path in sorted(run.iterdir()) if path.is_file()
            ]
            item["video_sha256"] = sha256(video)
            item["index_sha256"] = sha256(index)
            item["session_sha256"] = sha256(session_path)
            item["video_index_frame_count_match"] = (
                int(item["video"].get("nb_read_frames") or item["video"].get("nb_frames") or -1)
                == item["index"]["rows"]
            )
            item["availability"] = "AVAILABLE" if item["video_index_frame_count_match"] else "FRAME_COUNT_MISMATCH"
        except Exception as error:  # inventory must retain failures as rows
            item["availability"] = "UNAVAILABLE"
            item["error"] = f"{type(error).__name__}: {error}"
        rows.append(item)
        print(f"{run.name}: {item['availability']}", flush=True)

    (out / "inventory.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    columns = ["run_id", "availability", "codec_name", "width", "height", "r_frame_rate",
               "avg_frame_rate", "time_base", "duration", "nb_read_frames", "index_rows",
               "video_index_frame_count_match", "capture_timestamp_strictly_increasing",
               "max_capture_interval_s", "video_sha256", "index_sha256", "session_sha256", "error"]
    with (out / "inventory.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for item in rows:
            video = item.get("video", {})
            index = item.get("index", {})
            writer.writerow({
                "run_id": item["run_id"], "availability": item["availability"],
                **{key: video.get(key, "") for key in ("codec_name", "width", "height", "r_frame_rate", "avg_frame_rate", "time_base", "duration", "nb_read_frames")},
                "index_rows": index.get("rows", ""),
                "video_index_frame_count_match": item.get("video_index_frame_count_match", ""),
                "capture_timestamp_strictly_increasing": index.get("capture_timestamp_strictly_increasing", ""),
                "max_capture_interval_s": index.get("max_capture_interval_s", ""),
                "video_sha256": item.get("video_sha256", ""), "index_sha256": item.get("index_sha256", ""),
                "session_sha256": item.get("session_sha256", ""), "error": item.get("error", ""),
            })
    print(f"Wrote {out / 'inventory.csv'} and inventory.json ({len(rows)} runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
