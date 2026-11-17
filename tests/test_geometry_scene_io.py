from pathlib import Path

import pytest

from tools.geometry_scene.scene import Keyframe, Point, Scene, SceneNote, Segment
from tools.geometry_scene.scene_io import load_scene, save_scene


def test_scene_json_round_trip_is_renderer_scene_only(tmp_path: Path):
    scene = Scene(
        100, 80,
        tuple(Segment(Point(x, 0), Point(x * 2, 70)) for x in (1, 2, 3, 4, 5, 6, 7)),
        Segment(Point(1, 70), Point(14, 70)),
        (SceneNote("n1", "HOLD", (Keyframe(0.1, 10, 20, 14, 25),), (0.1, 0.1)),),
        "2.0", "run-test",
    )
    path = tmp_path / "scene.json"
    save_scene(scene, path)
    loaded = load_scene(path)
    assert loaded == scene
    assert "source_video" not in path.read_text(encoding="utf-8")


def test_scene_json_rejects_unknown_schema(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema_version":"1.0"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported scene schema"):
        load_scene(path)
