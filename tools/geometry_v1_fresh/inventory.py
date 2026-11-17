"""Read-only inventory of recorded source videos for Geometry Video V1.

The scanner intentionally reads only ``output/recording/run_*/`` video and
video-index files. Index timestamps are host/session monotonic values, not
wall-clock timestamps.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


INDEX_FIELDS = (
    "video_frame",
    "source_frame",
    "capture_timestamp",
    "acquired_timestamp",
    "elapsed_s",
    "encoded_at_host",
)
TIMESTAMP_CAVEAT = (
    "Index timestamps are host/session monotonic values, not wall-clock timestamps."
)
OUTPUT_FILES = ("inventory.csv", "inventory.md", "inventory.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    """Probe metadata and decode-count the selected video stream incrementally."""
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-count_frames",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"No video stream found in {path}")
    stream = streams[0]
    count = stream.get("nb_read_frames")
    if count in (None, "N/A"):
        raise ValueError(f"ffprobe did not return a decoded frame count for {path}")
    return {
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "nominal_fps": stream.get("r_frame_rate"),
        "average_fps": stream.get("avg_frame_rate"),
        "decoded_video_frames": int(count),
        "duration_s": float(stream["duration"]) if stream.get("duration") not in (None, "N/A") else None,
    }


def _read_index(path: Path) -> tuple[int, dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        missing = [name for name in INDEX_FIELDS if name not in headers]
        if missing:
            raise ValueError(f"{path} is missing required columns: {', '.join(missing)}")
        count = 0
        previous: dict[str, float] = {}
        first: dict[str, float] = {}
        nonincreasing = {name: 0 for name in INDEX_FIELDS}
        for row_number, row in enumerate(reader, start=2):
            count += 1
            for name in INDEX_FIELDS:
                try:
                    value = float(row[name])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid {name} at {path}:{row_number}") from exc
                if count == 1:
                    first[name] = value
                elif value <= previous[name]:
                    nonincreasing[name] += 1
                previous[name] = value
        if not count:
            raise ValueError(f"Index has no data rows: {path}")
    monotonic = {name: nonincreasing[name] == 0 for name in INDEX_FIELDS}
    coverage = {
        name: {"first": first[name], "last": previous[name]}
        for name in INDEX_FIELDS
    }
    return count, {
        "index_monotonic": monotonic,
        "index_nonincreasing_counts": nonincreasing,
        "index_coverage": coverage,
    }


def inventory_recordings(
    recording_root: str | Path = "output/recording",
    *,
    ffprobe: str | None = None,
) -> list[dict[str, Any]]:
    """Inventory only run directories' live video and video-index files."""
    executable = ffprobe or shutil.which("ffprobe")
    if not executable:
        raise FileNotFoundError("ffprobe was not found; install FFmpeg or pass ffprobe=")
    root = Path(recording_root)
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(root.glob("run_*")):
        if not run_dir.is_dir():
            continue
        video = run_dir / "live_source.mp4"
        index = run_dir / "live_video_index.csv"
        if not video.is_file() or not index.is_file():
            continue
        probe = _probe_video(video, executable)
        index_rows, index_info = _read_index(index)
        rows.append({
            "run": run_dir.name,
            "video_file": video.name,
            "index_file": index.name,
            "video_bytes": video.stat().st_size,
            "index_bytes": index.stat().st_size,
            "video_sha256": _sha256(video),
            "index_sha256": _sha256(index),
            **probe,
            "index_rows": index_rows,
            "frame_index_cardinality_matches": index_rows == probe["decoded_video_frames"],
            **index_info,
            "timestamp_caveat": TIMESTAMP_CAVEAT,
        })
    if not rows:
        raise FileNotFoundError(f"No run directories with both source files under {root}")
    return rows


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_inventory(rows: Iterable[dict[str, Any]], output_dir: str | Path) -> list[Path]:
    """Write CSV, Markdown, and JSON into an explicitly selected fresh folder."""
    rows = list(rows)
    destination = Path(output_dir)
    if destination.exists() and not destination.is_dir():
        raise FileExistsError(f"Output path is not a directory: {destination}")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Refusing nonempty output directory: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    targets = [destination / name for name in OUTPUT_FILES]
    conflicts = [path.name for path in targets if path.exists()]
    if conflicts:
        raise FileExistsError(f"Refusing to overwrite: {', '.join(conflicts)}")

    columns = list(rows[0]) if rows else []
    with targets[0].open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: _csv_value(value) for key, value in row.items()} for row in rows)
    targets[1].write_text(_markdown(rows), encoding="utf-8")
    targets[2].write_text(json.dumps({"timestamp_caveat": TIMESTAMP_CAVEAT, "runs": rows}, indent=2) + "\n", encoding="utf-8")
    return targets


def _markdown(rows: list[dict[str, Any]]) -> str:
    headers = ("run", "video_file", "index_file", "decoded_video_frames", "index_rows", "duration_s", "video_bytes", "video_sha256", "index_sha256", "frame_index_cardinality_matches")
    lines = ["# Fresh source inventory", "", TIMESTAMP_CAVEAT, "", "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = [str(row.get(header, "")).replace("|", "\\|") for header in headers]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recording-root", default="output/recording", help="Source recording root (default: output/recording)")
    parser.add_argument("--ffprobe", help="ffprobe executable; defaults to PATH lookup")
    parser.add_argument("--output", required=True, help="Fresh output directory for inventory.csv/md/json")
    args = parser.parse_args(argv)
    try:
        rows = inventory_recordings(args.recording_root, ffprobe=args.ffprobe)
        paths = write_inventory(rows, args.output)
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"inventory: {exc}", file=sys.stderr)
        return 2
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
