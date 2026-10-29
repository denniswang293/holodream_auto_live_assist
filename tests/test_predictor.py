import pytest
from src.predictor import Predictor


def history(count=11, start=200, speed=300):
    return [(i/60,start+speed*i/60,0.4) for i in range(count)]


def test_known_linear_trajectory():
    prediction = Predictor().predict(history(),352)
    assert prediction.velocity == pytest.approx(300)
    assert prediction.hit_time == pytest.approx((352-200)/300)


def test_requires_at_least_five_observations():
    assert Predictor().predict(history(4),352).eta is None


def test_last_two_frame_jitter_does_not_launch_eta():
    clean = history()
    jittered = clean.copy()
    jittered[-2] = (clean[-2][0],clean[-2][1]+3,0.4)
    jittered[-1] = (clean[-1][0],clean[-1][1]-3,0.4)
    old_two_frame_speed = (jittered[-1][1]-jittered[-2][1])*60
    assert old_two_frame_speed < 0  # Previous implementation would lose ETA.
    a,b = Predictor().predict(clean,352),Predictor().predict(jittered,352)
    assert b.hit_time is not None
    assert abs(a.hit_time-b.hit_time) < 0.025


def test_interior_outlier_does_not_corrupt_fit():
    observations = history()
    t,y,u = observations[5]
    observations[5] = (t,y+50,u)
    result = Predictor().predict(observations,352)
    assert result.velocity == pytest.approx(300)
    assert result.hit_time == pytest.approx((352-200)/300)


def test_latest_outlier_has_no_eta():
    observations = history()
    t,y,u = observations[-1]
    observations[-1] = (t,y+50,u)
    result = Predictor().predict(observations,352)
    assert result.eta is None
    assert result.reason == "latest_position_outlier"


def test_past_hit_line_is_not_clamped_to_zero():
    result = Predictor().predict(history(start=320),352)
    assert result.eta is None
    assert result.hit_time is None
    assert result.reason == "past_hit_line"


@pytest.mark.parametrize("speed", [0,-100,2500])
def test_stationary_backward_and_implausible_motion_have_no_eta(speed):
    assert Predictor().predict(history(speed=speed),352).eta is None


def test_unstable_fit_is_rejected():
    data = [(i/60,200+40*i/60+[0,1,-2,3,-1,2,-3,1,0,3,-1][i],0.4) for i in range(11)]
    result = Predictor({"max_uncertainty_s":0.001}).predict(data,352)
    assert result.eta is None


def test_irregular_timestamps_use_elapsed_time():
    times = [0,.018,.04,.071,.10,.145,.18]
    result = Predictor().predict([(t,200+300*t,.4) for t in times],352)
    assert result.velocity == pytest.approx(300)


def test_duplicate_timestamps_are_rejected():
    data = history()
    data[5] = (data[4][0],data[5][1],.4)
    assert Predictor().predict(data,352).reason == "invalid_or_short_timestamps"
