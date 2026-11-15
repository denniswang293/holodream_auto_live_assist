"""Render an inclusive, indexed frame window for offline visual inspection."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys, time
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lane_filter import LaneFilter, MASK_CHANNELS, PREVIEW_COLORS, ROLE_MASK  # noqa:E402
from src.model import Geometry  # noqa:E402


def validate_range(start: int, end: int) -> None:
    if start < 0 or end < start:
        raise ValueError("frame window must satisfy 0 <= start <= end")


def index_row(index: dict[int, dict[str, str]], video_frame: int) -> dict[str, str]:
    row = index.get(video_frame)
    if row is None:
        raise ValueError(f"missing video_frame={video_frame} in index")
    if int(row["video_frame"]) != video_frame:
        raise ValueError(f"index key mismatch at video_frame={video_frame}")
    if int(row["source_frame"]) < 0:
        raise ValueError(f"invalid source_frame at video_frame={video_frame}")
    captured, acquired = float(row["capture_timestamp"]), float(row["acquired_timestamp"])
    if not np.isfinite(captured) or not np.isfinite(acquired) or acquired < captured:
        raise ValueError(f"invalid timestamps at video_frame={video_frame}")
    return row


def read_index(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = {}
        for row in csv.DictReader(f):
            key = int(row["video_frame"])
            if key in rows: raise ValueError(f"duplicate video_frame={key} in index")
            rows[key] = row
    return rows


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def mask_preview(rectified, masks):
    image = np.zeros_like(rectified)
    for role, channel in ROLE_MASK.items(): image[masks[channel] > 0] = PREVIEW_COLORS[role]
    return image


def label(image, lines):
    cv2.rectangle(image, (0, 0), (image.shape[1], 42), (20, 20, 20), -1)
    for i, line in enumerate(lines): cv2.putText(image, line, (8, 16 + 14*i), cv2.FONT_HERSHEY_SIMPLEX, .38, (255,255,255), 1, cv2.LINE_AA)
    return image


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--start", type=int, required=True, help="inclusive video_frame")
    ap.add_argument("--end", type=int, required=True, help="inclusive video_frame")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--overlay", action="store_true", help="add semantic mask overlay panel")
    args=ap.parse_args()
    validate_range(args.start,args.end)
    run=args.run_dir.resolve(); out=args.out.resolve()
    if out.exists(): raise SystemExit(f"refusing to overwrite existing output: {out}")
    source=run/"live_source.mp4"; idxpath=run/"live_video_index.csv"
    index=read_index(idxpath)
    for frame_id in range(args.start,args.end+1): index_row(index,frame_id)
    cap=cv2.VideoCapture(str(source))
    if not cap.isOpened(): raise SystemExit("cannot open source video")
    fps=cap.get(cv2.CAP_PROP_FPS) or 60.
    geometry=Geometry(ROOT/"config/geometry_live_assist.json")
    lane_filter=LaneFilter(geometry)
    out.mkdir(parents=True)
    width,height=geometry.plane_width,geometry.height
    source_width=geometry.width
    panel_count=4 if args.overlay else 3
    video_path=out/"source_window.mp4"
    writer_width=source_width+width*(panel_count-1)
    writer=cv2.VideoWriter(str(video_path),cv2.VideoWriter_fourcc(*"mp4v"),fps,(writer_width,height))
    if not writer.isOpened(): cap.release(); raise SystemExit("cannot open output video writer")
    timeline=[]; mask_frames=[]; source_frames=[]; processing=[]; render=[]; decoded=0; start_time=time.perf_counter()
    try:
        while decoded <= args.end:
            ok, frame=cap.read()
            if not ok: raise ValueError(f"source ended before requested video_frame={decoded}")
            if args.start <= decoded <= args.end:
                row=index_row(index,decoded); source_frame=int(row["source_frame"])
                t=time.perf_counter(); normalized=geometry.normalize(frame); rectified=geometry.rectify(normalized)
                obs,masks,_,rectified,result=lane_filter.process_rectified(rectified,run_id=run.name,
                    source_frame=source_frame,video_frame=decoded,captured_at=float(row["capture_timestamp"]),acquired_at=float(row["acquired_timestamp"]))
                proc_ms=(time.perf_counter()-t)*1000; processing.append(proc_ms)
                render_start=time.perf_counter()
                pix=mask_preview(rectified,masks)
                panels=[normalized,rectified,pix]
                if args.overlay: panels.append(cv2.addWeighted(rectified,.65,pix,.65,0))
                stamp=f"source={source_frame} capture={float(row['capture_timestamp']):.6f}s"
                names=["NORMALIZED SOURCE","RECTIFIED SOURCE","SEMANTIC PIXEL MASK"]+( ["MASK OVERLAY"] if args.overlay else [])
                panels=[label(p,[f"{names[i]} | video_frame={decoded}",stamp]) for i,p in enumerate(panels)]
                writer.write(np.concatenate(panels,axis=1)); render.append((time.perf_counter()-render_start)*1000)
                timeline.append({"video_frame":decoded,"source_frame":source_frame,"capture_timestamp":row["capture_timestamp"],"acquired_timestamp":row["acquired_timestamp"],"detection_count":len(obs),"mask_pixels":int(np.count_nonzero(np.stack(list(masks.values())))),"processing_ms":f"{proc_ms:.3f}"})
                mask_frames.append(np.stack([masks[k] for k in MASK_CHANNELS])); source_frames.append(source_frame)
            decoded+=1
    finally:
        cap.release(); writer.release()
    elapsed=(time.perf_counter()-start_time)*1000
    np.savez_compressed(out/"semantic_masks.npz",video_frames=np.arange(args.start,args.end+1),source_frames=np.asarray(source_frames),channel_names=np.asarray(MASK_CHANNELS),masks=np.stack(mask_frames))
    with (out/"timeline.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(timeline[0])); w.writeheader(); w.writerows(timeline)
    manifest={"video_frame_window":{"start_inclusive":args.start,"end_inclusive":args.end,"count":len(timeline)},"run_id":run.name,"sequential_decode_start":0,"sequential_decoded_through":decoded-1,"index_rows_verified":len(timeline),"index_mapping_verified":all(int(index_row(index,r["video_frame"])["source_frame"])==r["source_frame"] for r in timeline),"geometry_status":geometry.status,"geometry_sha256":geometry.sha256,"source_video_sha256":sha256(source),"index_sha256":sha256(idxpath),"panel_widths_px":[source_width,width,width]+([width] if args.overlay else []),"outputs":{},"timing_ms":{"requested_frame_processing_mean":float(np.mean(processing)),"video_render_encode_mean_including_composition":float(np.mean(render)),"total_wall":elapsed}}
    for p in sorted(out.iterdir()):
        if p.is_file(): manifest["outputs"][p.name]={"sha256":sha256(p),"bytes":p.stat().st_size}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(out)

if __name__=="__main__": main()
