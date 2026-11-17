"""Source-left / geometry-right review video. This module never modifies source."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np

from .video import VFRVideoWriter


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_comparison(source_video: Path, geometry_video: Path, frame_index_path: Path,
                    run_id: str, output_path: Path) -> dict:
    with frame_index_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["run_id"] == run_id]
    rows.sort(key=lambda r: int(r["video_frame"]))
    if not rows or [int(r["video_frame"]) for r in rows] != list(range(len(rows))):
        raise ValueError("frame index is empty or discontinuous")
    times = [float(r["acquired_elapsed_seconds"]) for r in rows]
    if times[0] != 0 or any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError("acquired timestamp timeline must start at 0 and increase strictly")
    src = cv2.VideoCapture(str(source_video)); geo = cv2.VideoCapture(str(geometry_video))
    if not src.isOpened() or not geo.isOpened():
        src.release(); geo.release()
        raise RuntimeError("could not decode source or geometry video")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_duration = times[-1] - times[-2] if len(times)>1 else 1/25
    write_ms=[]; mapped=[]; decoded=0
    try:
        with VFRVideoWriter(output_path, 2560, 720, final_duration, crf=22) as writer:
            for i,(row,t) in enumerate(zip(rows,times)):
                ok_s, sf = src.read(); ok_g, gf = geo.read()
                if not ok_s or not ok_g:
                    raise ValueError(f"decode ended before indexed frame {i}: source={ok_s}, geometry={ok_g}")
                if sf.shape[:2] != (720,1280) or gf.shape[:2] != (720,1280):
                    raise ValueError(f"unexpected comparison frame size at {i}: {sf.shape}, {gf.shape}")
                start=time.perf_counter()
                pts=writer.write(np.hstack((sf,gf)),t)
                write_ms.append((time.perf_counter()-start)*1000)
                mapped.append({"run_id":run_id,"output_frame":i,"source_video_frame":int(row["video_frame"]),
                               "source_mp4_pts_seconds":row["source_pts_seconds"],
                               "acquired_timestamp":row["acquired_timestamp"],
                               "geometry_frame":i,"comparison_pts_90k":pts,
                               "comparison_pts_seconds":pts/90_000,
                               "mapping_error_seconds":pts/90_000-t})
                decoded+=1
        ok_s,_=src.read();ok_g,_=geo.read()
        if ok_s or ok_g:
            raise ValueError("source/geometry has extra frames beyond index")
    finally:
        src.release();geo.release()
    mapping_path=output_path.with_name("comparison_frame_index.csv")
    with mapping_path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(mapped[0]));w.writeheader();w.writerows(mapped)
    errors=[abs(r["mapping_error_seconds"]) for r in mapped]
    summary={"run_id":run_id,"source_video_sha256":file_sha256(source_video),
             "geometry_video_sha256":file_sha256(geometry_video),
             "comparison_video_sha256":file_sha256(output_path),"frame_index_sha256":file_sha256(mapping_path),
             "source_decoded_frames":decoded,"geometry_decoded_frames":decoded,
             "comparison_frames":decoded,"dropped_or_extra_frames":0,"layout":"source_left_geometry_right",
             "resolution":[2560,720],"timebase":"acquired_timestamp_VFR_1/90000",
             "write_ms":{"mean":statistics.fmean(write_ms),"p50":statistics.median(write_ms),
                         "p95":sorted(write_ms)[int(.95*(len(write_ms)-1))],"max":max(write_ms)},
             "timestamp_error_seconds":{"max_abs":max(errors),"p95_abs":sorted(errors)[int(.95*(len(errors)-1))]}}
    output_path.with_name("comparison_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    return summary
