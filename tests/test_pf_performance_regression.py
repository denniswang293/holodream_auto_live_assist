from src.tracker import Tracker


def test_unknown_pf_association_is_scored_once_per_track_candidate(make_candidate,monkeypatch):
    tracker=Tracker({"max_gap_s":.16,"max_missed_frames":8,"confirm_observations":4},352,
        predictor_mode="particle",particle_cfg={"count":128,"min_real_observations":4,
        "max_coast_ms":90,"deterministic_seed":93})
    for frame in range(6):
        tracks=tracker.update([make_candidate(y=150+frame*4,keys=["F"])],frame/60)
    track=tracks[0]
    calls=0
    original=track.particle_filter.identity_association_score
    def counted(*args,**kwargs):
        nonlocal calls
        calls+=1
        return original(*args,**kwargs)
    monkeypatch.setattr(track.particle_filter,"identity_association_score",counted)
    tracker.update([make_candidate(y=178,appearance="neutral_candidate",keys=["F"])],6/60)
    assert calls==1
    assert tracker.stage_times["unknown_association_s"]>=0
    assert tracker.stage_times["matching_s"]>=0
