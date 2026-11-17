import numpy as np

from tools.geometry_scene.association import AssociationConfig, TimedFrame, associate_frames
from tools.geometry_scene.segmentation import FrameObservations, PixelCandidate


def _candidate(x, y, *, status="OBSERVED", provenance=("OBSERVED_COLOR_COMPONENT",), color="cyan", solidity=0.95):
    mask = np.zeros((180, 240), dtype=np.uint8)
    return PixelCandidate((x, y, 30, 10), "UNKNOWN", status, (color,), provenance,
                          False, solidity, 300, mask)


def _frame(number, candidates):
    return TimedFrame(number, number / 30, FrameObservations(240, 180, tuple(candidates), np.zeros((180, 240), np.uint8)))


def test_downward_trajectory_keeps_one_persistent_identity():
    tracks = associate_frames([_frame(i, [_candidate(70, 20 + i * 8)]) for i in range(5)])
    assert len(tracks) == 1
    assert [o.bbox[1] for o in tracks[0].observations] == [20, 28, 36, 44, 52]
    assert all(o.status == "OBSERVED" for o in tracks[0].observations)


def test_adjacent_same_height_objects_remain_distinct():
    tracks = associate_frames([_frame(i, [_candidate(30, 60 + i * 5), _candidate(78, 60 + i * 5)]) for i in range(4)])
    assert len(tracks) == 2
    assert [len(t.observations) for t in tracks] == [4, 4]
    assert {t.observations[0].bbox[0] for t in tracks} == {30, 78}


def test_short_occlusion_is_bridged_only_with_unique_support_on_both_sides():
    frames = [_frame(0, [_candidate(50, 20)]), _frame(1, []), _frame(2, [_candidate(50, 32)])]
    tracks = associate_frames(frames, AssociationConfig(max_gap_ms=100))
    assert len(tracks) == 1
    assert len(tracks[0].observations) == 2
    assert len(tracks[0].intervals) == 1
    assert tracks[0].intervals[0].status == "INFERRED_OCCLUSION"

    too_long = associate_frames(frames, AssociationConfig(max_gap_ms=50))
    assert len(too_long) == 2
    assert not any(t.intervals for t in too_long)


def test_merged_candidate_is_not_silently_attached_to_either_track():
    frames = [
        _frame(0, [_candidate(30, 40), _candidate(80, 40)]),
        _frame(1, [_candidate(30, 45), _candidate(30, 45, status="AMBIGUOUS",
                                                  provenance=("MERGED_OR_OCCLUDED_REGION", "OWNERSHIP_UNRESOLVED"))]),
        _frame(2, [_candidate(30, 50), _candidate(80, 50)]),
    ]
    tracks = associate_frames(frames)
    # The merged candidate remains in frame observations for audit, but is not
    # promoted into a persistent identity or attached to either physical track.
    assert len(tracks) == 2
    assert sorted([o.frame for o in t.observations] for t in tracks) == [[0, 1, 2], [0, 2]]


def test_repeated_same_y_objects_stay_separate():
    tracks = associate_frames([_frame(0, [_candidate(25, 72), _candidate(150, 72)]),
                               _frame(1, [_candidate(25, 72), _candidate(150, 72)])])
    assert len(tracks) == 2
    assert all(len(t.observations) == 2 for t in tracks)
    assert {t.observations[0].bbox[0] for t in tracks} == {25, 150}


def test_unknown_candidates_form_unknown_evidence_paths_without_inferred_gaps():
    frames = [_frame(0, [_candidate(70, 20, status="UNKNOWN", solidity=0.89)]),
              _frame(1, [_candidate(70, 28, status="UNKNOWN", solidity=0.89)]),
              _frame(3, [_candidate(70, 44, status="UNKNOWN", solidity=0.89)])]
    tracks = associate_frames(frames, AssociationConfig(max_gap_ms=120))
    assert len(tracks) == 1
    assert [o.frame for o in tracks[0].observations] == [0, 1, 3]
    assert [o.status for o in tracks[0].observations] == ["UNKNOWN"] * 3
    assert tracks[0].intervals[0].status == "UNKNOWN"


def test_unknown_candidates_do_not_merge_into_typed_capable_evidence_tracks():
    frames = [_frame(0, [_candidate(70, 20, status="UNKNOWN", solidity=0.89)]),
              _frame(1, [_candidate(70, 28, status="AMBIGUOUS")]),
              _frame(2, [_candidate(70, 36, status="UNKNOWN", solidity=0.89)])]
    tracks = associate_frames(frames)
    assert len(tracks) == 2
    assert sorted([o.frame for o in track.observations] for track in tracks) == [[0, 2], [1]]
    unknown_track = next(t for t in tracks if t.observations[0].status == "UNKNOWN")
    assert all(o.status == "UNKNOWN" for o in unknown_track.observations)
