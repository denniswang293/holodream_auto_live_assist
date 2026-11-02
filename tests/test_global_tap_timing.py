from types import SimpleNamespace

import pytest

from src.global_tap_timing import GlobalTapTimingEstimator
from src.particle_predictor import ParticlePredictor


def track(track_id, history, *, status="confirmed", note_type="tap", missed=0):
    return SimpleNamespace(track_id=track_id, history=history, status=status,
                           confirmed_note_type=note_type, missed=missed)


def estimator(**overrides):
    config = {
        "enabled": True,
        "mode": "shadow",
        "min_tracks": 2,
        "min_samples": 3,
        "max_observation_age_ms": 180,
        "max_eta_s": .45,
    }
    config.update(overrides)
    return GlobalTapTimingEstimator(config)


def test_shared_model_keeps_independent_hit_times_and_ordering():
    first = track(1, [(1.00, 100), (1.10, 110), (1.20, 120)])
    second = track(2, [(1.05, 70), (1.15, 80), (1.25, 90)])
    modeler = estimator()
    model = modeler.update([first, second], trigger_y=130,
                           capture_timestamp=1.26, now=1.26)
    assert model.ready is True
    a = modeler.estimate(first, trigger_y=130, now=1.26)
    b = modeler.estimate(second, trigger_y=130, now=1.26)
    assert a.status == b.status == "AVAILABLE"
    assert a.hit_at == pytest.approx(1.30)
    assert b.hit_at == pytest.approx(1.65)
    assert a.hit_at < b.hit_at


def test_irregular_fps_and_processing_delay_do_not_shift_hit_at():
    first = track(1, [(1.00, 100), (1.07, 107), (1.21, 121)])
    second = track(2, [(1.00, 80), (1.07, 87), (1.21, 101)])
    modeler = estimator()
    modeler.update([first, second], trigger_y=151, capture_timestamp=1.22, now=1.22)
    result = modeler.estimate(first, trigger_y=151, now=1.26)
    assert result.status == "AVAILABLE"
    # The timestamp comes from the last observation, not processing time.
    assert result.hit_at == pytest.approx(1.51)


@pytest.mark.parametrize("bad_track", [
    track(1, [(1.0, 100), (1.1, 110), (1.2, 120)], status="coasting"),
    track(1, [(1.0, 100), (1.1, 110), (1.2, 120)], missed=1),
    track(1, [(1.0, 100), (1.1, 110), (1.2, 120)], note_type="hold"),
])
def test_invalid_track_state_is_excluded_but_valid_single_track_can_bootstrap(bad_track):
    good = track(2, [(1.0, 100), (1.1, 110), (1.2, 120)])
    model = estimator().update([bad_track, good], trigger_y=150,
                               capture_timestamp=1.21, now=1.21)
    assert model.ready is True
    assert model.independent_tracks == 1


def test_stale_coasting_and_nonnumeric_observations_are_rejected():
    stale = track(1, [(1.0, 100), (1.1, 110), (1.2, 120)])
    good = track(2, [(1.30, 90), (1.35, 95), (1.40, 100)])
    good2 = track(4, [(1.30, 80), (1.35, 85), (1.40, 90)])
    modeler = estimator()
    modeler.update([stale, good, good2], trigger_y=150, capture_timestamp=1.45, now=1.45)
    result = modeler.estimate(stale, trigger_y=150, now=1.45)
    assert result.status == "NOT_READY"
    assert result.reason == "stale_observation"
    malformed = track(3, [("bad", 100), (1.1, "bad"), (1.2, 120)])
    assert modeler.estimate(malformed, trigger_y=150, now=1.21).status == "NOT_READY"


def test_large_jump_and_nonlinear_speed_do_not_create_precise_eta():
    jump = track(1, [(1.0, 100), (1.1, 110), (1.2, 210)])
    other = track(2, [(1.0, 90), (1.1, 100), (1.2, 110)])
    model = estimator().update([jump, other], trigger_y=250,
                               capture_timestamp=1.21, now=1.21)
    assert model.ready is True
    nonlinear_a = track(1, [(1.0, 100), (1.1, 110), (1.2, 140)])
    nonlinear_b = track(2, [(1.0, 80), (1.1, 90), (1.2, 120)])
    model = estimator().update([nonlinear_a, nonlinear_b], trigger_y=180,
                               capture_timestamp=1.21, now=1.21)
    assert model.ready is False
    assert model.reason == "speed_variation_too_high"


def test_uncertainty_is_not_capped_and_blocks_global_eta():
    first = track(1, [(1.0, 80), (1.1, 90), (1.2, 100)])
    second = track(2, [(1.0, 80), (1.1, 92), (1.2, 104)])
    modeler = estimator(measurement_noise_px=4.0, max_uncertainty_s=.04)
    model = modeler.update([first, second], trigger_y=135,
                           capture_timestamp=1.21, now=1.21)
    assert model.ready is True
    result = modeler.estimate(first, trigger_y=135, now=1.21)
    assert result.uncertainty_s is not None
    assert result.uncertainty_s > .04
    assert result.status == "REJECTED"
    assert result.reason == "eta_uncertainty_too_high"


def test_time_uncertainty_grows_with_distance_and_stable_case_remains_available():
    near = track(1, [(1.0, 100), (1.1, 110), (1.2, 120)])
    far = track(2, [(1.0, 80), (1.1, 92), (1.2, 104)])
    modeler = estimator(max_uncertainty_s=.2)
    model = modeler.update([near, far], trigger_y=130,
                           capture_timestamp=1.21, now=1.21)
    assert model.ready is True
    near_eta = modeler.estimate(near, trigger_y=130, now=1.21)
    far_eta = modeler.estimate(far, trigger_y=130, now=1.21)
    assert near_eta.status == far_eta.status == "AVAILABLE"
    assert far_eta.uncertainty_s > near_eta.uncertainty_s


def test_zero_speed_and_nonfinite_history_never_create_model():
    zero = track(1, [(1.0, 100), (1.1, 100), (1.2, 100)])
    invalid = track(2, [(1.0, float("nan")), (1.1, float("inf")), (1.2, 120)])
    model = estimator().update([zero, invalid], trigger_y=150,
                               capture_timestamp=1.21, now=1.21)
    assert model.ready is False
    assert model.reason == "insufficient_independent_tracks"


def test_disabled_not_playing_and_active_require_dual_switch():
    disabled = GlobalTapTimingEstimator({"enabled": False})
    assert disabled.update([], trigger_y=150, capture_timestamp=1, now=1).reason == "DISABLED"
    not_playing = estimator()
    assert not_playing.update([], trigger_y=150, capture_timestamp=1, now=1,
                              playing=False).reason == "NOT_PLAYING"
    active = estimator(mode="active", allow_active=False)
    assert active.active_enabled is False
    assert estimator(mode="active", allow_active=True).active_enabled is True


def test_particle_tracking_only_does_not_emit_tap_eta_fields():
    pf = ParticlePredictor({"count": 64, "min_real_observations": 3},
                           track_id=7, physical_hit_y=325.5,
                           timing_enabled=False)
    prediction = pf.update([(1.0, 100.0, .4), (1.05, 106.0, .4),
                            (1.10, 112.0, .4)], 295.5)
    assert prediction.measurement_status == "INITIALIZED"
    assert prediction.eta is None
    assert prediction.hit_time is None
    assert prediction.eta_p10 is None
    assert prediction.valid_crossing_mass is None
    assert prediction.fitted_y is not None
