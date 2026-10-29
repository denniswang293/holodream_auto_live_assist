from src.events import EventCollector
from src.predictor import Prediction
from src.tracker import Track, Tracker


def test_stationary_light_is_rejected(tracker,make_candidate):
    collector = EventCollector()
    for i in range(40):
        tracks = tracker.update([make_candidate(y=250+(i%3-1))],i/60)
        for tr in tracks:
            collector.consider(tr,i,"PLAYING")
    assert len(tracker.tracks) == 1
    tr = tracker.tracks[0]
    assert tr.status == "rejected"
    assert tr.reason == "stationary_background"
    assert not tr.was_confirmed
    assert tr.eta() is None
    assert collector.rows == []


def test_global_matching_does_not_let_older_track_steal(tracker,make_candidate):
    tracker.update([make_candidate(u=.30,keys=["D","F"]),make_candidate(u=.36,keys=["D","F"])],0)
    tracks = tracker.update([make_candidate(y=105,u=.34,keys=["D","F"]),
                             make_candidate(y=105,u=.24,keys=["D","F"])],1/60)
    assert len(tracks) == 2
    assert tracks[0].history[-1][2] == .24
    assert tracks[1].history[-1][2] == .34


def test_adjacent_notes_keep_ids_when_candidate_order_reverses(tracker,make_candidate):
    for i in range(20):
        candidates = [make_candidate(y=100+i*5,u=.35),make_candidate(y=105+i*5,u=.53)]
        tracks = tracker.update(candidates if i%2 else candidates[::-1],i/60)
        assert len(tracks) == 2
        if i == 0:
            identities = {round(tr.history[-1][2],2):tr.track_id for tr in tracks}
        assert all(tr.track_id == identities[round(tr.history[-1][2],2)] for tr in tracks)


def test_short_occlusion_recovers_same_id(tracker,make_candidate):
    for i in range(7):
        tracker.update([make_candidate(y=100+i*5)],i/60)
    note_id = tracker.tracks[0].track_id
    assert tracker.tracks[0].status == "confirmed"
    tracker.update([],7/60)
    assert tracker.tracks[0].status == "lost"
    tracker.update([],8/60)
    tracks = tracker.update([make_candidate(y=145)],9/60)
    assert len(tracks) == 1
    assert tracks[0].track_id == note_id
    assert tracks[0].status == "confirmed"


def test_impossible_backward_jump_does_not_corrupt_track(tracker,make_candidate):
    for i in range(7):
        tracker.update([make_candidate(y=150+i*5)],i/60)
    old = tracker.tracks[0]
    tracker.update([make_candidate(y=100)],7/60)
    assert old.missed == 1
    assert old.history[-1][1] == 180
    assert tracker.next_id == 3


def test_width_jump_and_incompatible_lane_are_not_matched(tracker,make_candidate):
    tracker.update([make_candidate(y=150,u=.3)],0)
    original = tracker.tracks[0]
    tracker.update([make_candidate(y=155,u=.8)],1/60)
    assert original.missed == 1
    assert len(tracker.tracks) == 2


def test_gate_closes_all_tracks(tracker,make_candidate):
    tracker.update([make_candidate()],0)
    assert tracker.update([],1/60,playing=False) == []
    assert tracker.finished[0].status == "completed"
    assert tracker.finished[0].reason == "gameplay_gate_closed"


def test_overlapping_key_jitter_is_smoothed(tracker,make_candidate):
    for i in range(10):
        keys = ["F","J"] if i%3 == 0 else ["F"]
        tracker.update([make_candidate(y=100+i*5,keys=keys)],i/60)
    assert tracker.tracks[0].stable_keys == ["F"]


def test_rejected_background_does_not_follow_moving_note(tracker,make_candidate):
    for i in range(20):
        tracker.update([make_candidate(y=250)],i/60)
    rejected_id = tracker.tracks[0].track_id
    for i in range(20,30):
        tracker.update([make_candidate(y=250+5*(i-19))],i/60)
    moving = [tr for tr in tracker.tracks if tr.status == "confirmed"]
    assert len(moving) == 1
    assert moving[0].track_id != rejected_id


def test_past_line_completes_track(tracker,make_candidate):
    for i in range(12):
        tracker.update([make_candidate(y=310+i*4)],i/60)
    assert any(tr.reason == "past_hit_line" for tr in tracker.finished)


def test_early_prediction_target_does_not_end_track_before_physical_judgment(make_candidate):
    tracker=Tracker({'completion_y':325.5,'max_gap_s':.16},310.5)
    for i in range(11):
        tracker.update([make_candidate(y=270+i*5)],i/60)
    assert len(tracker.tracks)==1
    assert tracker.tracks[0].history[-1][1]==320
    assert tracker.tracks[0].prediction.reason=='past_hit_line'
    assert not any(tr.reason=='past_hit_line' for tr in tracker.finished)
    tracker.update([make_candidate(y=330)],11/60)
    assert any(tr.reason=='past_hit_line' for tr in tracker.finished)


def test_expired_occlusion_does_not_reuse_id(tracker,make_candidate):
    tracker.update([make_candidate()],0)
    tracker.update([],0.2)
    tracker.update([make_candidate(y=160)],0.21)
    assert tracker.tracks[0].track_id == 2


def test_pale_core_flicker_keeps_id_without_upgrading_unknown(tracker,make_candidate):
    for i in range(15):
        appearance = "neutral_candidate" if i%3 == 0 else "cyan_bar"
        tracker.update([make_candidate(y=100+i*5,appearance=appearance)],i/60)
        assert len(tracker.tracks) == 1
        assert tracker.tracks[0].track_id == 1
        assert tracker.tracks[0].candidate.note_type == ("unknown" if appearance == "neutral_candidate" else "tap")


def test_assist_tap_recovers_after_old_hit_time_outlier(make_candidate):
    class StablePredictor:
        cfg = {'min_velocity':20}
        def predict(self,history,hit_y):
            return Prediction(velocity=300,eta=.4,hit_time=1.04,uncertainty=.01,reason='')

    def observed(appearance,config):
        candidate=make_candidate(y=150,appearance=appearance)
        tr=Track(1,candidate,history=[(.08,145.,.4)],bbox=candidate.bbox,
                 status='confirmed',observations=5,first_time=0,last_time=.08,
                 hit_history=[1.5,1.01,1.02,1.03])
        tr.observe(candidate,.1,StablePredictor(),352,config)
        return tr

    config={'confirm_observations':5,'max_hit_drift_s':.15,'tap_hit_drift_window':3}
    assert observed('cyan_bar',config).prediction.hit_time==1.04
    assert observed('cyan_bar',{**config,'tap_hit_drift_window':5}).prediction.reason=='hit_time_drift'
    assert observed('green_candidate',config).prediction.reason=='hit_time_drift'
