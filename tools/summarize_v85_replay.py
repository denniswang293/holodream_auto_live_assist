"""Summarize V8.5 fixed/measured replays without claiming physical ground truth."""
from __future__ import annotations
import argparse, ast, csv, json, statistics
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def rows(path):
    if not path.exists(): return []
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))

def iter_rows(path):
    if not path.exists(): return
    with path.open(encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)

def write(path, items):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in items for k in r)) or ['status']
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(items)

def percentiles(values):
    if not values:return {'samples':0,'mean_ms':None,'p50_ms':None,'p90_ms':None,'p99_ms':None}
    s=sorted(values)
    def q(p): return s[min(len(s)-1,int((len(s)-1)*p))]
    return {'samples':len(s),'mean_ms':statistics.fmean(s),'p50_ms':q(.5),'p90_ms':q(.9),'p99_ms':q(.99)}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--fixed-dir',type=Path,required=True)
    ap.add_argument('--measured-dir',type=Path,required=True)
    ap.add_argument('--profile-csv',type=Path,required=True)
    ap.add_argument('--candidate-tracks',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=ROOT/'output/analysis_v85_early_identity')
    a=ap.parse_args(); out=a.out.resolve(); fixed=a.fixed_dir.resolve(); measured=a.measured_dir.resolve()

    # Stage metrics are measured per processed inference frame. Rendering and
    # encoding never appear in this input file.
    profiles=rows(a.profile_csv); vals=defaultdict(list)
    stage_columns=('processing_ms','observe_wall_ms','decision_wall_ms','normalize_ms','game_gate_ms',
        'perception_ms','rectify_ms','hsv_conversion_ms','gray_conversion_ms','connected_components_ms',
        'mask_and_component_ms','tap_panel_recovery_ms','data_conversion_ms','detection_adapter_ms',
        'tracker_association_ms')
    for r in profiles:
        for col in stage_columns:
            try: vals[(r.get('provider',''),col)].append(float(r[col]))
            except (TypeError,ValueError,KeyError): pass
    write(out/'frame_stage_latency.csv',[{'provider':provider,'stage':stage,**percentiles(x),
        'measurement':'inference wall clock; offline decode/render/encoding excluded'}
        for (provider,stage),x in sorted(vals.items())])

    # Identity flags are auditable observations, not physical ID switch labels.
    decisions=rows(fixed/'physical_note_decisions.csv'); flags=[]; holds=[]
    for r in decisions:
        if r.get('provider')!='v85':continue
        if r.get('visibility_state')=='AMBIGUOUS_ASSOCIATION' or r.get('reason')=='ambiguous_association':
            flags.append({'run_id':a.run_id,'video_frame':r.get('video_frame'),'capture_timestamp':r.get('capture_timestamp'),
                'provider_note_uid':r.get('note_uid'),'state':r.get('visibility_state'),'reason':r.get('reason'),
                'physical_identity_status':'UNKNOWN_NO_REVIEWED_PHYSICAL_ID','source':'fixed-delay decision log'})
        if r.get('kind')=='hold' or r.get('detection_kind')=='hold_head':
            holds.append({'run_id':a.run_id,'video_frame':r.get('video_frame'),'capture_timestamp':r.get('capture_timestamp'),
                'provider_note_uid':r.get('note_uid'),'state':r.get('state'),'reason':r.get('reason'),
                'tail_uid':r.get('tail_uid'),'tail_terminal_owner':r.get('tail_terminal_owner'),
                'tail_observations':r.get('tail_observations'),'tail_visibility_state':r.get('tail_visibility_state'),
                'physical_owner_status':'UNKNOWN_NO_REVIEWED_OWNER_LABEL'})
    write(out/'identity_switch_cases.csv',flags or [{'status':'NO_AUTOMATIC_AMBIGUOUS_ASSOCIATION_ROWS','physical_identity_status':'UNKNOWN_NO_REVIEWED_PHYSICAL_ID'}])
    write(out/'hold_tail_owner_cases.csv',holds or [{'status':'NO_HOLD_TAIL_DECISION_ROWS','physical_owner_status':'UNKNOWN_NO_REVIEWED_OWNER_LABEL'}])

    # Enrich automatically proposed candidate metrics only where an exact
    # birth-frame + bbox + provider-local tracker observation join exists.
    candidates=rows(a.candidate_tracks)
    v85_birth={}
    for c in iter_rows(fixed/'candidate_trace.csv'):
        if c.get('provider')!='v85' or c.get('candidate_stage')!='tracker_input':continue
        try: box_key=tuple(map(int,ast.literal_eval(c.get('bbox',''))))
        except Exception: box_key=()
        key=(str(c.get('video_frame')),box_key)
        if key not in v85_birth:v85_birth[key]=c.get('tracker_uid','')
    by_uid=defaultdict(list)
    for d in decisions:
        if d.get('provider')=='v85':by_uid[d.get('note_uid')].append(d)
    ref=rows(measured/'reference_actions_posthoc.csv')
    out_candidates=[]
    for c in candidates:
        if c.get('run_id')!=a.run_id:
            out_candidates.append({**c,'provider_local_replay_uid':'NOT_REPLAYED',
                'commit_at':'','visible_last_at':'','predicted_crossing_at':'',
                'physical_reference_action_at_posthoc_only':'',
                'join_method':'candidate scan only; no replay run for this session',
                'annotation_status':'UNKNOWN_NOT_HUMAN_REVIEWED'})
            continue
        try: bbox=tuple(map(int,json.loads(c['birth_bbox']))); frame=str(c['candidate_video_frame'])
        except Exception: bbox=();frame=''
        uid=v85_birth.get((frame,bbox),'')
        ds=by_uid.get(uid,[])
        def stamp(r,k):
            try:return float(r[k])
            except (TypeError,ValueError,KeyError):return None
        commits=[d for d in ds if d.get('state') in ('SCHEDULED','HELD','PRESSED','DONE') or d.get('identity_state') in ('COMMITTED','CONSUMED')]
        crossings=[stamp(d,'crossing_at') for d in ds];crossings=[x for x in crossings if x is not None]
        visible=[stamp(d,'last_observation') for d in ds];visible=[x for x in visible if x is not None]
        nearest=[]; birth=stamp(c,'first_candidate_at'); keyname=''
        for d in ds:
            if d.get('key'):keyname=d['key'];break
        for e in ref:
            if e.get('action')!='key_down' or e.get('key')!=keyname or birth is None:continue
            try: nearest.append((abs(float(e['timestamp'])-birth),float(e['timestamp'])))
            except (KeyError,ValueError):pass
        physical=min(nearest)[1] if nearest and min(nearest)[0]<=.5 else ''
        out_candidates.append({**c,'provider_local_replay_uid':uid or 'UNJOINED',
            'commit_at':min((stamp(d,'capture_timestamp') for d in commits if stamp(d,'capture_timestamp') is not None),default=''),
            'visible_last_at':max(visible) if visible else '',
            'predicted_crossing_at':min(crossings) if crossings else '',
            'physical_reference_action_at_posthoc_only':physical,
            'join_method':'same birth frame + exact rectified bbox; provider-local UID after join' if uid else 'NO_EXACT_JOIN',
            'annotation_status':'UNKNOWN_NOT_HUMAN_REVIEWED'} )
    write(out/'early_confirmation_metrics.csv',out_candidates)
    grouped=defaultdict(list)
    for c in out_candidates:grouped[(c.get('run_id'),c.get('color'),c.get('type_hint'))].append(c)
    summaries=[]
    for (run_id,color,hint),items in sorted(grouped.items()):
        ys=[];delays=[];distances=[]
        for c in items:
            try:ys.append(float(c['birth_y']))
            except (KeyError,ValueError,TypeError):pass
            try:delays.append(float(c['confirmed_at'])-float(c['first_candidate_at']))
            except (KeyError,ValueError,TypeError):pass
            try:distances.append(float(c['confirmed_y'])-float(c['birth_motion_y']))
            except (KeyError,ValueError,TypeError):pass
        def q(vals,p):return float(__import__('numpy').percentile(vals,p)) if vals else None
        summaries.append({'run_id':run_id,'color':color,'type_hint':hint,'candidate_tracks':len(items),
            'confirmed_tracks':sum(bool(c.get('confirmed_at')) for c in items),
            'candidate_to_confirm_s_p10':q(delays,10),'candidate_to_confirm_s_p50':q(delays,50),
            'candidate_to_confirm_s_p90':q(delays,90),'candidate_to_confirm_pixels_p10':q(distances,10),
            'candidate_to_confirm_pixels_p50':q(distances,50),'candidate_to_confirm_pixels_p90':q(distances,90),
            'ground_truth_status':'NOT_EVALUABLE_AUTOMATIC_TRACKS_ONLY'})
    write(out/'early_confirmation_by_class.csv',summaries)

    fixed_summary=rows(fixed/'baseline_vs_candidate.csv'); measured_summary=rows(measured/'baseline_vs_candidate.csv')
    stale_pauses=Counter(); stale_timeouts=Counter()
    for r in iter_rows(measured/'mock_actions.csv'):
        provider=r.get('provider','')
        if r.get('event')=='input_paused' and r.get('reason')=='stale_capture':stale_pauses[provider]+=1
        if r.get('event')=='disarmed' and r.get('reason')=='stale_timeout':stale_timeouts[provider]+=1
    for row in measured_summary:
        row['input_stale_pause_events']=stale_pauses[row.get('provider','')]
        row['stale_timeout_disarms']=stale_timeouts[row.get('provider','')]
    report={'run_id':a.run_id,'fixed_delay':fixed_summary,'measured_time':measured_summary,
        'fixed_manifest':str((fixed/'replay_manifest.json')),'measured_manifest':str((measured/'replay_manifest.json')),
        'measured_stale_events':{'input_paused_stale_capture':dict(stale_pauses),
            'disarmed_stale_timeout':dict(stale_timeouts)},
        'frame_stage_metrics':'frame_stage_latency.csv','identity_switch_cases':'identity_switch_cases.csv',
        'hold_tail_owner_cases':'hold_tail_owner_cases.csv',
        'human_reviewed_physical_ground_truth':False,'game_grade':'UNVERIFIED',
        'human_key_proximity_is_posthoc_auxiliary_only':True}
    (out/'replay_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(out)

if __name__=='__main__':main()
