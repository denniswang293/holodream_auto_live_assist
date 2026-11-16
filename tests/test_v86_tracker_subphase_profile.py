from src.model import Detection, Geometry
from src.tracking import Tracker
from tools.profile_v86_tracker_subphases import _profiled_update_factory


def _tap(x=42, y=60, component=1):
    return Detection((x, y, 40, 14), "cyan", "tap", ("D",), .9,
        component=component, plane_width=360, evidence=("test_real_pixel",),
        semantic_candidate="tap", face_quality=.9, full_face=True, birth_zone=True)


def _snapshot(tracker):
    return (
        [(uid, cap.note_uid, tuple(cap.samples), dict(cap.votes))
         for uid, cap in tracker.caps.items()],
        [(uid, note.kind, note.confirmed, note.last_seen, note.reason,
          note.state, note.tail_uid) for uid, note in tracker.notes.items()],
        dict(tracker.association_profile),
    )


def test_opt_in_subphase_profile_preserves_tracker_output():
    plain = Tracker(Geometry("config/geometry_live_assist.json", plane_width=360))
    profiled = Tracker(Geometry("config/geometry_live_assist.json", plane_width=360))
    rows = []
    instrumented_update = _profiled_update_factory(Tracker.update, rows, detail_assignment=True)
    sequence = ((1.0, _tap(y=60)), (1.03, _tap(y=67)),
                (1.06, _tap(y=74)), (1.09, _tap(y=81)))

    for timestamp, detection in sequence:
        plain_result = plain.update([detection], timestamp)
        profiled_result = instrumented_update(profiled, [detection], timestamp)
        assert [(n.uid, n.kind, n.confirmed, n.last_seen, n.reason, n.state, n.tail_uid)
                for n in plain_result] == [
                    (n.uid, n.kind, n.confirmed, n.last_seen, n.reason, n.state, n.tail_uid)
                    for n in profiled_result]
        assert _snapshot(plain) == _snapshot(profiled)

    assert len(rows) == len(sequence)
    assert all(row["tracker_update_profiled_wall_ms"] >= 0 for row in rows)
    assert all(row["tracker_input_prep_ms"] >= 0 for row in rows)
    assert all(row["tracker_link_tails_ms"] >= 0 for row in rows)
    assert all(row["tracker_detail_sparse_assignment_solve_ms"] >= 0 for row in rows)
