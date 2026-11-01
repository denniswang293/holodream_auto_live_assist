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


def _confirmed_tracker():
    tracker = SimpleTracker({"confirm_observations": 3,
                             "pf_assisted_reassociation": {"enabled": True, "mode": "shadow"}},
                            particle_cfg(), hit_y=310.5)
    for n in range(8):
        tracks = tracker.update([candidate(120 + n * 8)], 1.0 + n * .016)
    track = tracks[0]
    assert track.was_confirmed and track.particle_filter.initialized
    return tracker, track


def test_targeted_rescue_uses_only_unmatched_real_candidate_and_does_not_mutate():
    tracker, track = _confirmed_tracker()
    before = (list(track.history), track.physical_note_uid, track.particle_filter.last_time)
    rescue = candidate(184, u=.40)
    rescue.diagnostic_id = "real-unmatched"
    rows = tracker.pf_reassociation.propose_targeted([track], [rescue], track.last_time + .016)
    assert rows
    assert all(row["input_sent"] is False for row in rows)
    assert all(row.get("legacy_unmatched") is True for row in rows if row.get("candidate_id"))
    assert (list(track.history), track.physical_note_uid, track.particle_filter.last_time) == before


def test_targeted_rescue_never_takes_legacy_assigned_candidate():
    tracker, track = _confirmed_tracker()
    assigned = candidate(184, u=.40)
    assigned.diagnostic_id = "legacy-used"
    rows = tracker.pf_reassociation.propose_targeted(
        [track], [assigned], track.last_time + .016,
        assigned_candidate_ids={"legacy-used"})
    assert any(row["decision"] == "BASELINE_ALREADY_MATCHED" for row in rows)
    assert not any(row["decision"] == "INCREMENTAL_SHADOW_REACQUIRE_PROPOSAL" for row in rows)


def test_targeted_rescue_rejects_competing_track_deterministically():
    tracker, first = _confirmed_tracker()
    second = tracker._new_track(candidate(120, u=.40), first.last_time)
    for n in range(1, 8):
        tracker._observe(second, candidate(120 + n * 8, u=.40), first.last_time + n * .016)
    second.status = "lost"
    second.confirmed_note_type = "tap"
    # Align the two historical PF clocks to model a genuine same-frame
    # competition rather than making the second state stale by construction.
    second.particle_filter.last_time = first.particle_filter.last_time
    rescue = candidate(184, u=.40)
    rescue.diagnostic_id = "shared"
    rows = tracker.pf_reassociation.propose_targeted(
        [first, second], [rescue], first.last_time + .016)
    assert sum(row["decision"] == "INCREMENTAL_SHADOW_REACQUIRE_PROPOSAL" for row in rows) <= 1
    assert any(row["decision"] in {"REJECTED_AMBIGUOUS", "REJECTED_COMPETITION"} for row in rows)


def test_shadow_replay_reuses_original_track_without_creating_duplicate_uid():
    tracker, track = _confirmed_tracker()
    rescue = candidate(184, u=.40, keys=("Z",))
    rescue.diagnostic_id = "replay-candidate"
    original_id = track.track_id

    def proposal(_tracks, _candidates, timestamp, **_kwargs):
        return [{"track_id": original_id, "old_uid": track.physical_note_uid,
                 "candidate_id": "replay-candidate", "decision": "INCREMENTAL_SHADOW_REACQUIRE_PROPOSAL",
                 "reason": "pf_real_candidate_match", "input_sent": False,
                 "real_candidate": True, "legacy_unmatched": True}]

    tracker.pf_reassociation.propose_targeted = proposal
    trace = {"max_rows": 10000}
    tracks = tracker.update([rescue], track.last_time + .016, trace=trace,
                            frame_index=100, shadow_replay=True)
    assert [item.track_id for item in tracks] == [original_id]
    assert trace["shadow_replay_rows"][0]["decision"] == "SHADOW_STATE_REACQUIRED"
    assert all(item.get("input_sent") is False for item in trace["shadow_replay_rows"])
