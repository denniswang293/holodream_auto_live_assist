"""Profile pixel-backed candidate births and confirmation on indexed videos.

This is an audit, not ground truth: automatically generated detections stay
UNREVIEWED and no key actions or human key events are read.
"""
from __future__ import annotations
import argparse,csv,json,sys
from collections import Counter,defaultdict
from pathlib import Path
import cv2,numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.early_perception import EarlyPixelProvider  # noqa:E402
from src.model import Geometry  # noqa:E402
from src.tracking import Tracker  # noqa:E402


def read_index(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return {int(r['video_frame']):r for r in csv.DictReader(f)}


def run(run_dir,limit=None):
    geometry=Geometry(ROOT/'config/geometry_live_assist.json')
    provider=EarlyPixelProvider(geometry)
    tracker=Tracker(geometry)
    index=read_index(run_dir/'live_video_index.csv')
    cap=cv2.VideoCapture(str(run_dir/'live_source.mp4'))
    if not cap.isOpened():raise RuntimeError(f'cannot open {run_dir}/live_source.mp4')
    rows=[];row_by_uid={};decoded=0;last_capture=None
    try:
        while limit is None or decoded<limit:
            ok,image=cap.read()
            if not ok:break
            row=index.get(decoded)
            if row is None:decoded+=1;continue
            captured=float(row['capture_timestamp']);acquired=float(row['acquired_timestamp'])
            if acquired<captured or (last_capture is not None and captured<=last_capture):
                raise ValueError(f'invalid indexed timestamp in frame {decoded}')
            last_capture=captured
            normalized=geometry.normalize(image)
            detections=provider.detect(normalized)
            notes=tracker.update(detections,captured,provider.last_labels,provider.last_path)
            for note in notes:
                birth=note.birth_info
                if birth is None:continue
                if note.uid not in row_by_uid:
                    record={'run_id':run_dir.name,'note_uid':note.uid,
                        'candidate_video_frame':decoded,'candidate_source_frame':int(row.get('source_frame',decoded)),
                        'first_candidate_at':birth.captured_at,'birth_y':birth.bbox[1],
                        'birth_motion_y':note.origin_y,'birth_bbox':list(birth.bbox),
                        'birth_lane_span':list(birth.lane_span),'color':birth.color,
                        'type_hint':birth.type_hint,'birth_evidence':'|'.join(birth.evidence),
                        'birth_face_quality':birth.face_quality,'birth_full_face':birth.full_face,
                        'birth_zone':birth.birth_zone,'confirmed_at':'','confirmed_video_frame':'',
                        'confirmed_y':'','confirmed_kind':'','latest_kind':note.kind,
                        'commit_at':'','physical_reference_action_at':'',
                        'annotation_status':'UNKNOWN_NOT_HUMAN_REVIEWED'}
                    rows.append(record);row_by_uid[note.uid]=record
                record=row_by_uid[note.uid]
                record['latest_kind']=note.kind
                if note.confirmed and not record['confirmed_at']:
                    record['confirmed_at']=captured;record['confirmed_video_frame']=decoded
                    record['confirmed_y']=note.head[-1][1] if note.head else ''
                    record['confirmed_kind']=note.kind
            decoded+=1
    finally:cap.release()
    # Remove detections whose cap was a tail-only fragment or otherwise never
    # acquired a Track, while keeping UNKNOWN/pending note candidates visible.
    return decoded,rows,provider.birth_zone_end_y


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir',type=Path,action='append',required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'output/analysis_v85_early_identity')
    ap.add_argument('--limit-frames',type=int)
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    tracks=[];summary=[];zone_ends=[]
    for run_dir in args.run_dir:
        run_dir=run_dir.resolve();decoded,rows,zone=run(run_dir,args.limit_frames)
        tracks.extend(rows);zone_ends.append(zone)
        group=defaultdict(list)
        for row in rows:group[(row['color'],row['type_hint'])].append(row)
        for (color,hint),items in sorted(group.items()):
            ys=[float(r['birth_y']) for r in items]
            delays=[float(r['confirmed_at'])-float(r['first_candidate_at']) for r in items if r['confirmed_at']]
            distances=[float(r['confirmed_y'])-float(r['birth_motion_y']) for r in items if r['confirmed_at']]
            summary.append({'run_id':run_dir.name,'decoded_frames':decoded,'color':color,
                'type_hint':hint,'candidate_tracks':len(items),
                'confirmed_tracks':sum(bool(r['confirmed_at']) for r in items),
                'confirmed_tap_tracks':sum(r.get('confirmed_kind')=='tap' for r in items),
                'confirmed_hold_tracks':sum(r.get('confirmed_kind')=='hold' for r in items),
                'confirmed_type_pending_tracks':sum(r.get('confirmed_kind')=='pending' for r in items),
                'birth_y_p10':float(np.percentile(ys,10)),'birth_y_p50':float(np.percentile(ys,50)),
                'birth_y_p90':float(np.percentile(ys,90)),
                'candidate_to_confirm_s_p10':float(np.percentile(delays,10)) if delays else None,
                'candidate_to_confirm_s_p50':float(np.percentile(delays,50)) if delays else None,
                'candidate_to_confirm_s_p90':float(np.percentile(delays,90)) if delays else None,
                'candidate_to_confirm_pixels_p10':float(np.percentile(distances,10)) if distances else None,
                'candidate_to_confirm_pixels_p50':float(np.percentile(distances,50)) if distances else None,
                'candidate_to_confirm_pixels_p90':float(np.percentile(distances,90)) if distances else None,
                'ground_truth_status':'NOT_EVALUABLE_AUTOMATIC_TRACKS_ONLY'})
    if tracks:
        with (out/'early_candidate_tracks.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(tracks[0]));w.writeheader();w.writerows(tracks)
    if summary:
        with (out/'early_confirmation_metrics.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    (out/'birth_zone_audit.json').write_text(json.dumps({'run_ids':[p.name for p in args.run_dir],
        'limit_frames':args.limit_frames,'provisional_geometric_birth_zone_end_y':zone_ends[0] if zone_ends else None,
        'provider':'current-frame pixel evidence only','timestamps':'capture_timestamp from live_video_index.csv',
        'automatic_candidate_counts_are_not_physical_note_ground_truth':True,
        'confirmed_tracks':sum(bool(r['confirmed_at']) for r in tracks),
        'candidate_tracks':len(tracks),'recommended_zone_end_y':None,
        'zone_decision':'NOT_SET_FROM_UNREVIEWED_CANDIDATES'},indent=2),encoding='utf-8')
    print(out)


if __name__=='__main__':main()
