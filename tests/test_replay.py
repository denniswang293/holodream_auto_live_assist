from dataclasses import dataclass
import csv
import json

import numpy as np

from src.replay import replay_session
from src.scheduler import Action


@dataclass
class FakeFrame:
    run_id: str
    video_frame: int
    source_video_frame: int
    source_frame: int
    capture_timestamp: float
    acquired_timestamp: float
    image: object
    index_row: dict


class FakeRecording:
    run_id = "fake"

    def __init__(self, times):
        self.frames = [FakeFrame("fake", i, i, i, t, t + .001,
                                 np.full((1, 1, 3), i, np.uint8), {})
                       for i, t in enumerate(times)]

    def iter_frames(self):
        yield from self.frames


class FakeFramesEngine:
    """Observe a frame only when its acquisition time is available."""
    def __init__(self, geometry, scheduler, calibration):
        self.scheduler = scheduler
        self.seen = []
        self.did_schedule = False
        self.tracker = type("T", (), {"notes": {}})()

    def observe(self, frame):
        assert frame.acquired_at <= self.scheduler.clock() + 1e-9
        assert frame.captured_at <= frame.acquired_at
        self.seen.append((frame.sequence, frame.captured_at, self.scheduler.clock()))
        return {"frame": frame, "playing": True, "cpu_ms": 0., "notes": [], "detections": []}

    def decide(self, observation, processed_at=None):
        frame = observation["frame"]
        assert frame.captured_at <= processed_at
        self.scheduler.update_context(frame.captured_at, True, frame.focused, frame.roi_valid)
        if not self.did_schedule and frame.captured_at >= 1.03:
            self.did_schedule = True
            self.scheduler.offer(Action("synthetic-note", "S", "tap", processed_at + .004, .005))
        self.scheduler.poll()
        return ({"sequence": frame.sequence, "captured_at": frame.captured_at,
                 "acquired_at": frame.acquired_at, "processed_at": processed_at,
                 "playing": True, "focused": True, "roi_valid": True,
                 "capture_age_ms": (processed_at-frame.captured_at)*1000,
                 "cpu_ms": 0., "detections": 0, "tracks": 0, "armed": False,
                 "status": "INPUT OFF"}, [])


def run(times, out_dir=None):
    seen = []
    def factory(g, s, c):
        engine = FakeFramesEngine(g, s, c)
        seen.append(engine)
        return engine
    result = replay_session(FakeRecording(times), geometry=object(), calibration_path="missing.json",
                            cpu_ms=18., poll_ms=2., engine_factory=factory, out_dir=out_dir)
    return result, seen[0]


def test_latest_slot_overwrites_frames_while_processing_and_is_causal():
    result, engine = run([10., 10.004, 10.008, 10.030])
    assert [row[0] for row in engine.seen] == [0, 2, 3]
    assert all(start >= captured + .001 for _, captured, start in engine.seen)
    assert result["summary"]["frames_processed"] == 3
    assert result["summary"]["input_calibration_enabled"] is False
    assert "disabled" in result["summary"]["missing_calibration_reason"]


def test_replay_is_repeatable_and_does_not_read_human_key_events():
    first, _ = run([1., 1.05, 1.10, 1.15])
    second, _ = run([1., 1.05, 1.10, 1.15])
    assert first["simulated_actions"] == second["simulated_actions"]
    assert first["frame_summary"] == second["frame_summary"]
    assert first["summary"]["frames_processed"] == 4
    downs = [row for row in first["simulated_actions"] if row["action"] == "key_down"]
    assert downs
    assert all(row["note_uid"] == "synthetic-note" and row["scheduled_hit"] for row in downs)


def test_output_schema_matches_comparator_and_keeps_accuracy_unverified(tmp_path):
    result, _ = run([1., 1.03, 1.06, 1.09], out_dir=tmp_path)
    with (tmp_path / "track_summary.csv").open(encoding="utf-8", newline="") as f:
        tracks = list(csv.DictReader(f))
    with (tmp_path / "simulated_actions.csv").open(encoding="utf-8", newline="") as f:
        actions = list(csv.DictReader(f))
    assert "history" in tracks[0] if tracks else "history" in (tmp_path / "track_summary.csv").read_text()
    downs = [r for r in actions if r["action"] == "key_down"]
    ups = [r for r in actions if r["action"] == "key_up"]
    assert downs and ups
    assert downs[0]["event_id"] == ups[0]["event_id"]
    assert downs[0]["scheduled_hit"]
    summary = json.loads((tmp_path / "replay_summary.json").read_text())
    assert summary["game_accuracy"] == "UNVERIFIED"
    assert summary["dropped_frames"] >= 0
    assert "p99" in summary["cpu_observed_excluding_decode_ms"]
    assert "p10" in summary["observe_wall_ms"] and "p90" in summary["decide_wall_ms"]
    assert summary["cpu_observed_ms"]["count"] == summary["frames_processed"]
    assert summary["actual_actuator_key_downs"] == 1
    assert summary["actual_actuator_key_ups"] == 1


def test_capture_window_keeps_indexed_irregular_timestamps_and_source_ordinals():
    from tools.replay_recordings import WindowRecording
    from pathlib import Path
    recording=FakeRecording([100.,100.031,100.09,100.132,100.20])
    recording.path=Path('not_a_source_directory');recording.session={'start_timestamp':100.}
    window=WindowRecording(recording,100.03,100.14)
    frames=list(window.iter_frames())
    assert [f.source_video_frame for f in frames]==[1,2,3]
    assert [f.capture_timestamp for f in frames]==[100.031,100.09,100.132]
    assert window.session['start_timestamp']==100.03


def test_session_clock_origin_preserves_deterministic_actions():
    origin=FakeRecording([1.,1.05,1.10,1.15]);origin.session={'start_timestamp':1.}
    shifted=replay_session(origin,geometry=object(),calibration_path='missing.json',
        cpu_ms=18.,poll_ms=2.,engine_factory=FakeFramesEngine)
    original,_=run([1.,1.05,1.10,1.15])
    assert shifted['simulated_actions']==original['simulated_actions']
