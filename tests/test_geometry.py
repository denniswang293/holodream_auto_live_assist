from src.geometry import Playfield


def field():
    return Playfield(28, 346, 374, 352, 36, 684)


def test_bounds_interpolate_between_top_and_bottom():
    g = field()
    assert g.bounds(28) == (346, 374)
    assert g.bounds(352) == (36, 684)


def test_lane_mapping_clamps_and_maps_six_lane_centers():
    g = field()
    left, right = g.bounds(352)
    centers = [left + (i + 0.5) * (right-left) / 6 for i in range(6)]
    assert [g.lane(x, 352) for x in centers] == list(range(6))
    assert g.lane(-1000, 352) == 0
    assert g.lane(1000, 352) == 5


def test_wide_note_returns_all_overlapped_lanes():
    g = field()
    left, right = g.bounds(352)
    assert g.candidate_lanes(left + 0.9*(right-left)/6,
                             left + 2.1*(right-left)/6, 352) == [0, 1, 2]


def test_tiny_lane_overlap_does_not_add_neighbor_key():
    g = field()
    left,right = g.bounds(352)
    width = (right-left)/6
    assert g.candidate_lanes(left+1.01*width,left+2.01*width,352,6,0.15) == [1]
