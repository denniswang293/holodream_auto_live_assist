import csv
from copy import deepcopy
import gzip
import json

import pytest

from tools.compare_player_references import compare,find_anchor
from tools.replay_player_references import clean


def source_frames():
    frames=[]
    for i in range(6):
        timestamp=9.75+i*.04
        c=dict(bbox=[220,255+i*8,130,10],appearance='cyan_bar',note_type='tap',
               keys=['D','F'],u_min=.25,u_max=.48,path_bbox=None)
        track=dict(uid='one:simple:1',last_time=timestamp,candidate=c,
                   confirmed_type='tap',global_decision={
                       'press_at':10.04,'physical_cross_at':10.10,'reason':'global_eligible'})
        frames.append(dict(captured=timestamp,acquired=timestamp+.015,
                           candidates=[c],tracks=[track]))
    return frames


def write_replay(path,frames):
    with gzip.open(path/'frames.jsonl.gz','wt') as stream:
        for f in frames:stream.write(json.dumps(f)+'\n')
    with (path/'actions.csv').open('w',newline='') as stream:
        fields=['action','event_id','key','timestamp','reason']
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        writer.writerow(dict(action='key_down',event_id='one:simple:1',key='F',timestamp=10.04,reason=''))
        writer.writerow(dict(action='key_up',event_id='one:simple:1',key='F',timestamp=10.065,reason=''))


def interval(identifier,key='D',down=10.,up=10.15):
    return dict(reference_press_id=str(identifier),key=key,down_timestamp=str(down),
                up_timestamp=str(up),duration_ms=str((up-down)*1000))


def test_reference_anchor_uses_finished_exposure_before_key_not_nominal_fps():
    frames=source_frames()
    # The final exposure ends after this key event, even though capture began
    # before it. It cannot be claimed as a pre-input observation.
    down=frames[-1]['captured']+.005
    anchor=find_anchor(frames,[f['acquired'] for f in frames],down,'D')
    assert anchor['frame']==len(frames)-2
    assert anchor['exposure_end']<=down


def test_same_source_timing_and_alternative_legal_key_do_not_become_hit_truth(tmp_path):
    write_replay(tmp_path,source_frames())
    result=compare('reference',tmp_path,[interval(1)])[0]
    assert result['auto_key']=='F' and result['reference_key']=='D'
    assert result['timing_difference_ms']==pytest.approx(40.)
    assert result['release_difference_ms']==pytest.approx(-85.)
    assert result['physical_note_id']=='UNKNOWN'
    assert result['visual_crossing_at']==''
    assert result['visual_crossing_status']=='EXTRAPOLATED_ONLY_NOT_OBSERVED'
    assert 'MOCK_GAME_RESULT_UNKNOWN' in result['game_result']


def test_one_auto_action_cannot_explain_two_repeated_same_key_notes(tmp_path):
    frames=source_frames()
    for frame in frames: frame['candidates'][0]['bbox'][1]+=20
    write_replay(tmp_path,frames)
    result=compare('reference',tmp_path,[interval(1,up=10.05),interval(2,down=10.1,up=10.2)])
    assert sum(bool(r['auto_event_id']) for r in result)==1


def test_two_human_keys_on_same_visible_head_are_not_two_proven_notes(tmp_path):
    write_replay(tmp_path,source_frames())
    result=compare('reference',tmp_path,[interval(1,'D'),interval(2,'F')])
    assert all(r['association']=='REFERENCE_MULTIKEY_SHARED_HEAD' for r in result)
    assert all(r['timing_difference_ms']=='' for r in result)


def test_next_incoming_head_is_not_matched_when_foreground_is_unresolved_edge():
    frames=source_frames()
    for f in frames:
        f['candidates'][0]['bbox'][1]-=60
        f['candidates'].append(dict(bbox=[220,305,130,2],appearance='yellow_bar',
            note_type='unknown',keys=['D'],u_min=.25,u_max=.48,path_bbox=None))
    assert find_anchor(frames,[f['acquired'] for f in frames],10.,'D') is None


def test_nonfinite_diagnostics_are_explicitly_unavailable_in_strict_json():
    payload=clean(dict(speed=float('nan'),range=[1.,float('inf')]))
    assert json.loads(json.dumps(payload,allow_nan=False))=={'speed':None,'range':[1.,None]}


def test_ab_comparison_freezes_reference_visual_anchors(tmp_path):
    baseline=tmp_path/'baseline';variant=tmp_path/'variant'
    baseline.mkdir();variant.mkdir()
    frames=source_frames()
    write_replay(baseline,frames)
    for frame in frames:frame['candidates']=[]
    write_replay(variant,frames)
    result=compare('reference',variant,[interval(1)],baseline)[0]
    assert result['association']=='VISUAL_CHAIN'
    assert result['auto_event_id']=='one:simple:1'
    assert result['timing_difference_ms']==pytest.approx(40.)


def test_ab_comparison_rejects_different_source_timeline(tmp_path):
    baseline=tmp_path/'baseline';variant=tmp_path/'variant'
    baseline.mkdir();variant.mkdir()
    write_replay(baseline,source_frames())
    frames=source_frames();frames[0]['captured']+=.001
    write_replay(variant,frames)
    with pytest.raises(ValueError,match='identical indexed source captures'):
        compare('reference',variant,[interval(1)],baseline)


def test_timing_comparison_never_selects_post_input_prediction(tmp_path):
    frames=source_frames()
    for frame in frames:frame['tracks'][0]['global_decision']['press_at']=10.02
    future=deepcopy(frames[-1]);future.update(captured=10.05,acquired=10.065)
    future['tracks'][0]['global_decision']['press_at']=10.04
    frames.append(future)
    write_replay(tmp_path,frames)
    result=compare('reference',tmp_path,[interval(1)])[0]
    assert result['predicted_press_at']==10.02
