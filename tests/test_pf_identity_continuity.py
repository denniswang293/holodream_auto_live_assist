"""Deterministic tests for confirmed Tap identity across degraded frames."""

from src.tracker import Tracker


def build_confirmed_tap(make_candidate):
    tracker = Tracker({"max_gap_s": .16, "max_missed_frames": 8, "confirm_observations": 4},
                      352, predictor_mode="particle",
                      particle_cfg={"count": 128, "min_real_observations": 4,
                                    "max_coast_ms": 90, "deterministic_seed": 41})
    for i in range(6):
        tracks = tracker.update([make_candidate(y=150 + i * 4, keys=["F"])], i / 60)
    assert len(tracks) == 1 and tracks[0].confirmed_note_type == "tap"
    return tracker, tracks[0]


def test_confirmed_tap_unknown_then_tap_keeps_identity_and_particle(make_candidate):
    tracker, original = build_confirmed_tap(make_candidate)
    uid, pf, key = original.physical_note_uid, original.particle_filter, original.stable_keys[:]
    t = 6 / 60
    unknown = make_candidate(y=174 + 4, appearance="neutral_candidate", keys=["F"])
    tracks = tracker.update([unknown], t)
    assert len(tracks) == 1
    current = tracks[0]
    assert current.track_id == original.track_id
    assert current.physical_note_uid == uid and current.particle_filter is pf
    assert current.confirmed_note_type == "tap"
    assert current.current_observation_type == "unknown"
    assert current.identity_state == "TAP_DEGRADED_OBSERVATION"
    assert current.stable_keys == key
    assert current.prediction.measurement_status == "DEGRADED_USED"

    tracks = tracker.update([make_candidate(y=182, keys=["F"])], t + 1 / 60)
    assert tracks[0].physical_note_uid == uid
    assert tracks[0].confirmed_note_type == "tap"
    assert tracks[0].current_observation_type == "tap"


def test_unknown_outlier_coasts_without_updating_particle_weights(make_candidate):
    tracker, track = build_confirmed_tap(make_candidate)
    pf = track.particle_filter
    before_weights = pf.weights.copy()
    before_count = pf.observation_count
    tracks = tracker.update([make_candidate(y=290, appearance="neutral_candidate", keys=["F"])], 6 / 60)
    assert tracks[0].identity_state == "TAP_COASTING"
    assert tracks[0].status == "lost"
    assert (pf.weights == before_weights).all()
    assert pf.observation_count == before_count
    assert tracker.last_unknown_association_audit
    assert not tracker.last_unknown_association_audit[0]["association_accepted"]


def test_unknown_with_wrong_key_or_hold_features_is_not_tap_identity(make_candidate):
    tracker, track = build_confirmed_tap(make_candidate)
    # A different lane cannot inherit the frozen F identity.
    tracks = tracker.update([make_candidate(y=178, u=.76, appearance="neutral_candidate", keys=["L"])], 6 / 60)
    assert tracks and track.identity_state == "TAP_COASTING"
    assert track.current_observation_type == "tap"
    assert not any(row["association_accepted"] for row in tracker.last_unknown_association_audit)


def test_short_missing_frame_coasts_and_identity_recovers(make_candidate):
    tracker, track = build_confirmed_tap(make_candidate)
    uid = track.physical_note_uid
    tracker.update([], 6 / 60)
    assert track.identity_state == "TAP_COASTING"
    recovered = tracker.update([make_candidate(y=178, keys=["F"])], 7 / 60)
    assert any(t.physical_note_uid == uid and t.confirmed_note_type == "tap" for t in recovered)


def test_unknown_cannot_extend_identity_past_reliable_observation_limit(make_candidate):
    tracker, track = build_confirmed_tap(make_candidate)
    # The PF has seen a closer Unknown, but the 90ms clock is anchored to the
    # last reliable colored Tap and may not be refreshed by degraded frames.
    t = track.last_reliable_tap_at + .091
    tracker.update([make_candidate(y=192, appearance="neutral_candidate", keys=["F"])], t)
    assert track.identity_state == "TAP_COASTING"
    assert any(row["final_reason"] == "tap_identity_reliable_observation_expired"
               for row in tracker.last_unknown_association_audit)
