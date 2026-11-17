"""Read-only inventory for the Geometry Scene V2 source recordings."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,codec_long_name,width,height,r_frame_rate,avg_frame_rate,time_base,duration,nb_frames,nb_read_frames,pix_fmt",
         "-show_entries", "format=duration,size,format_name", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    return {"stream": streams[0] if streams else {}, "format": data.get("format", {})}


def frame_pts(path: Path, ffprobe: str) -> list[tuple[float, float | None]]:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
         "frame=best_effort_timestamp_time,pkt_duration_time", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    output = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(",")
        if not parts or not parts[0]:
            continue
        try:
            output.append((float(parts[0]), float(parts[1]) if len(parts) > 1 and parts[1] else None))
        except ValueError:
            continue
    return output


def cadence(values: list[float]) -> dict[str, Any]:
    deltas = [b - a for a, b in zip(values, values[1:])]
    if not deltas:
        return {"samples": 0}
    median = statistics.median(deltas)
    return {"samples": len(deltas), "median_seconds": median, "min_seconds": min(deltas),
            "max_seconds": max(deltas), "max_abs_from_median_seconds": max(abs(x - median) for x in deltas),
            "intervals_gt_1_5x_median": sum(x > median * 1.5 for x in deltas)}


def index_stats(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"present": False}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    fields = reader.fieldnames or []
    numeric = {}
    for key in ("video_frame", "source_frame", "capture_timestamp", "acquired_timestamp"):
        if key not in fields:
            continue
        try:
            numeric[key] = [float(row[key]) for row in rows if row.get(key, "") != ""]
        except ValueError:
            numeric[key] = []
    stats: dict[str, Any] = {"present": True, "sha256": sha256(path), "rows": len(rows), "columns": fields}
    for key, values in numeric.items():
        stats[key] = {"first": values[0] if values else None, "last": values[-1] if values else None,
                      "strictly_increasing": all(a < b for a, b in zip(values, values[1:])),
                      "sample_count": len(values), "cadence": cadence(values)}
    if "capture_timestamp" in numeric and "acquired_timestamp" in numeric:
        stats["capture_acquired_delta_seconds"] = {
            "first": numeric["acquired_timestamp"][0] - numeric["capture_timestamp"][0],
            "median": sorted(b - a for a, b in zip(numeric["capture_timestamp"], numeric["acquired_timestamp"]))[len(rows)//2]
            if rows else None,
        }
    return stats


def build_inventory(recording_root: Path, ffprobe: str) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    videos = sorted(p for p in recording_root.rglob("*") if p.is_file() and p.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi"})
    rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {"schema_version": 1, "source_root": str(recording_root.resolve()), "files": []}
    frame_rows: list[dict[str, Any]] = []
    for video in videos:
        run_dir = video.parent
        index = run_dir / "live_video_index.csv"
        info = probe(video, ffprobe)
        stream, fmt = info["stream"], info["format"]
        idx = index_stats(index if index.exists() else None)
        pts_rows = frame_pts(video, ffprobe)
        decoded = int(stream.get("nb_read_frames") or 0)
        fps = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or ""
        timestamp_rows = idx.get("video_frame", {}).get("sample_count", 0)
        pts_values = [item[0] for item in pts_rows]
        pts_cadence = cadence(pts_values)
        vfr = ("CFR" if pts_cadence.get("samples") and pts_cadence.get("max_abs_from_median_seconds", 1) < 0.0005 else
               "VFR" if pts_cadence.get("samples") else "PTS_UNAVAILABLE")
        record = {
            "run_id": run_dir.name, "video": str(video.resolve()), "video_name": video.name,
            "video_bytes": video.stat().st_size, "video_sha256": sha256(video),
            "codec": stream.get("codec_name"), "codec_long_name": stream.get("codec_long_name"),
            "width": stream.get("width"), "height": stream.get("height"),
            "pixel_format": stream.get("pix_fmt"), "r_frame_rate": stream.get("r_frame_rate"),
            "avg_frame_rate": stream.get("avg_frame_rate"), "time_base": stream.get("time_base"),
            "duration_seconds": fmt.get("duration") or stream.get("duration"),
            "declared_frames": stream.get("nb_frames"), "decoded_frames": decoded,
            "index_rows": idx.get("rows"), "index_video_frame_samples": timestamp_rows,
            "index_frame_count_matches_decode": timestamp_rows == decoded,
            "index_sha256": idx.get("sha256"), "index_present": idx.get("present"),
            "capture_timestamp_first": idx.get("capture_timestamp", {}).get("first"),
            "capture_timestamp_last": idx.get("capture_timestamp", {}).get("last"),
            "acquired_timestamp_first": idx.get("acquired_timestamp", {}).get("first"),
            "acquired_timestamp_last": idx.get("acquired_timestamp", {}).get("last"),
            "capture_timestamps_monotonic": idx.get("capture_timestamp", {}).get("strictly_increasing"),
            "acquired_timestamps_monotonic": idx.get("acquired_timestamp", {}).get("strictly_increasing"),
            "timestamp_basis": "live_video_index capture/acquired host perf-counter; MP4 nominal fps is not substituted",
            "pts_rows": len(pts_rows), "pts_cadence": pts_cadence, "vfr_status": vfr,
            "decode_status": "DECODED" if decoded else "NO_DECODED_FRAMES",
        }
        if index.exists():
            with index.open("r", encoding="utf-8-sig", newline="") as stream_in:
                index_rows = list(csv.DictReader(stream_in))
            for i in range(max(len(index_rows), len(pts_rows))):
                ir = index_rows[i] if i < len(index_rows) else {}
                pts = pts_rows[i][0] if i < len(pts_rows) else None
                frame_rows.append({
                    "run_id": run_dir.name, "video_frame": ir.get("video_frame", i),
                    "source_frame": ir.get("source_frame", ""), "source_pts_seconds": pts,
                    "capture_timestamp": ir.get("capture_timestamp", ""),
                    "acquired_timestamp": ir.get("acquired_timestamp", ""),
                    "elapsed_s": ir.get("elapsed_s", ""), "encoded_at_host": ir.get("encoded_at_host", ""),
                    "index_row_present": i < len(index_rows), "pts_present": i < len(pts_rows),
                })
        rows.append(record)
        manifest["files"].append({**record, "index": idx, "probe": info})
    return rows, manifest, frame_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recording-root", type=Path, default=Path("output/recording"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refusing nonempty output directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    rows, manifest, frame_rows = build_inventory(args.recording_root.resolve(), args.ffprobe)
    with (out / "inventory.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    (out / "source_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if frame_rows:
        with (out / "frame_index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(frame_rows[0]))
            writer.writeheader()
            writer.writerows(frame_rows)
    print(json.dumps({"videos": len(rows), "decoded_frames": sum(r["decoded_frames"] for r in rows),
                      "all_index_counts_match": all(r["index_frame_count_matches_decode"] for r in rows),
                      "output": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
