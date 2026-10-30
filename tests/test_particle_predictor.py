import math

import numpy as np
import pytest

from src.particle_predictor import ParticlePredictor


def trajectory(speed=300., seed=20261030, count=128):
    pf = ParticlePredictor({"count": count, "max_posterior_width_ms": 100},
                           seed=seed, track_id=17, physical_hit_y=325.5)
    history = []
    out = None
    for i, t in enumerate((0., .016, .035, .052, .071, .089, .109, .128, .148)):
        history.append((t, 120 + speed*t, .4))
        out = pf.update(history, 310.5, physical_hit_y=325.5)
    return pf, out


def test_particle_eta_uses_capture_timestamp_and_separate_physical_line():
    _, p = trajectory()
    assert p.predictor_mode == "particle"
    assert p.eta_p10 <= p.eta_p50 <= p.eta_p90
    assert p.valid_crossing_mass >= .95
    assert p.hit_time == pytest.approx(.635, abs=.025)
    assert p.physical_hit_time > p.hit_time
    assert p.eta == pytest.approx(p.hit_time - .148)


def test_fixed_seed_replay_is_repeatable():
    a, pa = trajectory(seed=123)
    b, pb = trajectory(seed=123)
    assert np.array_equal(a.y, b.y)
    assert pa.hit_time == pb.hit_time
    assert pa.eta_p10 == pb.eta_p10


def test_outlier_is_rejected_without_becoming_a_measurement():
    pf, before = trajectory()
    t = pf.last_time + .016
    rejected = pf.update([(t, pf._prediction(310.5, pf.last_time, "").fitted_y + 60, .4)], 310.5)
    assert rejected.measurement_status == "REJECTED_MEASUREMENT"
    assert rejected.hit_time is not None
    assert abs(rejected.hit_time - (before.hit_time + .016)) < .04


def test_nonmonotonic_timestamp_fails_closed():
    pf, _ = trajectory()
    p = pf.update([(pf.last_time, 220, .4)], 310.5)
    assert p.measurement_status == "REJECTED_TIMESTAMP"
    assert p.reason != ""


def test_coast_uncertainty_grows_and_expires():
    pf, _ = trajectory()
    near = pf.coast_to(pf.last_time + .01, 310.5)
    far = pf.coast_to(pf.last_time + .07, 310.5)
    assert far.eta_p90 - far.eta_p10 > near.eta_p90 - near.eta_p10
    expired = pf.coast_to(pf.last_time + .2, 310.5)
    assert expired.reason == "PF_COAST_EXPIRED"
    assert expired.hit_time is None


def test_past_target_and_invalid_particle_parameters_are_not_clamped_to_now():
    pf, _ = trajectory()
    assert pf._prediction(1., pf.last_time, "").hit_time is None
    assert pf._prediction(1., pf.last_time, "").reason == "ALREADY_PAST_TRIGGER"
    with pytest.raises(ValueError):
        ParticlePredictor({"count": 8})
