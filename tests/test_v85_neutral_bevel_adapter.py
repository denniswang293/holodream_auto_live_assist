from src.early_perception import EarlyPixelProvider


def test_thin_neutral_fragment_at_complete_tap_bevel_is_suppressed():
    tap = (231, 259, 103, 28)
    fragment = (240, 284, 83, 3)
    assert EarlyPixelProvider._occluded_neutral_fragment(fragment, [tap])


def test_neutral_fragment_remains_when_not_covered_by_tap_face():
    fragment = (240, 284, 83, 3)
    assert not EarlyPixelProvider._occluded_neutral_fragment(fragment, [])
    assert not EarlyPixelProvider._occluded_neutral_fragment(fragment, [(100, 259, 80, 28)])


def test_full_or_tall_neutral_candidate_is_not_suppressed_by_bevel_rule():
    tap = (231, 259, 103, 28)
    assert not EarlyPixelProvider._occluded_neutral_fragment((240, 284, 83, 5), [tap])
    assert not EarlyPixelProvider._occluded_neutral_fragment((240, 270, 83, 3), [tap])
