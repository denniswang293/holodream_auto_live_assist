import pytest

from src.timing_estimator import LinearTimingEstimator


def test_linear_timing_estimator_uses_capture_timestamps_and_is_shadow_only():
    estimator = LinearTimingEstimator(window=5, min_velocity=20)
    observations = [(10.0, 100.0, .4), (10.02, 106.0, .4),
                    (10.04, 112.0, .4), (10.06, 118.0, .4)]
    result = estimator.estimate(observations, 130.0, 10.06)
    assert result.reason == "ok"
    assert result.velocity == pytest.approx(300.0)
    assert result.eta == pytest.approx(0.04)
    assert result.hit_at == pytest.approx(10.10)


def test_linear_timing_uses_last_valid_observation_after_dropout():
    estimator = LinearTimingEstimator(window=5, min_velocity=20, max_observation_age_s=.20)
    observations = [(10.0, 100.0, .4), (10.05, 110.0, .4), (10.10, 120.0, .4)]
    result = estimator.estimate(observations, 140.0, 10.18, now=10.18)
    assert result.reason == "ok"
    assert result.hit_at == pytest.approx(10.20)


def test_linear_timing_rejects_expired_observation():
    estimator = LinearTimingEstimator(max_observation_age_s=.10)
    observations = [(10.0, 100.0, .4), (10.02, 106.0, .4), (10.04, 112.0, .4)]
    result = estimator.estimate(observations, 140.0, 10.20, now=10.20)
    assert result.reason == "stale_observation"
    assert result.hit_at is None


def test_linear_timing_rejects_nonpositive_eta_when_target_is_behind():
    estimator = LinearTimingEstimator()
    observations = [(10.0, 100.0, .4), (10.02, 106.0, .4), (10.04, 112.0, .4)]
    result = estimator.estimate(observations, 110.0, 10.04)
    assert result.reason == "target_not_future"
    assert result.eta is None


def test_linear_timing_handles_low_fps_and_speed_change():
    estimator = LinearTimingEstimator(window=5, min_velocity=20)
    observations = [(1.0, 100.0, .4), (1.10, 115.0, .4),
                    (1.30, 145.0, .4), (1.50, 175.0, .4)]
    result = estimator.estimate(observations, 205.0, 1.50, now=1.50)
    assert result.reason == "ok"
    assert result.velocity > 100
    assert result.eta is not None


def test_linear_timing_estimator_rejects_static_gray_background():
    estimator = LinearTimingEstimator()
    observations = [(1.0, 150.0, .4), (1.02, 150.0, .4), (1.04, 150.0, .4)]
    result = estimator.estimate(observations, 300.0, 1.04)
    assert result.hit_at is None
    assert result.reason == "invalid_or_reverse_motion"


def test_linear_timing_ignores_malformed_tail_and_uses_last_valid_timestamp():
    estimator = LinearTimingEstimator(max_observation_age_s=.20)
    observations = [(2.0, 100.0, .4), (2.05, 110.0, .4),
                    (2.10, 120.0, .4), (float("nan"), float("nan"), .4)]
    result = estimator.estimate(observations, 140.0, 2.15, now=2.15)
    assert result.reason == "ok"
    assert result.hit_at == pytest.approx(2.20)
