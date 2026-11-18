import unittest

from scene_refinement import refine_scene_track_discontinuities


GEOMETRY = {
    "rail_boundaries": [
        {"top_intercept_x": lane * 100.0, "slope_dx_per_dy": 0.0}
        for lane in range(7)
    ]
}


def scene_for(kind="Tap", frames=None):
    if frames is None:
        frames = [(0, 250, 100), (1, 251, 110), (2, 252, 120),
                  (3, 400, 114), (4, 401, 124), (5, 402, 134)]
    keyframes = [{
        "frame": frame,
        "capture_timestamp": frame / 60,
        "head_x": x,
        "head_y": y,
        "source_bbox": [x - 10, y - 4, 20, 4],
        "candidate_color_observed": "cyan",
        "source_observation_kind": "tap" if kind == "Tap" else "hold_head",
    } for frame, x, y in frames]
    return {
        "frame_count": 100,
        "notes": [{
            "id": "note:1", "type": kind, "lane": 2, "confidence": 0.9,
            "confidence_status": "AUTO_HEURISTIC / PROVISIONAL",
            "color": "#35D5FF", "association_status": "AUTO_VISUAL_REVIEWED / PROVISIONAL",
            "intervals": [{"state": "visible", "start_frame": keyframes[0]["frame"],
                           "end_frame": keyframes[-1]["frame"] + 1}],
            "unobserved_intervals": [], "keyframes": keyframes,
            "head_body_tail_evidence": {"tap_face_observations": len(keyframes)},
        }],
    }


class TrackDiscontinuityTests(unittest.TestCase):
    def test_splits_one_frame_sideways_jump_with_upward_reversal(self):
        scene, audit = refine_scene_track_discontinuities(scene_for(), GEOMETRY)
        self.assertEqual(len(scene["notes"]), 2)
        left, right = scene["notes"]
        self.assertEqual([k["frame"] for k in left["keyframes"]], [0, 1, 2])
        self.assertEqual([k["frame"] for k in right["keyframes"]], [3, 4, 5])
        self.assertEqual([left["lane"], right["lane"]], [2, 4])
        self.assertIn("NOT_GROUND_TRUTH", right["association_split"]["labels"])
        self.assertEqual(audit["split_track_count"], 1)

    def test_does_not_split_downward_moving_candidate(self):
        frames = [(0, 250, 100), (1, 251, 110), (2, 252, 120),
                  (3, 400, 130), (4, 401, 140), (5, 402, 150)]
        scene, audit = refine_scene_track_discontinuities(scene_for(frames=frames), GEOMETRY)
        self.assertEqual(len(scene["notes"]), 1)
        self.assertEqual(audit["split_track_count"], 0)

    def test_does_not_split_hold(self):
        scene, audit = refine_scene_track_discontinuities(scene_for("Hold"), GEOMETRY)
        self.assertEqual(len(scene["notes"]), 1)
        self.assertEqual(audit["split_track_count"], 0)

    def test_does_not_split_nonconsecutive_observations(self):
        frames = [(0, 250, 100), (1, 251, 110), (2, 252, 120),
                  (4, 400, 114), (5, 401, 124), (6, 402, 134)]
        scene, audit = refine_scene_track_discontinuities(scene_for(frames=frames), GEOMETRY)
        self.assertEqual(len(scene["notes"]), 1)
        self.assertEqual(audit["split_track_count"], 0)

    def test_does_not_split_if_one_side_has_too_few_anchors(self):
        frames = [(0, 250, 100), (1, 251, 110), (2, 252, 120), (3, 400, 114)]
        scene, audit = refine_scene_track_discontinuities(scene_for(frames=frames), GEOMETRY)
        self.assertEqual(len(scene["notes"]), 1)
        self.assertEqual(audit["split_track_count"], 0)


if __name__ == "__main__":
    unittest.main()
