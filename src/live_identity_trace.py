"""Bounded, asynchronous live identity telemetry.

The writer is deliberately diagnostic-only.  It never participates in a
decision, scheduler call, or input path.  When the bounded queue is full, a
diagnostic row is dropped and the health file records the loss.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
import queue
import threading
import time


CANDIDATE_FIELDS = [
    "run_id", "capture_sequence", "source_frame", "source_video_frame",
    "capture_timestamp", "processing_timestamp", "frame_uid", "stage",
    "candidate_id", "parent_proposal_id", "raw_bbox", "core_bbox", "x",
    "y", "w", "h", "u_min", "u_max", "u_center", "appearance",
    "note_type", "candidate_keys", "score", "passed", "reject_reason",
    "lane_span", "trace_status",
]

ASSOCIATION_FIELDS = [
    "run_id", "capture_sequence", "source_frame", "source_video_frame",
    "capture_timestamp", "processing_timestamp", "frame_uid", "row_type",
    "track_id", "track_uid", "candidate_id", "track_status_before",
    "matched_this_frame", "assigned", "track_last_time",
    "last_real_observation_ts", "observation_age_ms", "delta_t_ms",
    "predicted_y", "predicted_u", "observed_y", "observed_u", "dy_px",
    "du", "motion_continuity", "reject_reason", "total_cost",
    "residual_px", "tolerance_px", "competition_track_ids", "skip_reason",
    "dropped_rows", "trace_status",
]

TRACK_FIELDS = [
    "run_id", "capture_sequence", "source_frame", "source_video_frame",
    "capture_timestamp", "processing_timestamp", "frame_uid", "track_id",
    "track_uid", "note_uid", "candidate_id", "matched_this_frame",
    "real_observation_this_frame", "coasting_this_frame",
    "last_real_observation_timestamp", "observation_age_ms", "missed_frames",
    "track_status", "confirmed_note_type", "appearance", "bbox",
    "stable_keys", "prediction_reason", "termination_reason",
    "state_transition", "intent_state", "intent_key", "trace_status",
]


class LiveIdentityTraceWriter:
    """Write bounded telemetry rows without blocking the capture loop."""

    def __init__(self, directory: Path, run_id: str, config: dict | None = None):
        self.directory = Path(directory)
        self.run_id = str(run_id)
        self.config = dict(config or {})
        self.capacity = max(64, int(self.config.get("max_queue_rows", 4096)))
        self.queue: queue.Queue[tuple[str, dict] | None] = queue.Queue(maxsize=self.capacity)
        self.enabled = bool(self.config.get("enabled", False))
        self._closed = False
        self._lock = threading.Lock()
        self.submitted_rows = 0
        self.written_rows = 0
        self.dropped_diagnostic_rows = 0
        self.covered_frames: set[int] = set()
        self._files: dict[str, object] = {}
        self._writers: dict[str, csv.DictWriter] = {}
        if self.enabled:
            self.directory.mkdir(parents=True, exist_ok=True)
            for name, fields in (
                    ("live_candidate_trace.csv", CANDIDATE_FIELDS),
                    ("live_association_attempts.csv", ASSOCIATION_FIELDS),
                    ("live_track_identity.csv", TRACK_FIELDS)):
                fh = (self.directory / name).open("w", newline="", encoding="utf-8-sig")
                self._files[name] = fh
                self._writers[name] = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
                self._writers[name].writeheader()
        self._thread = threading.Thread(target=self._run, name="holodream-identity-trace", daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            item = self.queue.get()
            if item is None:
                self.queue.task_done()
                break
            name, row = item
            try:
                writer = self._writers.get(name)
                if writer is not None:
                    writer.writerow(row)
                    self._files[name].flush()
                    with self._lock:
                        self.written_rows += 1
            finally:
                self.queue.task_done()

    @staticmethod
    def _text(value):
        if value is None:
            return ""
        if isinstance(value, (tuple, list, dict)):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return value

    def _metadata(self, frame, processing_timestamp):
        sequence = int(frame.sequence)
        return {
            "run_id": self.run_id,
            "capture_sequence": sequence,
            "source_frame": sequence,
            # Recorder/video index is asynchronous; join this field later by
            # source_frame + capture_timestamp when an index is available.
            "source_video_frame": "",
            "capture_timestamp": frame.captured_at,
            "processing_timestamp": processing_timestamp,
            "frame_uid": f"{self.run_id}:{sequence}",
        }

    def _submit(self, name: str, row: dict, frame):
        if not self.enabled or self._closed:
            return False
        try:
            self.queue.put_nowait((name, row))
        except queue.Full:
            with self._lock:
                self.dropped_diagnostic_rows += 1
            return False
        with self._lock:
            self.submitted_rows += 1
            self.covered_frames.add(int(frame.sequence))
        return True

    def submit_frame(self, frame, processing_timestamp, detector_rows,
                     pair_rows, attempt_rows, assignment_rows, track_rows,
                     state: str):
        if not self.enabled or self._closed:
            return
        meta = self._metadata(frame, processing_timestamp)
        for source in detector_rows:
            row = {**meta, **{k: self._text(v) for k, v in source.items()}}
            bbox = source.get("core_bbox") or source.get("raw_bbox")
            if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                row.setdefault("x", bbox[0]); row.setdefault("y", bbox[1])
                row.setdefault("w", bbox[2]); row.setdefault("h", bbox[3])
            if row.get("u_min") not in (None, "") and row.get("u_max") not in (None, ""):
                try:
                    row["u_center"] = (float(row["u_min"]) + float(row["u_max"])) / 2
                    row["lane_span"] = f"{float(row['u_min']):.6f}:{float(row['u_max']):.6f}"
                except (TypeError, ValueError):
                    pass
            row["trace_status"] = "candidate_trace"
            self._submit("live_candidate_trace.csv", row, frame)
        for row_type, rows in (("pair", pair_rows), ("attempt", attempt_rows), ("assignment", assignment_rows)):
            for source in rows:
                row = {**meta, "row_type": row_type,
                       **{k: self._text(v) for k, v in source.items()}}
                row["track_uid"] = row.get("track_uid") or (
                    f"simple:{row['track_id']}" if row.get("track_id") not in (None, "") else "")
                row["skip_reason"] = row.get("skip_reason", "")
                row["trace_status"] = f"{row_type}_trace"
                self._submit("live_association_attempts.csv", row, frame)
        for source in track_rows:
            row = {**meta, **{k: self._text(v) for k, v in source.items()}}
            track_id = row.get("track_id", "")
            row["track_uid"] = row.get("track_uid") or (f"simple:{track_id}" if track_id != "" else "")
            row["note_uid"] = row.get("note_uid") or f"{self.run_id}:simple:{track_id}" if track_id != "" else ""
            row["trace_status"] = f"track_trace:{state}"
            self._submit("live_track_identity.csv", row, frame)

    def health_snapshot(self) -> dict:
        with self._lock:
            return {
                "enabled": self.enabled,
                "run_id": self.run_id,
                "queue_capacity": self.capacity,
                "queue_size": self.queue.qsize(),
                "submitted_rows": self.submitted_rows,
                "written_rows": self.written_rows,
                "dropped_diagnostic_rows": self.dropped_diagnostic_rows,
                "trace_coverage_frames": len(self.covered_frames),
                "trace_coverage_min_frame": min(self.covered_frames) if self.covered_frames else None,
                "trace_coverage_max_frame": max(self.covered_frames) if self.covered_frames else None,
                "closed": self._closed,
            }

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self.enabled:
            self.queue.join()
        self.queue.put(None)
        self._thread.join(timeout=10)
        for fh in self._files.values():
            fh.close()
        if self.enabled:
            health = self.health_snapshot()
            health["closed"] = True
            (self.directory / "live_identity_trace_health.json").write_text(
                json.dumps(health, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

