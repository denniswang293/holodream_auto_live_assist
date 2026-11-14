"""Render current-frame pixel segmentation for offline review only."""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.lane_filter import LaneFilter, MASK_CHANNELS, PREVIEW_COLORS, ROLE_MASK  # noqa:E402
from src.model import Geometry  # noqa:E402
from src.perception import Perception  # noqa:E402


def read_index(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {int(row["video_frame"]): row for row in csv.DictReader(f)}


def debug_overlay(rectified, observations):
    result = cv2.addWeighted(rectified, .72, np.zeros_like(rectified), .28, 0)
    for o in observations:
        x, y, w, h = o.bbox_rectified
        color = PREVIEW_COLORS.get(o.role, PREVIEW_COLORS["UNKNOWN"])
        if o.polygon_rectified:
            cv2.polylines(result, [np.asarray(o.polygon_rectified, np.int32)], True, color, 1)
        cv2.rectangle(result, (x, y), (x + w - 1, y + h - 1), color, 1)
        cv2.putText(result, f"{o.role} {o.candidate_id}", (x, max(10, y - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX, .28, color, 1, cv2.LINE_AA)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "output/analysis_lane_filter_v84_rework")
    ap.add_argument("--mode", choices=("baseline", "filtered", "compare"), default="compare")
    ap.add_argument("--limit-frames", type=int)
    ap.add_argument("--review-seconds", type=float, nargs="+", default=[4.9, 6.0, 13.2, 14.9, 16.9])
    args = ap.parse_args()
    run_dir = args.run_dir.resolve(); source_path = run_dir / "live_source.mp4"
    index_path = run_dir / "live_video_index.csv"
    index = read_index(index_path)
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened(): raise SystemExit(f"cannot open {source_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    geometry = Geometry(ROOT / "config/geometry_live_assist.json")
    out = args.out.resolve() / run_dir.name
    out.mkdir(parents=True, exist_ok=True)
    mask_dir = out / "masks"; mask_dir.mkdir(exist_ok=True)
    review_dir = out / "review_frames"; review_dir.mkdir(exist_ok=True)
    selected = {int(round(sec * fps)): sec for sec in args.review_seconds}
    lane_filter = LaneFilter(geometry) if args.mode in ("filtered", "compare") else None
    legacy = Perception(geometry) if args.mode in ("baseline", "compare") else None
    writers = {}
    obs_path = out / "detections.csv"
    summary_path = out / "frame_summary.csv"
    fields = list(__import__("dataclasses").fields(__import__("src.lane_filter", fromlist=["LaneObservation"]).LaneObservation))
    obs_names = [f.name for f in fields]
    processing_ms=[];legacy_ms=[];render_ms=[];normalize_ms=[];rectify_ms=[];profile_rows=[]
    frame_rows=[];mask_chunk=[];chunk_start=0;decoded=0;missing_index=0
    role_counts={key:0 for key in ROLE_MASK}; channel_pixels={key:0 for key in MASK_CHANNELS}
    try:
        with obs_path.open("w", encoding="utf-8", newline="") as of, summary_path.open("w", encoding="utf-8", newline="") as sf:
            ow=csv.DictWriter(of,fieldnames=obs_names);ow.writeheader()
            sw=csv.DictWriter(sf,fieldnames=["video_frame","source_frame","capture_timestamp","acquired_timestamp","focused","roi_valid","detection_count","roles","pixel_area","normalize_ms","rectify_ms","hsv_conversion_ms","gray_conversion_ms","connected_components_ms","mask_and_component_ms","data_conversion_ms","temporal_association_ms","preview_render_ms","segmentation_ms","render_and_encode_ms","legacy_perception_ms"]);sw.writeheader()
            while args.limit_frames is None or decoded < args.limit_frames:
                ok, frame = cap.read()
                if not ok: break
                loop_start=time.perf_counter(); idx=index.get(decoded)
                if idx is None:
                    missing_index+=1; source_frame=decoded; captured=acquired=None; focused=False; roi_valid=False
                else:
                    source_frame=int(idx.get("source_frame",decoded));captured=float(idx["capture_timestamp"]);acquired=float(idx["acquired_timestamp"])
                    focused=str(idx.get("focused","True")).lower() in ("true","1");roi_valid=str(idx.get("roi_valid","True")).lower() in ("true","1")
                t0=time.perf_counter();normalized=geometry.normalize(frame);norm_ms=(time.perf_counter()-t0)*1000
                t0=time.perf_counter();rectified=geometry.rectify(normalized);rect_ms=(time.perf_counter()-t0)*1000
                observations=[];masks={};preview=None;pixel_area=0;seg_ms=0.;old_ms=0.;profile={}
                if lane_filter is not None and captured is not None and acquired is not None and acquired>=captured:
                    t0=time.perf_counter()
                    observations,masks,preview,rectified,result=lane_filter.process_rectified(rectified,run_id=run_dir.name,
                        source_frame=source_frame,video_frame=decoded,captured_at=captured,acquired_at=acquired)
                    seg_ms=(time.perf_counter()-t0)*1000
                    profile={**getattr(lane_filter.segmenter,"last_profile",{}),"video_frame":decoded,
                        "normalize_ms":norm_ms,"rectify_ms":rect_ms,"segmentation_and_conversion_ms":seg_ms}
                    profile_rows.append(profile)
                    for o in observations:ow.writerow(o.csv_row())
                    for role in role_counts:role_counts[role]+=sum(o.role==role for o in observations)
                    channel_pixels={c:channel_pixels[c]+int(np.count_nonzero(masks[c])) for c in MASK_CHANNELS}
                    pixel_area=sum(int(np.count_nonzero(masks[c])) for c in ("tap_face","hold_head","hold_body","hold_tail"))
                    overlay=debug_overlay(rectified,observations)
                    mask_color=np.zeros_like(rectified)
                    for role,channel in ROLE_MASK.items():mask_color[masks[channel]>0]=PREVIEW_COLORS[role]
                    if decoded in selected:
                        key=f"frame_{decoded:06d}_{selected[decoded]:.1f}s"
                        cv2.imwrite(str(review_dir/f"{key}_source.png"),frame)
                        cv2.imwrite(str(review_dir/f"{key}_rectified.png"),rectified)
                        cv2.imwrite(str(review_dir/f"{key}_gray.png"),cv2.cvtColor(rectified,cv2.COLOR_BGR2GRAY))
                        cv2.imwrite(str(review_dir/f"{key}_mask.png"),mask_color)
                        cv2.imwrite(str(review_dir/f"{key}_overlay.png"),overlay)
                        np.savez_compressed(review_dir/f"{key}_masks.npz",channel_names=np.asarray(MASK_CHANNELS),**masks)
                    if not mask_chunk:chunk_start=decoded
                    mask_chunk.append(np.stack([masks[c] for c in MASK_CHANNELS]))
                    if len(mask_chunk)>=120:
                        np.savez_compressed(mask_dir/f"masks_{chunk_start:06d}_{decoded:06d}.npz",
                            frame_indices=np.arange(chunk_start,decoded+1),channel_names=np.asarray(MASK_CHANNELS),masks=np.stack(mask_chunk));mask_chunk=[]
                else:
                    overlay=np.zeros_like(rectified)
                if legacy is not None:
                    t0=time.perf_counter(); detections=legacy.detect(normalized);old_ms=(time.perf_counter()-t0)*1000
                    legacy_canvas=np.zeros((geometry.height,geometry.plane_width,3),np.uint8)
                    for x,y,w,h in ((int(d.bbox[0]),int(d.bbox[1]),int(d.bbox[2]),int(d.bbox[3])) for d in detections):
                        cv2.rectangle(legacy_canvas,(x,y),(x+w-1,y+h-1),(120,100,220),-1)
                    if "baseline_video" not in writers:
                        writers["baseline_video"]=cv2.VideoWriter(str(out/"baseline_legacy_boxes.mp4"),cv2.VideoWriter_fourcc(*"mp4v"),fps,(geometry.plane_width,geometry.height))
                    writers["baseline_video"].write(legacy_canvas)
                if lane_filter is not None:
                    if "filtered_video" not in writers:
                        writers["filtered_video"]=cv2.VideoWriter(str(out/"filtered_video.mp4"),cv2.VideoWriter_fourcc(*"mp4v"),fps,(geometry.plane_width,geometry.height))
                        writers["side_video"]=cv2.VideoWriter(str(out/"side_by_side.mp4"),cv2.VideoWriter_fourcc(*"mp4v"),fps,(geometry.plane_width*2,geometry.height))
                        writers["debug_video"]=cv2.VideoWriter(str(out/"debug_overlay.mp4"),cv2.VideoWriter_fourcc(*"mp4v"),fps,(geometry.plane_width,geometry.height))
                    writers["filtered_video"].write(preview)
                    writers["side_video"].write(np.concatenate((rectified,preview),axis=1))
                    writers["debug_video"].write(overlay)
                process_elapsed=(time.perf_counter()-loop_start)*1000
                render_encode_ms=max(0.,process_elapsed-seg_ms-old_ms-norm_ms-rect_ms)
                role_names="|".join(sorted({o.role for o in observations}))
                sw.writerow({"video_frame":decoded,"source_frame":source_frame,"capture_timestamp":captured,"acquired_timestamp":acquired,
                    "focused":focused,"roi_valid":roi_valid,"detection_count":len(observations),"roles":role_names,
                    "pixel_area":pixel_area,"normalize_ms":f"{norm_ms:.3f}","rectify_ms":f"{rect_ms:.3f}",
                    "segmentation_ms":f"{profile.get('segmentation_ms',seg_ms):.3f}","hsv_conversion_ms":f"{profile.get('hsv_conversion_ms',0.):.3f}",
                    "gray_conversion_ms":f"{profile.get('gray_conversion_ms',0.):.3f}",
                    "connected_components_ms":f"{profile.get('connected_components_ms',0.):.3f}",
                    "mask_and_component_ms":f"{profile.get('mask_and_component_ms',0.):.3f}",
                    "data_conversion_ms":f"{profile.get('data_conversion_ms',0.):.3f}",
                    "temporal_association_ms":f"{profile.get('temporal_association_ms',0.):.3f}",
                    "preview_render_ms":f"{profile.get('preview_render_ms',0.):.3f}",
                    "render_and_encode_ms":f"{render_encode_ms:.3f}","legacy_perception_ms":f"{old_ms:.3f}"})
                processing_ms.append(seg_ms);legacy_ms.append(old_ms);normalize_ms.append(norm_ms);rectify_ms.append(rect_ms);render_ms.append(render_encode_ms)
                frame_rows.append(decoded);decoded+=1
    finally:
        cap.release()
        for w in writers.values():w.release()
    if mask_chunk:
        np.savez_compressed(mask_dir/f"masks_{chunk_start:06d}_{decoded-1:06d}.npz",
            frame_indices=np.arange(chunk_start,decoded),channel_names=np.asarray(MASK_CHANNELS),masks=np.stack(mask_chunk))
    audit={"run_id":run_dir.name,"mode":args.mode,"decoded_frames":decoded,"index_rows":len(index),
        "missing_index_rows":missing_index,"partial":args.limit_frames is not None and decoded>=args.limit_frames,
        "preview_fps_only":fps,"timestamps_from_index":True,"geometry_status":geometry.status,
        "geometry_sha256":geometry.sha256,"segmentation_source":"current rectified frame pixels only",
        "legacy_detections_used_for_candidate_masks":False,"role_observation_counts":role_counts,
        "mask_channel_pixel_counts":channel_pixels,
        "segmentation_wall_ms_mean":float(np.mean(processing_ms)) if processing_ms else None,
        "segmentation_wall_ms_p90":float(np.percentile(processing_ms,90)) if processing_ms else None,
        "legacy_perception_wall_ms_mean":float(np.mean(legacy_ms)) if legacy_ms else None,
        "normalize_ms_mean":float(np.mean(normalize_ms)) if normalize_ms else None,
        "rectify_ms_mean":float(np.mean(rectify_ms)) if rectify_ms else None,
        "segmenter_hsv_conversion_ms_mean":float(np.mean([r.get("hsv_conversion_ms",0.) for r in profile_rows])) if profile_rows else None,
        "segmenter_gray_conversion_ms_mean":float(np.mean([r.get("gray_conversion_ms",0.) for r in profile_rows])) if profile_rows else None,
        "segmenter_connected_components_ms_mean":float(np.mean([r.get("connected_components_ms",0.) for r in profile_rows])) if profile_rows else None,
        "segmenter_mask_and_component_ms_mean":float(np.mean([r.get("mask_and_component_ms",0.) for r in profile_rows])) if profile_rows else None,
        "segmenter_data_conversion_ms_mean":float(np.mean([r.get("data_conversion_ms",0.) for r in profile_rows])) if profile_rows else None,
        "segmenter_temporal_association_ms_mean":float(np.mean([r.get("temporal_association_ms",0.) for r in profile_rows])) if profile_rows else None,
        "segmenter_preview_render_ms_mean":float(np.mean([r.get("preview_render_ms",0.) for r in profile_rows])) if profile_rows else None,
        "encoding_and_render_wall_ms_mean":float(np.mean(render_ms)) if render_ms else None,
        "visual_metrics":"NOT_EVALUATED_UNTIL_MANUAL_POLYGON_LABELS_ARE_REVIEWED"}
    (out/"audit.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    (out/"quality_report.json").write_text(json.dumps({"segmentation_pixel_precision_recall_iou":"NOT_EVALUATED_NO_REVIEWED_PIXEL_GROUND_TRUTH",
        "physical_note_recall_false_positives":"NOT_EVALUATED_NO_REVIEWED_PHYSICAL_NOTE_ID_LABELS",
        "hold_connectivity_owner_accuracy":"NOT_EVALUATED_NO_REVIEWED_HEAD_TAIL_OWNERSHIP_LABELS",
        "frame_observations":sum(role_counts.values()),"channel_pixel_counts":channel_pixels,
        "known_risk":"multi-hold scene at preview 14.9s requires human ownership review"},indent=2),encoding="utf-8")
    print(out)


if __name__=="__main__":main()
