from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.calibration import geometry_hash
from src.geometry import CalibratedGeometry
from src.live_capture import CapturedFrame
from src.live_engine import LiveEngine,track_options
from src.live_input import ActionIntent,MockActuator,TapScheduler
from src.predictor import Prediction
from src.tap_assignment import AnyCoveredKeyRule
from src.tracker import Track

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_rule():
    geometry = CalibratedGeometry(json.loads((ROOT/'config/geometry_live_assist.json').read_text(encoding='utf-8-sig')))
    config = json.loads((ROOT/'config.json').read_text())
    config['live'] = json.loads((ROOT/'config/live_assist_v5.json').read_text(encoding='utf-8-sig'))
    # Existing cases describe the original conservative policy. New cases
    # explicitly enable the user's experimental unknown/uncertain policy.
    config['live']['speculative_taps']['enabled'] = False
    config['live']['input_advance_px'] = 0
    config['live']['dropout_grace_ms'] = 0
    config['live']['hold_visual']['enabled'] = False
    return config,geometry


def track(make_candidate,i,keys,u0,u1,hit=1000.02):
    c = replace(make_candidate(y=300,keys=keys),u_min=u0,u_max=u1)
    return Track(i,c,history=[(1000.,300.,(u0+u1)/2)],bbox=c.bbox,status='confirmed',
                 observations=10,first_time=999.8,last_time=1000.,stable_keys=list(keys),
                 hit_history=[hit]*3,prediction=Prediction(velocity=180,eta=hit-1000.,hit_time=hit,uncertainty=.001))


def decide(rule,tracks,scheduler):
    return rule.decide(tracks,{tr.track_id:track_options(tr,1000.,rule.allowed_keys,{},allow_range=True)
                              for tr in tracks},scheduler)


def scheduler():
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    return clock,actuator,TapScheduler('assist',actuator,clock=lambda:clock.now)


def test_profile_is_user_statement_not_fake_verified_accuracy(setup_rule):
    config,g = setup_rule
    rule = AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    assert rule.allowed_keys==set('SDFJKL')
    assert rule.metadata()['recognition_accuracy']=='UNVERIFIED'
    assert 'verified_key_mapping' not in config['live']
    for key,value in [('geometry_sha256','wrong'),('key_order',list('L K J F D S'.split())),
                      ('confirmed_by','model'),('rule','press_all')]:
        changed = deepcopy(config)
        changed['live']['tap_rule'][key] = value
        with pytest.raises(ValueError):AnyCoveredKeyRule.from_config(changed,geometry_hash(g.document))


def test_wide_note_selects_maximum_coverage_not_first_or_chord(setup_rule,make_candidate):
    config,g = setup_rule
    rule = AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    _,_,s = scheduler()
    tr = track(make_candidate,1,['D','F'],.30,.49)
    before = list(tr.candidate.candidate_keys)
    assert decide(rule,[tr],s)[1]==(('F',),'')
    assert tr.stable_keys==tr.candidate.candidate_keys==before==['D','F']
    assert not s.pending


def test_batch_matching_reserves_only_choice_for_other_note(setup_rule,make_candidate):
    config,g = setup_rule
    rule = AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    _,_,s = scheduler()
    wide = track(make_candidate,1,['D','F'],.30,.49)
    narrow = track(make_candidate,2,['F'],.35,.49)
    choices = decide(rule,[wide,narrow],s)
    assert choices=={1:(('D',),''),2:(('F',),'')}
    assert decide(rule,[narrow,wide],s)==choices
    third = track(make_candidate,3,['D','F'],.30,.49)
    assert decide(rule,[wide,narrow,third],s)[3]==((),'tap_key_conflict')


def test_timed_reservations_and_locked_key(setup_rule,make_candidate):
    config,g = setup_rule
    rule = AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    _,_,s = scheduler()
    s.recent.append(('F',1000.02))
    tr = track(make_candidate,1,['D','F'],.30,.49)
    assert decide(rule,[tr],s)[1]==(('D',),'')
    tr.candidate = replace(tr.candidate,u_min=.34,u_max=.49,candidate_keys=['F'])
    tr.stable_keys = ['F']
    assert decide(rule,[tr],s)[1]==((),'assigned_key_no_longer_valid')
    later = track(make_candidate,2,['F'],.35,.49,hit=1000.10)
    assert decide(rule,[later],s)[2]==(('F',),'')
    assert len(rule.bindings)==1


def test_new_note_avoids_a_committed_deadline_even_if_original_prediction_was_different(setup_rule,make_candidate):
    config,g=setup_rule
    rule=AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    _,_,s=scheduler()
    s.recent.append(('F',1000.20))
    s.pending['existing']=ActionIntent('existing',('F',),1000.02,.001)
    tr=track(make_candidate,1,['D','F'],.30,.49)
    assert decide(rule,[tr],s)[1]==(('D',),'')


@pytest.mark.parametrize('case',['unstable','overlap','green','pink','neutral','past','nan','uncertain','outside'])
def test_rule_retains_semantic_motion_time_and_span_rejections(setup_rule,make_candidate,case):
    config,g = setup_rule
    rule = AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    _,_,s = scheduler()
    tr = track(make_candidate,1,['D','F'],.30,.49)
    if case=='unstable':tr.stable_keys=['S']  # no stable/current key in common
    if case=='overlap':tr.candidate.suspected_overlap=True
    if case in ('green','pink','neutral'):
        tr.candidate.appearance = case+'_candidate';tr.candidate.note_type='unknown'
    if case=='past':tr.prediction=replace(tr.prediction,hit_time=999.)
    if case=='nan':tr.prediction=replace(tr.prediction,uncertainty=float('nan'))
    if case=='uncertain':tr.prediction=replace(tr.prediction,uncertainty=.1)
    if case=='outside':tr.candidate.u_min=-.1
    assert decide(rule,[tr],s)[1][0]==()
    assert not s.pending


@pytest.mark.parametrize('appearance',['cyan_bar','yellow_bar','green_candidate',
                                       'pink_candidate','neutral_candidate'])
def test_experimental_unknown_candidate_sends_one_timed_key_after_arm(setup_rule,make_candidate,appearance):
    config,g=setup_rule
    config['live']['speculative_taps']['enabled']=True
    clock=SimpleNamespace(now=1000.)
    actuator=MockActuator()
    s=TapScheduler('assist',actuator,clock=lambda:clock.now,max_uncertainty=.10)
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.03)
    tr.candidate=replace(tr.candidate,note_type='unknown',appearance=appearance)
    tr.prediction=replace(tr.prediction,uncertainty=.08)
    tr.stable_keys=['S']  # Current footprint still identifies an allowed lane.
    engine.tracker.update=lambda *args,**kwargs:[tr]
    _,_,events,_=engine.process(CapturedFrame(0,np.zeros((404,720,3),np.uint8),1000.,1000.))
    assert events[0]['type']=='unknown'
    assert events[0]['resolution_basis']=='speculative_visible_candidate'
    assert events[0]['resolved_keys']=='F'
    assert len(s.pending)==1 and not actuator.calls
    clock.now=1000.03;s.poll()
    assert actuator.calls==[('down','F')]
    s.close();assert actuator.calls[-1]==('up','F')


def test_experimental_unknown_still_requires_future_time_current_lane_and_focus(setup_rule,make_candidate):
    config,g=setup_rule
    config['live']['speculative_taps']['enabled']=True
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.03)
    tr.candidate=replace(tr.candidate,note_type='unknown',appearance='green_candidate')
    spec=config['live']['speculative_taps']
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)[0]==('D','F')
    tr.prediction=Prediction(reason='unstable_eta')
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)[0]==()
    tr.prediction=Prediction(eta=.03,hit_time=1000.03,uncertainty=.08)
    tr.candidate=replace(tr.candidate,candidate_keys=[])
    tr.stable_keys=[]
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)[0]==()
    clock,actuator,s=scheduler()
    s.update_context(1000.,'PLAYING',False)
    assert not s.toggle() and not s.pending and not actuator.calls
    s.close()


def test_two_consistent_hit_estimates_allow_only_ordinary_assist_taps(setup_rule,make_candidate):
    config,_=setup_rule
    spec={**config['live']['speculative_taps'],'enabled':True,'tap_min_hit_observations':2}
    tr=track(make_candidate,1,['F'],.34,.48,hit=1000.12)
    tr.candidate=replace(tr.candidate,note_type='unknown',appearance='cyan_bar')
    tr.hit_history=[1000.11,1000.12]
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)==(('F',),'')
    tr.hit_history=[1000.11]
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)[1]=='unstable_hit_time'
    tr.hit_history=[1000.11,1000.30]
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)[1]=='unstable_hit_time'
    tr.hit_history=[1000.11,1000.12]
    tr.candidate=replace(tr.candidate,appearance='green_candidate')
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative=spec)[1]=='unstable_hit_time'
    tr.candidate=replace(tr.candidate,appearance='cyan_bar',note_type='tap')
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,speculative={'enabled':False})[1]=='unstable_hit_time'


def test_single_fit_last_chance_requires_visible_nearline_cyan_or_yellow(setup_rule,make_candidate):
    config,_=setup_rule
    spec={**config['live']['speculative_taps'],'enabled':True,'tap_last_chance_single_fit':True}
    tr=track(make_candidate,1,['F'],.34,.48,hit=1000.03)
    tr.candidate=replace(tr.candidate,note_type='unknown',appearance='cyan_bar')
    tr.hit_history=[1000.03]
    tr.prediction=replace(tr.prediction,uncertainty=.01)
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,
                         speculative=spec,nearline_y=285)==(('F',),'')
    tr.history=[(1000.,270.,.4)]
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,
                         speculative=spec,nearline_y=285)[1]=='unstable_hit_time'
    tr.history=[(1000.,300.,.4)]
    tr.prediction=replace(tr.prediction,hit_time=1000.08,eta=.08)
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,
                         speculative=spec,nearline_y=285)[1]=='unstable_hit_time'
    tr.prediction=replace(tr.prediction,hit_time=1000.03,eta=.03,uncertainty=.03)
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,
                         speculative=spec,nearline_y=285)[1]=='unstable_hit_time'
    tr.prediction=replace(tr.prediction,uncertainty=.01)
    tr.candidate=replace(tr.candidate,appearance='green_candidate')
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True,
                         speculative=spec,nearline_y=285)[1]=='unstable_hit_time'


def test_engine_requires_hotkey_and_sends_only_selected_key_then_releases(setup_rule,make_candidate):
    config,g = setup_rule
    clock,actuator,s = scheduler()
    engine = LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update = lambda *args:'PLAYING'
    first = track(make_candidate,1,['D','F'],.30,.49)
    visible = [first]
    engine.tracker.update = lambda *args,**kwargs:visible
    image = np.zeros((404,720,3),np.uint8)
    _,_,events,_ = engine.process(CapturedFrame(0,image,1000.,1000.))
    assert events[0]['key_candidates']=='D|F' and events[0]['resolved_keys']=='F'
    assert events[0]['resolution_basis']=='user_confirmed_any_covered_key'
    assert not s.pending and not actuator.calls
    assert s.toggle();s.poll()
    clock.now = 1000.005
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert not s.pending  # An event seen while OFF cannot fire after arming.
    visible[:] = [track(make_candidate,2,['D','F'],.30,.49,hit=1000.025)]
    clock.now = 1000.01
    engine.process(CapturedFrame(2,image,clock.now,clock.now))
    assert len(s.pending)==1 and not actuator.calls
    clock.now = 1000.025;s.poll()
    assert actuator.calls==[('down','F')]
    s.disarm('F12')
    assert actuator.calls==[('down','F'),('up','F')]
    assert not s.armed and not s.held




@pytest.mark.parametrize('interruption',['missed','overlap','unstable_keys'])
def test_fresh_reacquisition_can_retry_same_arm_but_never_repeat_key_down(setup_rule,make_candidate,interruption):
    config,g = setup_rule
    clock,actuator,s = scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine = LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update = lambda *args:'PLAYING'
    tr = track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    engine.tracker.update = lambda *args,**kwargs:[tr]
    image = np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,clock.now,clock.now))
    assert len(s.pending)==1
    clock.now = 1000.01
    if interruption=='missed':tr.missed=1
    if interruption=='overlap':tr.candidate.suspected_overlap=True
    if interruption=='unstable_keys':tr.stable_keys=['D']
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert not s.pending and not actuator.calls
    assert engine.tap_rule.bindings[1]=='F'
    tr.missed=0;tr.candidate.suspected_overlap=False;tr.stable_keys=['D','F']
    clock.now = 1000.02
    engine.process(CapturedFrame(2,image,clock.now,clock.now))
    assert len(s.pending)==1
    clock.now = 1000.04;s.poll()
    assert actuator.calls==[('down','F')]
    clock.now = 1000.045
    engine.process(CapturedFrame(3,image,clock.now,clock.now))
    assert not s.pending
    s.close()
    assert actuator.calls==[('down','F'),('up','F')]


def test_reacquisition_after_disarming_cannot_revive_previous_arm(setup_rule,make_candidate):
    config,g = setup_rule
    clock,actuator,s = scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine = LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update = lambda *args:'PLAYING'
    tr = track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    engine.tracker.update = lambda *args,**kwargs:[tr]
    image = np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,clock.now,clock.now))
    clock.now = 1000.01;tr.missed=1
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert not s.pending
    s.toggle();s.toggle();s.poll()
    clock.now = 1000.02;tr.missed=0
    engine.process(CapturedFrame(2,image,clock.now,clock.now))
    assert not s.pending and not actuator.calls


@pytest.mark.parametrize('loss',['note_occlusion','nearline_outlier','nearline_motion_outliers','nearline_hit_drift',
                                 'confirmed_hit_drift','confirmed_invalid_eta','outlier_far_from_line','invalid_key',
                                 'rejected','focus','roi','stale','overlap','special'])
def test_short_commit_only_survives_note_occlusion_with_fresh_playing_context(setup_rule,make_candidate,loss):
    config,g = setup_rule
    clock,actuator,s = scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine = LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update = lambda *args:'PLAYING'
    tr = track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    tr.candidate = replace(tr.candidate,bbox=(280,308,60,7))
    tr.bbox=tr.candidate.bbox;tr.history=[(1000.,311.5,.4)]
    engine.tracker.update = lambda *args,**kwargs:[tr]
    image = np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert engine.occlusion_commits and len(s.pending)==1
    clock.now=1000.02
    if loss=='note_occlusion':tr.missed=1
    if loss in ('nearline_outlier','nearline_motion_outliers','nearline_hit_drift','outlier_far_from_line','invalid_key'):
        tr.status='tentative'
        reason={'nearline_motion_outliers':'motion_outliers','nearline_hit_drift':'hit_time_drift'}.get(loss,'latest_position_outlier')
        tr.prediction=Prediction(reason=reason)
    if loss in ('confirmed_hit_drift','confirmed_invalid_eta'):
        tr.prediction=Prediction(reason='hit_time_drift' if loss=='confirmed_hit_drift' else 'unstable_eta')
    if loss=='rejected':tr.status='rejected'
    if loss=='outlier_far_from_line':
        tr.candidate=replace(tr.candidate,bbox=(280,280,60,7))
        tr.history=[(1000.02,283.5,.4)]
    if loss=='invalid_key':tr.candidate.candidate_keys=['D']
    if loss=='overlap':tr.candidate.suspected_overlap=True
    if loss=='special':tr.candidate.note_type='unknown';tr.candidate.appearance='green_candidate'
    if loss=='stale':clock.now=1000.08
    engine.process(CapturedFrame(1,image,1000.02,1000.02),focused=loss!='focus',roi_valid=loss!='roi')
    if loss in ('note_occlusion','nearline_outlier','nearline_motion_outliers','nearline_hit_drift',
                'confirmed_hit_drift','confirmed_invalid_eta'):
        assert len(s.pending)==1
        clock.now=1000.04;s.poll()
        assert actuator.calls==[('down','F')]
    else:
        assert not s.pending and not actuator.calls
    s.close()
    assert not s.held


def test_committed_deadline_cannot_extend_past_bounded_horizon(setup_rule,make_candidate):
    config,g=setup_rule
    rule=AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))
    assert rule.commit_horizon==.1
    config['live']['tap_rule']['commit_horizon_ms']=101
    with pytest.raises(ValueError):AnyCoveredKeyRule.from_config(config,geometry_hash(g.document))


def test_range_rule_uses_current_and_temporally_stable_key_intersection(setup_rule,make_candidate):
    config,g=setup_rule
    tr=track(make_candidate,1,['D','F'],.30,.49)
    tr.stable_keys=['D']
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True)==(('D',),'')
    assert track_options(tr,1000.,set('SDFJKL'),{})==((),'ambiguous_or_unstable_keys')
    tr.stable_keys=['S']
    assert track_options(tr,1000.,set('SDFJKL'),{},allow_range=True)==((),'ambiguous_or_unstable_keys')


@pytest.mark.parametrize('activation',['same_arm','off_at_first','rearmed'])
def test_initially_unready_event_can_only_become_eligible_in_its_original_arm(setup_rule,make_candidate,activation):
    config,g=setup_rule
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True)
    if activation!='off_at_first':s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    tr.stable_keys=['S']
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    _,_,events,_=engine.process(CapturedFrame(0,image,1000.,1000.))
    assert events[0]['abstain_reason']=='ambiguous_or_unstable_keys' and not s.pending
    if activation=='off_at_first':s.toggle();s.poll()
    if activation=='rearmed':s.toggle();s.toggle();s.poll()
    clock.now=1000.01;tr.stable_keys=['F']
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert bool(s.pending)==(activation=='same_arm')
    clock.now=1000.04;s.poll()
    assert actuator.calls==([('down','F')] if activation=='same_arm' else [])
    s.close()


@pytest.mark.parametrize('fragment',['cyan_bar','yellow_bar','green_candidate','disjoint','new_uncommitted'])
def test_partial_colored_edge_only_maintains_existing_nearline_tap(setup_rule,make_candidate,fragment):
    config,g=setup_rule
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    tr.candidate=replace(tr.candidate,bbox=(280,308,60,7))
    tr.history=[(1000.,311.5,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    if fragment!='new_uncommitted':
        engine.process(CapturedFrame(0,image,1000.,1000.))
        assert engine.occlusion_commits
    clock.now=1000.02
    tr.status='tentative';tr.prediction=Prediction(reason='latest_position_outlier')
    tr.candidate=replace(tr.candidate,note_type='unknown',appearance=fragment if fragment in
                         ('cyan_bar','yellow_bar','green_candidate') else 'cyan_bar',
                         bbox=(280,308,15,2),u_min=.30,u_max=.325,candidate_keys=['D'])
    tr.history=[(1000.02,309.,.3125)]
    if fragment=='disjoint':tr.candidate=replace(tr.candidate,u_min=.01,u_max=.05,candidate_keys=['S'])
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    keep=fragment in ('cyan_bar','yellow_bar')
    assert bool(s.pending)==keep
    clock.now=1000.04;s.poll()
    assert actuator.calls==([('down','F')] if keep else [])
    s.close()


@pytest.mark.parametrize('fragment',['inside_body','inside_body_tap','above_body','disjoint_span','wrong_color'])
def test_committed_head_keeps_its_key_when_only_an_inner_upper_edge_remains(
        setup_rule,make_candidate,fragment):
    config,g=setup_rule
    config['live']['input_advance_px']=15
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['K','L'],.6699,.9961,hit=1000.085)
    tr.candidate=replace(tr.candidate,bbox=(452,278,177,27),appearance='yellow_bar',note_type='tap')
    tr.history=[(1000.,291.5,.833)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    original=next(iter(s.pending.values()))
    assert original.keys==('K',) and engine.occlusion_commits
    clock.now=1000.065
    y=270 if fragment=='above_body' else 289 if fragment=='inside_body_tap' else 293
    height=5 if fragment=='inside_body_tap' else 1
    tr.candidate=replace(tr.candidate,bbox=(541,y,84,height),u_min=.8318,u_max=.9857,
                         candidate_keys=['L'],note_type='tap' if fragment=='inside_body_tap' else 'unknown',
                         appearance='green_candidate' if fragment=='wrong_color' else 'yellow_bar')
    if fragment=='disjoint_span':
        tr.candidate=replace(tr.candidate,u_min=.01,u_max=.15,candidate_keys=['S'])
    tr.status='tentative';tr.missed=0;tr.last_time=clock.now
    tr.history=[(clock.now,y+height/2,.91)]
    tr.prediction=Prediction(reason='latest_position_outlier')
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    if fragment in ('inside_body','inside_body_tap'):
        assert next(iter(s.pending.values()))==original
        tr.status='lost';tr.missed=1;clock.now=1000.08
        engine.process(CapturedFrame(2,image,clock.now,clock.now))
        clock.now=original.hit_at;s.poll()
        assert actuator.calls==[('down','K')]
    else:
        assert not s.pending and not actuator.calls
    s.close()


@pytest.mark.parametrize('bottom,committed',[(311,True),(306,False)])
def test_commit_entry_uses_existing_jitter_corridor(setup_rule,make_candidate,bottom,committed):
    config,g=setup_rule
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    tr.candidate=replace(tr.candidate,bbox=(280,bottom-7,60,7))
    tr.history=[(1000.,bottom-3.5,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    engine.process(CapturedFrame(0,np.zeros((404,720,3),np.uint8),1000.,1000.))
    assert bool(engine.occlusion_commits)==committed
    s.close()


def test_capture_processing_delay_cannot_expire_commit_before_its_own_deadline(setup_rule,make_candidate):
    config,g=setup_rule
    clock,actuator,s=scheduler()
    clock.now=1000.01
    s.update_context(1000.,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.108)
    tr.candidate=replace(tr.candidate,bbox=(280,308,60,7))
    tr.history=[(1000.,311.5,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.001))
    assert engine.occlusion_commits and len(s.pending)==1
    for i,captured,processed in [(1,1000.08,1000.09),(2,1000.10,1000.105)]:
        tr.missed=i;clock.now=processed
        engine.process(CapturedFrame(i,image,captured,captured+.001))
        assert len(s.pending)==1 and not actuator.calls
    clock.now=1000.108;s.poll()
    assert actuator.calls==[('down','F')]
    s.close();assert actuator.calls[-1]==('up','F')


def test_fresh_frame_after_committed_deadline_does_not_revive_expired_action(setup_rule,make_candidate):
    config,g=setup_rule
    clock,actuator,s=scheduler()
    s.update_context(1000.,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.04)
    tr.candidate=replace(tr.candidate,bbox=(280,308,60,7))
    tr.history=[(1000.,311.5,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert engine.occlusion_commits
    tr.missed=1;clock.now=1000.06
    engine.process(CapturedFrame(1,image,1000.059,1000.059))
    assert not s.pending and not actuator.calls


@pytest.mark.parametrize('track_present',[True,False])
def test_recent_confirmed_head_keeps_its_scheduled_key_through_detector_dropout(
        setup_rule,make_candidate,track_present):
    config,g=setup_rule
    config['live'].update(input_advance_px=15,dropout_grace_ms=200,dropout_min_y=265)
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.15)
    tr.candidate=replace(tr.candidate,bbox=(280,277,60,6))
    tr.history=[(1000.,280.,.4)]
    current=[tr]
    engine.tracker.update=lambda *args,**kwargs:current
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert len(s.pending)==1 and engine.dropout_commits and not engine.occlusion_commits
    tr.status='lost';tr.missed=1
    if not track_present:current=[]
    clock.now=1000.05
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert len(s.pending)==1
    clock.now=1000.14
    engine.process(CapturedFrame(2,image,clock.now,clock.now))
    assert len(s.pending)==1
    clock.now=1000.15;s.poll()
    assert actuator.calls==[('down','F')]
    s.close();assert actuator.calls[-1]==('up','F')


@pytest.mark.parametrize('focused',[True,False])
def test_ordinary_tap_early_dropout_keeps_original_deadline_only_with_focus(
        setup_rule,make_candidate,focused):
    config,g=setup_rule
    config['live']['speculative_taps']['enabled']=True
    config['live'].update(input_advance_px=15,dropout_grace_ms=200,dropout_min_y=265,
                          tap_dropout_grace_ms=250,tap_dropout_min_y=250)
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.24)
    tr.candidate=replace(tr.candidate,bbox=(280,249,60,6),appearance='cyan_bar',note_type='tap')
    tr.history=[(1000.,252.,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert len(s.pending)==1 and engine.dropout_commits and not engine.occlusion_commits
    tr.status='lost';tr.missed=1
    clock.now=1000.05
    engine.process(CapturedFrame(1,image,clock.now,clock.now),focused=focused)
    assert bool(s.pending)==focused
    if focused:
        clock.now=1000.23
        engine.process(CapturedFrame(2,image,clock.now,clock.now))
        clock.now=1000.24;s.poll()
        assert actuator.calls==[('down','F')]
    else:
        clock.now=1000.24;s.poll()
        assert not actuator.calls
    s.close()


def test_early_dropout_extension_does_not_apply_to_unknown_fragment(setup_rule,make_candidate):
    config,g=setup_rule
    config['live']['speculative_taps']['enabled']=True
    config['live'].update(input_advance_px=15,dropout_grace_ms=200,dropout_min_y=265,
                          tap_dropout_grace_ms=250,tap_dropout_min_y=250)
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.24)
    tr.candidate=replace(tr.candidate,bbox=(280,272,60,6),appearance='cyan_bar',note_type='unknown')
    tr.history=[(1000.,275.,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert len(s.pending)==1 and not engine.dropout_commits
    tr.status='lost';tr.missed=1;clock.now=1000.05
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert not s.pending and not actuator.calls
    s.close()


@pytest.mark.parametrize('loss',['focus','late','incompatible_observation','past_line'])
def test_dropout_grace_never_overrides_context_or_new_conflicting_evidence(
        setup_rule,make_candidate,loss):
    config,g=setup_rule
    config['live'].update(input_advance_px=15,dropout_grace_ms=200,dropout_min_y=265)
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.15)
    tr.candidate=replace(tr.candidate,bbox=(280,277,60,6))
    tr.history=[(1000.,280.,.4)]
    current=[tr]
    engine.tracker.update=lambda *args,**kwargs:current
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert len(s.pending)==1
    if loss=='late':clock.now=1000.21;current=[]
    else:clock.now=1000.05
    if loss=='incompatible_observation':
        tr.status='tentative';tr.missed=0;tr.last_time=clock.now
        tr.candidate=replace(tr.candidate,candidate_keys=['S'],u_min=.01,u_max=.1)
    else:current=[]
    if loss=='past_line':
        tr.reason='past_hit_line';engine.tracker.finished.append(tr)
    engine.process(CapturedFrame(1,image,clock.now,clock.now),focused=loss!='focus')
    assert not s.pending and not actuator.calls
    s.close()


@pytest.mark.parametrize('change,retained',[
    ('same_bar',True),('wrong_key',False),('wrong_color',False),
    ('past_line',False),('expired',False)])
def test_scheduled_nearline_tap_can_survive_only_a_compatible_position_outlier(
        setup_rule,make_candidate,change,retained):
    config,g=setup_rule
    config['live'].update(input_advance_px=15,dropout_grace_ms=200,dropout_min_y=265)
    clock,actuator,s=scheduler()
    s.update_context(clock.now,'PLAYING',True);s.toggle();s.poll()
    engine=LiveEngine(config,g,s,clock=lambda:clock.now,detector=lambda *args:[])
    engine.gate.update=lambda *args:'PLAYING'
    tr=track(make_candidate,1,['D','F'],.30,.49,hit=1000.15)
    tr.candidate=replace(tr.candidate,bbox=(280,277,60,6))
    tr.history=[(1000.,280.,.4)]
    engine.tracker.update=lambda *args,**kwargs:[tr]
    image=np.zeros((404,720,3),np.uint8)
    engine.process(CapturedFrame(0,image,1000.,1000.))
    assert len(s.pending)==1 and engine.dropout_commits
    clock.now=1000.21 if change=='expired' else 1000.02
    tr.status='tentative';tr.last_time=clock.now
    tr.prediction=Prediction(reason='latest_position_outlier')
    tr.history=[(clock.now,320. if change=='past_line' else 288.,.4)]
    tr.candidate=replace(tr.candidate,bbox=(280,317 if change=='past_line' else 285,60,6),
                         candidate_keys=['S'] if change=='wrong_key' else ['D','F'],
                         appearance='pink_candidate' if change=='wrong_color' else 'cyan_bar')
    engine.process(CapturedFrame(1,image,clock.now,clock.now))
    assert bool(s.pending)==retained
    if retained:
        tr.status='lost';tr.missed=1
        clock.now=1000.14
        engine.process(CapturedFrame(2,image,clock.now,clock.now))
        assert len(s.pending)==1
        clock.now=1000.15;s.poll()
        assert actuator.calls==[('down','F')]
    else:
        assert not actuator.calls
    s.close()
