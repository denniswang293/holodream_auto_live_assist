"""Synthetic positives and negatives for offline cross-tracker Tap bridges."""
from __future__ import annotations

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reconstruct_scene import (
    _associate_external_partial_tap_tracks,
    _attach_retrospective_recovery_taps,
)


def _fixture(*, color: str = "cyan", confirmed: bool = True, x_offset: float = 0.0,
             duplicate: bool = False) -> dict:
    def direct(frame: int, x: float, y: float) -> dict:
        return {
            "frame": frame, "candidate_kind": "tap", "candidate_color": "cyan",
            "head_x": x, "head_y": y, "source_bbox": [x - 50, y - 30, 100, 30],
        }

    target = {
        "confirmed_seen": True,
        "points": [direct(10, 350, 230), direct(26, 470, 390)],
    }
    fragments = {}
    for name in (["fragment"] if not duplicate else ["fragment_a", "fragment_b"]):
        points = []
        for frame in range(11, 26):
            t = (frame - 10) / 16
            center_x = 350 + t * 120 + x_offset
            bottom_y = 230 + t * 160
            width = 100 + t * 80
            height = 30
            points.append({
                "frame": frame, "candidate_kind": "plate_fragment",
                "candidate_color": color, "candidate_score_uncalibrated": 0.95,
                "source_bbox": [center_x - width / 2, bottom_y - height, width, 5],
            })
        fragments[name] = {"confirmed_seen": confirmed, "points": points}
    return {"target": target, **fragments}


class PartialBridgeTests(unittest.TestCase):
    def test_unique_aligned_confirmed_track_bridges(self) -> None:
        # The fragment is slightly horizontally clipped but remains within
        # the association gate; rendered center/width must follow this note's
        # bracketed full-head observations, not the fragment bbox.
        bridges = _associate_external_partial_tap_tracks(_fixture(x_offset=18), lane_pixels=100)
        self.assertEqual(len(bridges["target"]), 1)
        self.assertEqual(len(bridges["target"][0]["bridge_points"]), 15)
        first = bridges["target"][0]["bridge_points"][0]
        self.assertAlmostEqual(first["head_x"], 357.5)
        self.assertAlmostEqual(first["source_bbox"][2], 100.0)
        self.assertAlmostEqual(first["source_bbox"][0], 307.5)
        self.assertEqual(first["partial_fragment_bbox"], [323.0, 210.0, 105.0, 5.0])

    def test_rejects_color_mismatch(self) -> None:
        self.assertEqual(_associate_external_partial_tap_tracks(_fixture(color="neutral"), 100), {})

    def test_rejects_unconfirmed_fragment_tracker(self) -> None:
        self.assertEqual(_associate_external_partial_tap_tracks(_fixture(confirmed=False), 100), {})

    def test_rejects_misaligned_fragment_path(self) -> None:
        self.assertEqual(_associate_external_partial_tap_tracks(_fixture(x_offset=100), 100), {})

    def test_rejects_ambiguous_fragment_tracks(self) -> None:
        self.assertEqual(_associate_external_partial_tap_tracks(_fixture(duplicate=True), 100), {})


def _recovery_fixture(*, boxes: list[list[float]]) -> tuple[list[dict], dict]:
    recovery = []
    for offset, bbox in enumerate(boxes):
        recovery.append({
            "frame": 10 + offset,
            "candidate_color": "cyan",
            "candidate_score_uncalibrated": 0.9,
            "detector_rectified_bbox": bbox,
            "rectified_x": bbox[0] + bbox[2] / 2,
            "rectified_y": bbox[1] + bbox[3],
            "head_x": bbox[0] + bbox[2] / 2,
            "head_y": bbox[1] + bbox[3],
        })
    endpoint_bbox = list(boxes[-1])
    history = {
        "tap": {
            "confirmed_seen": True,
            "kind_history": ["tap", "tap"],
            "color_history": ["cyan", "cyan"],
            "points": [{
                "frame": 10 + len(boxes),
                "candidate_kind": "tap",
                "candidate_color": "cyan",
                "detector_rectified_bbox": endpoint_bbox,
            }],
        }
    }
    return recovery, history


class RecoveryAssociationGuardTests(unittest.TestCase):
    def test_rejects_stationary_recovery_boxes_on_judgment_band(self) -> None:
        recovery, history = _recovery_fixture(boxes=[
            [300, 566, 100, 19], [300, 566, 100, 19],
        ])
        links, diagnostics = _attach_retrospective_recovery_taps(
            recovery, history, judgment_line_y=580,
        )
        self.assertEqual(links, [])
        self.assertEqual(diagnostics[0]["reason"], "stationary_recovery_cluster_overlaps_judgment_band")
        self.assertIn("JUDGMENT_BAND_AMBIGUITY", diagnostics[0]["labels"])

    def test_keeps_moving_note_cluster_near_but_not_static_at_line(self) -> None:
        recovery, history = _recovery_fixture(boxes=[
            [300, 560, 100, 19], [302, 564, 100, 19],
        ])
        links, _ = _attach_retrospective_recovery_taps(
            recovery, history, judgment_line_y=580,
        )
        self.assertEqual(len(links), 2)

    def test_keeps_stationary_cluster_away_from_judgment_line(self) -> None:
        recovery, history = _recovery_fixture(boxes=[
            [300, 400, 100, 19], [300, 400, 100, 19],
        ])
        links, _ = _attach_retrospective_recovery_taps(
            recovery, history, judgment_line_y=580,
        )
        self.assertEqual(len(links), 2)


if __name__ == "__main__":
    unittest.main()
