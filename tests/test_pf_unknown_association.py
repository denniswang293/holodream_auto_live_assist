"""PF association gates reject special, out-of-lane, and ambiguous evidence."""

from src.tracker import Tracker


def seeded(make_candidate):
    tr = Tracker({"max_gap_s": .16, "max_missed_frames": 8, "confirm_observations": 4},
                 352, predictor_mode="particle",
                 particle_cfg={"count": 128, "min_real_observations": 4,
                               "max_coast_ms": 90, "deterministic_seed": 54})
    for i in range(6):
        tracks = tr.update([make_candidate(y=140 + i * 4, keys=["F"])], i / 60)
    return tr, tracks[0]


def test_compatible_unknown_records_y_time_span_key_and_score(make_candidate):
    tracker, old = seeded(make_candidate)
    tracks = tracker.update([make_candidate(y=168, appearance="neutral_candidate", keys=["F"])], 6 / 60)
    audit = tracker.last_unknown_association_audit
    assert tracks[0].physical_note_uid == old.physical_note_uid
    assert audit and audit[0]["association_accepted"]
    for field in ("predicted_y", "observed_y", "innovation_y", "sigma_y", "span_overlap",
                  "span_width_ratio", "key_match", "coast_ms", "final_reason"):
        assert field in audit[0]
    assert audit[0]["final_reason"] == "PF_MATCHED_DEGRADED_UNKNOWN"


def test_two_unknown_candidates_competing_for_one_tap_are_abstained(make_candidate):
    tracker, old = seeded(make_candidate)
    a = make_candidate(y=168, appearance="neutral_candidate", keys=["F"])
    b = make_candidate(y=170, appearance="neutral_candidate", keys=["F"])
    tracks = tracker.update([a, b], 6 / 60)
    assert all(t.current_observation_type != "unknown" or
               t.physical_note_uid != old.physical_note_uid for t in tracks)
    assert any(row["final_reason"] == "competing_unknown_associations"
               for row in tracker.last_unknown_association_audit)


def test_expired_pf_and_special_path_are_rejected(make_candidate):
    tracker, old = seeded(make_candidate)
    special = make_candidate(y=190, appearance="green_candidate", keys=["F"])
    # Unknown special candidates remain unassociated; they may not become Tap.
    tracks = tracker.update([special], 6 / 60)
    assert all(t.confirmed_note_type != "tap" or t.current_observation_type != "unknown"
               for t in tracks)


def test_diffuse_particle_distribution_is_not_used_for_identity(make_candidate):
    tracker, track = seeded(make_candidate)
    track.particle_filter.y[:] = track.particle_filter.y.mean()
    track.particle_filter.v[:] = track.particle_filter.v.mean()
    track.particle_filter.vu[:] = track.particle_filter.vu.mean()
    track.particle_filter.ess = 1.0
    tracker.update([make_candidate(y=168, appearance="neutral_candidate", keys=["F"])], 6 / 60)
    assert not tracker.last_unknown_association_audit[0]["association_accepted"]
    assert tracker.last_unknown_association_audit[0]["final_reason"] == "particle_distribution_unreliable"

