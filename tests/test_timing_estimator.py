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


def test_linear_timing_estimator_rejects_static_gray_background():
    estimator = LinearTimingEstimator()
    observations = [(1.0, 150.0, .4), (1.02, 150.0, .4), (1.04, 150.0, .4)]
    result = estimator.estimate(observations, 300.0, 1.04)
    assert result.hit_at is None
    assert result.reason == "invalid_or_reverse_motion"
