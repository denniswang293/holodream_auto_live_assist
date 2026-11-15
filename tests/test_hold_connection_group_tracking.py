import cv2

from src.early_perception import EarlyPixelProvider
from src.model import Detection, Geometry
from src.tracking import Tracker


def _hold_pair(x, y, group_id, head_component, tail_component, color="green"):
    head = Detection(
        (x, y, 72, 18), color, "hold_head", ("D",), 1.0,
        component=head_component, plane_width=360,
        evidence=("v85_early_provider", "connected_observed_pixels"),
        semantic_candidate="hold", face_quality=0.9, full_face=True,
        connected_ribbon=True, birth_zone=True,
        connection_group_id=group_id,
    )
    tail = Detection(
        (x, 20, 72, 12), color, "hold_tail", ("D",), 1.0,
        component=tail_component, plane_width=360,
        evidence=("v85_early_provider", "connected_observed_pixels"),
        semantic_candidate="hold", face_quality=0.8, full_face=True,
        connected_ribbon=True, connection_group_id=group_id,
    )
    return head, tail


def _feed(tracker, geometry, groups, count=4):
    result = []
    for frame in range(count):
        timestamp = frame * 0.02
        detections = []
        for group_id, x, head_component, tail_component in groups:
            detections.extend(_hold_pair(x, 120 + frame * 3, group_id,
                                         head_component, tail_component))
        result = tracker.update(detections, timestamp)
    return result


def test_assist_six_second_hold_head_and_tail_keep_the_same_pixel_group():
    geometry = Geometry("config/geometry_live_assist.json")
    image = cv2.imread("tests/fixtures/v85/assist_6_0s_frame_360.png")
    assert image is not None
    provider = EarlyPixelProvider(geometry, birth_zone_end_y=176.75,
                                 record_conversion_trace=True)
    provider.detect(image)
    holds = [d for d in provider.last_result.components
             if d.role in ("hold_head", "hold_body", "hold_tail")]
    assert {d.role for d in holds} >= {"hold_head", "hold_body", "hold_tail"}
    assert len({d.connection_group_id for d in holds}) == 1
    group_id = holds[0].connection_group_id
    converted = [d for d in provider.detect(image.copy())
                 if d.kind in ("hold_head", "hold_tail")]
    assert {d.kind for d in converted} == {"hold_head", "hold_tail"}
    assert all(d.connection_group_id == group_id for d in converted)


def test_tracker_links_tail_when_exact_current_frame_group_is_unique():
    geometry = Geometry("config/geometry_live_assist.json")
    tracker = Tracker(geometry)
    notes = _feed(tracker, geometry, [(7, 90, 11, 12)])
    holds = [n for n in notes if n.kind == "hold"]
    assert len(holds) == 1 and holds[0].confirmed
    note = holds[0]
    assert note.full_head_observations >= 2
    assert note.tail_uid
    endpoint = tracker.caps[note.tail_uid]
    assert endpoint.detection.kind == "hold_tail"
    assert endpoint.detection.connection_group_id == note.detection.connection_group_id == 7
    assert endpoint.connection_owner_uid == note.uid


def test_tracker_uses_current_head_color_when_birth_color_was_neutral():
    geometry = Geometry("config/geometry_live_assist.json")
    tracker = Tracker(geometry)
    notes = []
    for frame in range(4):
        color = "neutral" if frame < 2 else "green"
        head, tail = _hold_pair(90, 120 + frame * 3, 7, 11, 12, color)
        notes = tracker.update([head, tail], frame * 0.02)
    holds = [n for n in notes if n.kind == "hold" and n.confirmed]
    assert len(holds) == 1
    note = holds[0]
    assert note.color == "neutral" and note.detection.color == "green"
    assert note.tail_uid
    assert tracker.caps[note.tail_uid].connection_owner_uid == note.uid


def test_tracker_keeps_two_unique_connected_hold_groups_separate():
    geometry = Geometry("config/geometry_live_assist.json")
    tracker = Tracker(geometry)
    notes = _feed(tracker, geometry, [(7, 30, 11, 12), (19, 230, 21, 22)])
    holds = [n for n in notes if n.kind == "hold" and n.confirmed]
    assert len(holds) == 2
    owners = {n.detection.connection_group_id: n for n in holds}
    assert set(owners) == {7, 19}
    for group_id, note in owners.items():
        assert note.tail_uid
        assert tracker.caps[note.tail_uid].detection.connection_group_id == group_id
        assert tracker.caps[note.tail_uid].connection_owner_uid == note.uid


def test_tracker_abstains_when_multiple_heads_share_one_connection_group():
    geometry = Geometry("config/geometry_live_assist.json")
    tracker = Tracker(geometry)
    notes = _feed(tracker, geometry, [(7, 30, 11, 12), (7, 230, 21, 22)])
    holds = [n for n in notes if n.kind == "hold" and n.confirmed]
    assert len(holds) == 2
    assert all(not n.tail_uid for n in holds)
