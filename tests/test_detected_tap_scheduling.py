from src.live_engine import track_options

from tests.test_pf_eta_eligibility import good_particle_track


def test_confirmed_tap_with_valid_pf_eta_is_not_blocked_by_empty_hit_history(make_candidate):
    track = good_particle_track(make_candidate)
    assert track_options(track, 1.0, set("SDFJKL"), {"max_eta_s": .45},
                         allow_range=True) == (("F",), "")


def test_invalid_pf_evidence_has_specific_schedule_rejection(make_candidate):
    track = good_particle_track(make_candidate)
    track.prediction = track.prediction.__class__(**{
        **track.prediction.__dict__, "valid_crossing_mass": .2})
    assert track_options(track, 1.0, set("SDFJKL"), {"max_eta_s": .45},
                         allow_range=True) == ((), "particle_crossing_mass_too_low")
