import csv
import json
import threading
import time

import numpy as np
import pytest

from src.capture import CaptureWorker, Region
from src.diagnostics import Diagnostics
from src.scheduler import Action, MockActuator, Scheduler


class FakeCapture:
    name = "fake"
    def __init__(self): self.closed = False; self.n = 0
    def grab(self):
        self.n += 1
        return np.full((3, 4, 3), self.n, np.uint8)
    def close(self): self.closed = True


def test_capture_latest_frame_and_resource_thread_ownership():
    made = []
    def factory():
        cap = FakeCapture(); cap.owner = threading.get_ident(); made.append(cap); return cap
    worker = CaptureWorker(Region(1, 2, 4, 3), fps=500, factory=factory).start()
    time.sleep(.025)
    frame = worker.take(.2)
    worker.close()
    assert frame.sequence > 0
    assert frame.image.shape == (3, 4, 3)
    assert frame.acquired_at >= frame.captured_at
    assert worker.dropped > 0
    assert made[0].closed and made[0].owner != threading.get_ident()
    assert worker.resolved_backend == "fake"
    assert worker.fallback_reason == ""


def test_capture_publishes_auto_fallback_metadata_from_owner_thread():
    class AutoFallback(FakeCapture):
        name = "mss"
        fallback_reason = "dxcam unavailable"
    worker = CaptureWorker(Region(0, 0, 2, 2), factory=AutoFallback).start()
    assert worker.take(.2) is not None
    worker.close()
    assert worker.resolved_backend == "mss"
    assert worker.fallback_reason == "dxcam unavailable"


def test_capture_backend_error_is_reported_without_synthetic_frame():
    worker = CaptureWorker(Region(0, 0, 2, 2), factory=lambda: Broken()).start()
    assert worker.take(.2) is None
    worker.close()
    assert "device unavailable" in str(worker.error)


class Broken:
    def grab(self): raise RuntimeError("device unavailable")
    def close(self): pass


class FakeWriter:
    def __init__(self, path): self.path = path; self.frames = []; self.released = False
    def write(self, image): self.frames.append(image.copy())
    def release(self): self.released = True


def test_diagnostics_ordered_actions_snapshot_and_paired_video(tmp_path):
    made = []
    def writer(path, fps, size):
        assert fps == 60 and size == (720, 404)
        value = FakeWriter(path); made.append(value); return value
    d = Diagnostics(tmp_path, record=True, writer_factory=writer)
    assert d.event({"timestamp": 1, "key": "S", "action": "down"})
    assert d.event({"timestamp": 2, "key": "S", "action": "up"})
    image = np.zeros((404, 720, 3), np.uint8)
    info = {"sequence": 7, "captured_at": 10.0, "acquired_at": 10.01, "status": "ready"}
    notes = [{"bbox": [1, 2, 3, 4], "decision": "track"}]
    d.frame(image, info, notes)
    image[:] = 255; info["sequence"] = 99; notes[0]["decision"] = "mutated"
    summary = d.close()
    assert summary["actions"] == 2 and summary["frames"] == 1
    with (tmp_path / "actions.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [json.loads(r["payload_json"])["action"] for r in rows] == ["down", "up"]
    index = list(csv.DictReader((tmp_path / "live_video_index.csv").open(encoding="utf-8", newline="")))
    assert len(index) == 1 and index[0]["source_frame"] == "7"
    assert index[0]["capture_timestamp"] == "10.0"
    assert len(made) == 2 and all(w.released and len(w.frames) == 1 for w in made)
    assert not np.any(made[0].frames[0])
    assert np.any(made[1].frames[0])
    session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert session["capture_kind"] == "auto_assist"


def test_diagnostics_merges_runtime_metadata_into_session(tmp_path):
    d = Diagnostics(tmp_path)
    d.metadata.update({"game_title": "fixture", "captured_frames": 3,
                       "capture_dropped_frames": 1, "processed_frames": 2})
    d.close()
    session = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert session["capture_kind"] == "auto_assist"
    assert session["game_title"] == "fixture"
    assert session["captured_frames"] == 3 and session["capture_dropped_frames"] == 1


def test_slow_diagnostics_writer_does_not_block_frame_producer(tmp_path):
    entered, release = threading.Event(), threading.Event()
    class Slow(FakeWriter):
        def write(self, image):
            entered.set(); release.wait(1); super().write(image)
    d = Diagnostics(tmp_path, record=True, writer_factory=lambda *args: Slow(args[0]))
    image = np.zeros((404, 720, 3), np.uint8)
    d.frame(image, {"sequence": 0}, [])
    assert entered.wait(.5)
    started = time.perf_counter()
    for i in range(1, 20): d.frame(image, {"sequence": i}, [])
    assert time.perf_counter() - started < .1
    release.set()
    summary = d.close()
    assert summary["frame_overwrites"] > 0


def test_diagnostics_queue_overflow_and_writer_errors_propagate(tmp_path):
    d = Diagnostics(tmp_path)
    d.actions = __import__("queue").Queue(maxsize=1)
    assert d.event({"n": 1})
    assert not d.event({"n": 2})
    with pytest.raises(RuntimeError, match="queue overflow"):
        d.close()


def test_diagnostics_writer_failure_propagates_at_close(tmp_path):
    class Failing(FakeWriter):
        def write(self, image): raise OSError("disk full")
    d = Diagnostics(tmp_path, record=True, writer_factory=lambda path, *args: Failing(path))
    d.frame(np.zeros((404, 720, 3), np.uint8), {"sequence": 0}, [])
    with pytest.raises(RuntimeError, match="disk full"):
        d.close()


def test_scheduler_event_mix_uses_fixed_action_schema(tmp_path):
    class Clock:
        now = 100.0
        def __call__(self): return self.now
    clock = Clock()
    d = Diagnostics(tmp_path)
    scheduler = Scheduler(MockActuator(), clock=clock, on_event=d.event)
    scheduler.update_context(100.0, playing=True, focused=True, roi_valid=True)
    assert scheduler.toggle()
    assert scheduler.offer(Action("note-1", "S", "tap", 100.02, .001))
    clock.now = 100.02
    scheduler.poll()
    clock.now = 100.05
    scheduler.poll()
    scheduler.disarm("fixture_done")
    events = scheduler.drain_events()
    assert {row["event"] for row in events} >= {"armed", "accepted", "pressed", "released", "disarmed"}
    d.close()
    with (tmp_path / "actions.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["event", "at", "uid", "key", "kind", "reason", "generation", "payload_json"]
        rows = list(reader)
    assert [row["event"] for row in rows] == [row["event"] for row in events]
    armed = next(row for row in rows if row["event"] == "armed")
    accepted = next(row for row in rows if row["event"] == "accepted")
    assert armed["generation"] == "1"
    assert accepted["uid"] == "note-1" and accepted["key"] == "S"
    assert rows[-1]["reason"] == "fixture_done"


def test_diagnostics_timeout_is_bounded_and_worker_is_daemon(tmp_path):
    entered, release = threading.Event(), threading.Event()
    class Hung(FakeWriter):
        def write(self, image):
            entered.set(); release.wait(1)
    d = Diagnostics(tmp_path, record=True, writer_factory=lambda path, *args: Hung(path), close_timeout=.02)
    d.frame(np.zeros((404, 720, 3), np.uint8), {"sequence": 0}, [])
    assert entered.wait(.5)
    assert d.thread.daemon
    with pytest.raises(RuntimeError, match="did not flush"):
        d.close()
    release.set()
    d.thread.join(.5)
    assert not d.thread.is_alive()


def test_no_output_diagnostics_has_no_io_or_thread():
    d = Diagnostics(None, record=True)
    assert d.thread is None
    assert not d.event({"x": 1})
    assert not d.frame(np.zeros((1, 1, 3), np.uint8), {}, [])
    assert d.close()["frames"] == 0


def test_overlay_never_draws_old_boxes_as_current_detections(tmp_path):
    made=[]
    def writer(path,*args):
        value=FakeWriter(path);made.append(value);return value
    d=Diagnostics(tmp_path,record=True,writer_factory=writer)
    info=dict(sequence=1,captured_at=10.,acquired_at=10.01)
    notes=[dict(bbox=[100,100,50,10],last_observation=9.8,
                tail_bbox=[500,250,40,10],tail_last_observation=9.8),
           dict(bbox=[200,200,50,10],last_observation=10.,
                tail_bbox=[400,250,40,10],tail_last_observation=10.)]
    d.frame(np.zeros((404,720,3),np.uint8),info,notes);d.close()
    overlay=made[1].frames[0]
    assert not np.any(overlay[100:111,100:151])
    assert np.any(overlay[200:211,200:251])
    assert not np.any(overlay[250:261,500:541])
    assert np.any(overlay[250:261,400:441])

