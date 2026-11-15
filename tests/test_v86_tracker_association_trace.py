from src.model import Detection, Geometry
from src.tracking import Tracker


def _tap(x=42, y=60, component=1):
    return Detection((x, y, 40, 14), "cyan", "tap", ("D",), .9,
        component=component, plane_width=360, evidence=("test_real_pixel",),
        semantic_candidate="tap", face_quality=.9, full_face=True, birth_zone=True)


def _state(tracker):
    return ([(uid, cap.note_uid, tuple(cap.samples)) for uid, cap in tracker.caps.items()],
            [(uid, note.kind, note.confirmed, note.last_seen, note.reason) for uid, note in tracker.notes.items()])


def test_association_trace_is_opt_in_and_does_not_change_tracker_state():
    plain=Tracker(Geometry("config/geometry_live_assist.json",plane_width=360))
    traced=Tracker(Geometry("config/geometry_live_assist.json",plane_width=360))
    for frame,(timestamp,detection) in enumerate(((1.0,_tap(y=60)),(1.03,_tap(y=67)),(1.06,_tap(y=74))),1):
        plain.update([detection],timestamp)
        traced.update([detection],timestamp)
        assert _state(plain)==_state(traced)
        assert plain.association_trace==[]
    traced.trace_associations=True
    plain.update([_tap(y=81)],1.09)
    traced.update([_tap(y=81)],1.09)
    assert _state(plain)==_state(traced)
    assert any(row.get("assignment_status")=="selected" for row in traced.association_trace)
    assert any(row.get("outcome")=="matched_existing_cap" for row in traced.association_trace)
    assert plain.association_trace==[]


def test_trace_records_gate_rejection_and_new_cap_birth_without_relabeling_it():
    tracker=Tracker(Geometry("config/geometry_live_assist.json",plane_width=360))
    tracker.trace_associations=True
    tracker.update([_tap(x=42,y=60)],2.0)
    tracker.update([_tap(x=260,y=67,component=2)],2.03)
    reasons={row["edge_reason"] for row in tracker.association_trace if row.get("trace_type")=="association_edge"}
    outcomes={row["outcome"] for row in tracker.association_trace if row.get("trace_type")=="detection_outcome"}
    assert any("lane_center_gate" in reason for reason in reasons)
    assert "born_new_cap" in outcomes

