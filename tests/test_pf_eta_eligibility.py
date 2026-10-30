from types import SimpleNamespace

import pytest

from src.live_engine import particle_eta_evidence
from src.predictor import Prediction
from src.tracker import Track


def good_particle_track(make_candidate):
    candidate = make_candidate(y=260, keys=["F"])
    track = Track(7, candidate, history=[(1.0, 260., .5)], bbox=candidate.bbox,
                  status="confirmed", stable_keys=["F"], confirmed_note_type="tap",
                  identity_state="CONFIRMED_TAP", hit_history=[])
    track.particle_filter = SimpleNamespace(
        cfg={"count": 128, "min_real_observations": 4, "max_coast_ms": 90,
             "min_valid_crossing_mass": .95, "identity_min_ess_fraction": .1},
        count=128, initialized=True, last_time=1.0)
    track.prediction = Prediction(
        hit_time=1.2, eta=.2, uncertainty=.01, eta_p10=.19, eta_p50=.2, eta_p90=.21,
        valid_crossing_mass=.98, ess=96, real_observation_count=6, coast_ms=0,
        predictor_mode="particle", measurement_status="USED", reason="")
    return track


def test_particle_posterior_is_eligible_without_legacy_hit_history(make_candidate):
    track = good_particle_track(make_candidate)
    evidence = particle_eta_evidence(track, 1.0, {"max_eta_s": .45})
    assert evidence.is_usable
    assert evidence.reject_reason == ""
    assert evidence.hit_at == 1.2
    assert evidence.credible_width_ms == pytest.approx(20)
    assert evidence.ess_fraction == pytest.approx(.75)
    assert track.hit_history == []


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("real_observation_count", 2, "particle_insufficient_real_observations"),
    ("ess", 5, "particle_ess_too_low"),
    ("valid_crossing_mass", .5, "particle_crossing_mass_too_low"),
    ("eta_p90", .30, "particle_posterior_too_wide"),
    ("reason", "PF_COAST_EXPIRED", "PF_COAST_EXPIRED"),
])
def test_particle_eta_rejects_weak_posterior_evidence(make_candidate, field, value, reason):
    track = good_particle_track(make_candidate)
    track.prediction = Prediction(**{**track.prediction.__dict__, field: value})
    evidence = particle_eta_evidence(track, 1.0, {"max_eta_s": .45})
    assert not evidence.is_usable
    assert evidence.reject_reason == reason
