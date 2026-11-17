from __future__ import annotations

import cv2
import numpy as np

from tools.geometry_scene.scene import Keyframe, Point, Scene, SceneNote, Segment
from tools.geometry_scene.renderer import render_scene_frame


def base(notes=()):
    rails = tuple(Segment(Point(x, 2), Point(x, 62)) for x in (4, 16, 28, 40, 52, 64, 76))
    return Scene(80, 64, rails, Segment(Point(4, 55), Point(76, 55)), tuple(notes))


def note(i, kind="TAP", x=10, y=20, color=(20, 100, 240), interval=(0, 2), status="OBSERVED"):
    return SceneNote(i, kind, (Keyframe(0, x, y, 12, 8, status), Keyframe(2, x, y, 12, 8, status)), interval, color)


def test_blank_scene_has_only_static_geometry_and_fresh_dark_canvas():
    s = base()
    a = render_scene_frame(s, 0); b = render_scene_frame(s, 1)
    assert a.shape == (64, 80, 3) and a.dtype == np.uint8
    assert np.array_equal(a, b) and np.any(a != np.array(s.background, dtype=np.uint8))


def test_same_height_taps_remain_two_instances():
    image = render_scene_frame(base((note("a", x=10), note("b", x=50))), 1)
    assert np.count_nonzero(np.all(image == (20, 100, 240), axis=2)) == 2 * 13 * 9


def test_two_concurrent_holds_remain_distinct():
    image = render_scene_frame(base((note("h1", "HOLD", x=8), note("h2", "HOLD", x=54, color=(0, 200, 0)))), 1)
    assert np.any(np.all(image == (20, 100, 240), axis=2))
    assert np.any(np.all(image == (0, 200, 0), axis=2))


def test_tap_and_hold_overlap_are_both_drawn():
    image = render_scene_frame(base((note("t", x=30), note("h", "HOLD", x=38, color=(0, 200, 0)))), 1)
    assert np.any(np.all(image == (20, 100, 240), axis=2))
    assert np.any(np.all(image == (0, 200, 0), axis=2))


def test_hold_parts_are_one_connected_geometry():
    image = render_scene_frame(base((note("h", "HOLD"),)), 1)
    mask = (image == (20, 100, 240)).all(axis=2).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    assert count == 2  # background plus one hold component
    assert stats[1, cv2.CC_STAT_WIDTH] == 13 and stats[1, cv2.CC_STAT_HEIGHT] == 9


def test_interpolation_is_bounded_by_keyframes_and_note_interval():
    moving = SceneNote("m", "TAP", (Keyframe(1, 10, 10, 8, 6), Keyframe(3, 30, 10, 8, 6)), (1, 3))
    s = base((moving,))
    mid = render_scene_frame(s, 2)
    assert np.all(mid[10:16, 20:28] == moving.color)
    assert not np.any(np.all(render_scene_frame(s, 0.9) == moving.color, axis=2))
    assert not np.any(np.all(render_scene_frame(s, 3.1) == moving.color, axis=2))


def test_unknown_keyframe_does_not_bridge_or_render_as_confirmed():
    n = SceneNote("u", "TAP", (Keyframe(0, 10, 10, 8, 6), Keyframe(1, 18, 10, 8, 6, "UNKNOWN"), Keyframe(2, 26, 10, 8, 6)), (0, 2))
    image = render_scene_frame(base((n,)), 0.5)
    assert not np.any(np.all(image == n.color, axis=2))


def test_source_pixels_are_never_an_input_or_canvas():
    source = np.full((64, 80, 3), (255, 0, 255), dtype=np.uint8)
    rendered = render_scene_frame(base((note("t"),)), 1)
    assert not np.any(np.all(rendered == (255, 0, 255), axis=2))
    assert np.array_equal(source, np.full_like(source, (255, 0, 255)))


def test_observed_outline_is_rendered_as_fresh_scene_geometry():
    outline = tuple(Point(x, y) for x, y in ((20, 20), (36, 20), (42, 48), (14, 48)))
    n = SceneNote("poly", "HOLD", (Keyframe(1, 14, 20, 28, 28, outline=outline),), (1, 1))
    image = render_scene_frame(base((n,)), 1)
    assert np.all(image[30, 28] == n.color)
    assert np.all(image[45, 15] == n.color)
    assert np.all(image[45, 12] != n.color)


def test_interpolation_resamples_contours_with_different_vertex_counts():
    square = tuple(Point(x, y) for x, y in ((10, 10), (30, 10), (30, 30), (10, 30)))
    triangle = tuple(Point(x, y) for x, y in ((12, 12), (28, 12), (20, 28)))
    n = SceneNote("changing-contour", "HOLD",
                  (Keyframe(0, 10, 10, 20, 20, outline=square),
                   Keyframe(2, 12, 12, 16, 16, outline=triangle)), (0, 2))
    image = render_scene_frame(base((n,)), 1)
    assert np.all(image[19, 20] == n.color)
    # A bbox fallback paints this lower corner; interpolated source contours do not.
    assert np.all(image[29, 12] != n.color)
