import numpy as np

from src.lane_filter import LaneFilter
from src.model import Detection, Geometry


def test_observations_use_current_source_provenance_and_no_action_inputs(monkeypatch):
    geometry = Geometry()
    lane_filter = LaneFilter(geometry)
    monkeypatch.setattr(lane_filter.perception, "detect", lambda _: [
        Detection((20, 100, 40, 12), "cyan", "tap", ("S",), .8,
                  plane_width=geometry.plane_width)])
    image = np.zeros((404, 720, 3), np.uint8)
    obs, masks, _ = lane_filter.process(image, run_id="r", source_frame=3,
        video_frame=2, captured_at=1.0, acquired_at=1.01)
    assert len(obs) == 1
    assert (obs[0].run_id, obs[0].source_frame, obs[0].video_frame) == ("r", 3, 2)
    assert (obs[0].captured_at, obs[0].acquired_at) == (1.0, 1.01)
    assert obs[0].role == "TAP_FACE" and obs[0].fresh_observation
    assert np.count_nonzero(masks["tap_face"]) > 0
    assert not np.count_nonzero(masks["hold_head"])


def test_capture_order_is_validated_before_perception(monkeypatch):
    lane_filter = LaneFilter(Geometry())
    monkeypatch.setattr(lane_filter.perception, "detect", lambda _: (_ for _ in ()).throw(AssertionError()))
    try:
        lane_filter.process(np.zeros((404, 720, 3), np.uint8), run_id="r",
            source_frame=1, video_frame=1, captured_at=2.0, acquired_at=1.0)
    except ValueError as exc:
        assert "acquired_at" in str(exc)
    else:
        raise AssertionError("reversed capture/acquired timestamps must be rejected")
