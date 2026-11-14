"""Create short, timestamp-aligned V8.5 candidate review clips and UNKNOWN queue."""
from __future__ import annotations
import argparse,csv,json,sys
from pathlib import Path
import cv2,numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.early_perception import EarlyPixelProvider  # noqa:E402
from src.lane_filter import MASK_CHANNELS,PREVIEW_COLORS,ROLE_MASK  # noqa:E402
from src.model import Geometry  # noqa:E402


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def parse_pair(value):
    try:
        v=json.loads(value.replace('(', '[').replace(')', ']'))
        return float(v[0]),float(v[1])
    except Exception:return (0.,0.)


def choose_cases(rows):
    cases=[]
    choices=[('tap_cyan','cyan',('tap','pending')),
             ('hold_green','green',('hold',)),
             ('hold_yellow','yellow',('hold','pending')),
             ('gray_panel','neutral',('pending',))]
    used=set()
    for case_id,color,hints in choices:
        pool=[r for r in rows if r['color']==color and r['type_hint'] in hints and
              str(r['birth_zone']).lower() in ('true','1') and
              (r.get('confirmed_at') or case_id=='hold_yellow')]
        pool.sort(key=lambda r:(r['run_id'],float(r['first_candidate_at']),-float(r.get('birth_face_quality') or 0)))
        if pool:
            row=pool[0];cases.append({'case_id':case_id,'row':row,'status':'AUTO_CANDIDATE_UNKNOWN'});used.add((row['run_id'],row['note_uid']))
        else:cases.append({'case_id':case_id,'row':None,'status':'NOT_FOUND_IN_SCANNED_RUNS'})
    # Add two unreviewed negative/ambiguity prompts from real candidate tracks
    # close to judgment and a pair of same-frame Hold candidates when present.
    near=[r for r in rows if float(r['birth_y'])>=300]
    if near:
        cases.append({'case_id':'near_hit_effect_or_fragment','row':near[0],
                      'status':'AUTO_CANDIDATE_UNKNOWN;could_be_note_or_effect'})
    holds=[r for r in rows if r['type_hint']=='hold' and r['color'] in ('green','yellow')]
    paired=None
    for i,a in enumerate(holds):
        lane_a=parse_pair(a['birth_lane_span'])
        for b in holds[i+1:]:
            if a['run_id']!=b['run_id'] or abs(int(a['candidate_video_frame'])-int(b['candidate_video_frame']))>1:continue
            lane_b=parse_pair(b['birth_lane_span'])
            if max(lane_a[0],lane_b[0])>=min(lane_a[1],lane_b[1]):paired=(a,b);break
        if paired:break
    if paired:
        cases.append({'case_id':'simultaneous_hold_candidates','row':paired[0],
            'peer':paired[1],'status':'AUTO_CANDIDATES_UNKNOWN;owner_not_verified'})
    else:cases.append({'case_id':'simultaneous_hold_candidates','row':None,'status':'NOT_FOUND_IN_SCANNED_RUNS'})
    return cases


def render_case(run_dir,case,out_dir,window_s,birth_zone_end_y):
    row=case['row'];run_id=run_dir.name
    idx=csv_rows(run_dir/'live_video_index.csv')
    target=float(row['first_candidate_at']);before,after=window_s
    selected=[r for r in idx if target-before<=float(r['capture_timestamp'])<=target+after]
    if not selected:return None
    start=int(selected[0]['video_frame']);end=int(selected[-1]['video_frame']);center=int(row['candidate_video_frame'])
    cap=cv2.VideoCapture(str(run_dir/'live_source.mp4'))
    if not cap.isOpened():return None
    # Frame seeking on long-GOP MP4 can return an earlier keyframe while the
    # sidecar index advances from ``start``. Decode sequentially from frame 0
    # so every overlay and timestamp refers to the actual indexed source frame.
    geometry=Geometry(ROOT/'config/geometry_live_assist.json');provider=EarlyPixelProvider(geometry,birth_zone_end_y=birth_zone_end_y)
    name=f"{run_id}_{case['case_id']}";case_dir=out_dir/name;case_dir.mkdir(parents=True,exist_ok=True)
    fps=float(cap.get(cv2.CAP_PROP_FPS) or 60.);writer=None;frame_no=0;center_written=False;decoded_rows={int(r['video_frame']):r for r in idx}
    while frame_no<=end:
        ok,image=cap.read()
        if not ok:break
        if frame_no<start:
            frame_no+=1
            continue
        indexed=decoded_rows.get(frame_no)
        if indexed is None:frame_no+=1;continue
        timestamp=float(indexed['capture_timestamp'])
        if not target-before<=timestamp<=target+after:frame_no+=1;continue
        normalized=geometry.normalize(image);detections=provider.detect(normalized)
        rect=provider.last_rect;masks=provider.last_result.masks
        mask=np.zeros_like(rect)
        for role,channel in ROLE_MASK.items():mask[masks[channel]>0]=PREVIEW_COLORS[role]
        overlay=cv2.addWeighted(rect,.68,mask,.72,0)
        for d in detections:
            x,y,w,h=d.bbox;col=PREVIEW_COLORS['HOLD_HEAD'] if d.kind=='hold_head' else PREVIEW_COLORS['TAP_FACE'] if d.kind=='tap' else PREVIEW_COLORS['UNKNOWN']
            cv2.rectangle(overlay,(x,y),(x+w-1,y+h-1),col,1)
            cv2.putText(overlay,f'{d.kind}/{d.semantic_candidate}',(x,max(10,y-2)),cv2.FONT_HERSHEY_SIMPLEX,.25,col,1)
        left=cv2.resize(normalized,(640,360));right=cv2.resize(overlay,(320,360))
        canvas=np.concatenate((left,right),axis=1)
        label=f"{case['case_id']} | video_frame={frame_no} | capture={timestamp:.6f} | {case['status']}"
        cv2.rectangle(canvas,(0,0),(canvas.shape[1],25),(0,0,0),-1);cv2.putText(canvas,label,(6,17),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
        if writer is None:writer=cv2.VideoWriter(str(case_dir/'side_by_side.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps,(canvas.shape[1],canvas.shape[0]))
        writer.write(canvas)
        if frame_no==center and not center_written:
            cv2.imwrite(str(case_dir/'source.png'),image);cv2.imwrite(str(case_dir/'rectified.png'),rect)
            cv2.imwrite(str(case_dir/'mask.png'),mask);cv2.imwrite(str(case_dir/'overlay.png'),overlay)
            np.savez_compressed(case_dir/'masks.npz',channel_names=np.asarray(MASK_CHANNELS),**masks);center_written=True
        frame_no+=1
    cap.release()
    if writer is not None:writer.release()
    return {'case_id':case['case_id'],'run_id':run_id,'candidate_video_frame':center,
        'candidate_source_frame':row['candidate_source_frame'],'capture_timestamp':target,
        'window_start_video_frame':start,'window_end_video_frame':end,
        'window_start_capture_timestamp':selected[0]['capture_timestamp'],
        'window_end_capture_timestamp':selected[-1]['capture_timestamp'],
        'color':row['color'],'type_hint':row['type_hint'],'candidate_bbox':row['birth_lane_span'],
        'birth_y':row['birth_y'],'case_status':case['status'],'annotation_status':'NOT_HUMAN_REVIEWED',
        'physical_note_id':'UNKNOWN','owner_labels':'UNKNOWN','review_video':str((case_dir/'side_by_side.mp4').relative_to(ROOT)),
        'source_frame_image':str((case_dir/'source.png').relative_to(ROOT)) if center_written else ''}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir',action='append',type=Path,required=True)
    ap.add_argument('--tracks',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'output/analysis_v85_early_identity/review_windows')
    ap.add_argument('--window-seconds',type=float,nargs=2,default=(.5,.5))
    ap.add_argument('--birth-zone-end-y',type=float,default=None)
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    tracks=csv_rows(args.tracks);cases=choose_cases(tracks);run_map={p.name:p.resolve() for p in args.run_dir}
    queue=[]
    for case in cases:
        row=case.get('row')
        if row is None:
            queue.append({'case_id':case['case_id'],'case_status':case['status'],
                'annotation_status':'NOT_FOUND_IN_SCANNED_RUNS','physical_note_id':'UNKNOWN','owner_labels':'UNKNOWN'})
            continue
        run=run_map[row['run_id']]
        rendered=render_case(run,case,out,args.window_seconds,args.birth_zone_end_y)
        queue.append(rendered or {'case_id':case['case_id'],'run_id':run.name,
            'case_status':'RENDER_FAILED','annotation_status':'UNKNOWN','physical_note_id':'UNKNOWN'})
    if queue:
        with (out/'review_queue.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in queue for k in r)));w.writeheader();w.writerows(queue)
    print(out)


if __name__=='__main__':main()
