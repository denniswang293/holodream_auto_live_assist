from src.detector import Candidate
from src.simple_tracker import SimpleTracker
from src.pf_reassociation import PFAssistedReassociation


def candidate(y, *, u=.40, keys=("F",), appearance="cyan_bar"):
    return Candidate((250, round(y - 3), 60, 6), appearance, .9,
                     u - .06, u + .06, list(keys), "tap",
                     body_bbox=(250, round(y - 3), 60, 6))


def particle_cfg():
    return {"count": 64, "min_observations": 3, "min_duration_s": .02,
            "min_velocity": 20, "min_displacement_px": 1,
            "max_posterior_width_ms": 100}


def test_pf_shadow_proposal_never_mutates_observation_or_sends_input():
    tracker = SimpleTracker({"confirm_observations": 3,
                              "pf_assisted_reassociation": {"enabled": True, "mode": "shadow"}},
                            particle_cfg(), hit_y=310.5)
    for n in range(6):
        tracks = tracker.update([candidate(150 + n * 6)], 1.0 + n * .016)
    track = tracks[0]
    before = (track.observations, len(track.history), track.physical_note_uid)
    rows = tracker.pf_reassociation.propose(
        [track], [candidate(186)], track.last_time + .016)
    assert rows
    assert all(row.get("input_sent") is False for row in rows)
    assert (track.observations, len(track.history), track.physical_note_uid) == before


def test_pf_shadow_requires_real_candidate_and_rejects_missing_state():
    disabled = PFAssistedReassociation({"enabled": False})
    assert disabled.propose([], [], 1.0) == []
    tracker = SimpleTracker({"confirm_observations": 3,
                              "pf_assisted_reassociation": {"enabled": True}},
                            particle_cfg(), hit_y=310.5)
    tracks = tracker.update([candidate(150)], 1.0)
    rows = tracker.pf_reassociation.propose(tracks, [], 1.016)
    assert rows[0]["decision"] == "NO_REAL_CANDIDATE"
