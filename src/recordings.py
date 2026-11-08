"""Readers and normalization helpers for HoloDream manual recordings.

The capture index is authoritative for frame timing. MP4 timestamps and nominal
FPS are deliberately not used as clocks.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2


@dataclass(frozen=True)
class Frame:
    run_id: str
    video_frame: int
    source_video_frame: int
    source_frame: int | None
    capture_timestamp: float
    acquired_timestamp: float
    image: object
    index_row: dict[str, str]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Recording:
    """A recording folder with an indexed, causal frame iterator.

    ``iter_frames()`` yields decoded frames in encoded/index order. Timestamps
    are host performance-counter seconds from ``capture_timestamp`` and
    ``acquired_timestamp``. The MP4 is checked against the complete index before
    each frame is yielded; source frame gaps are retained as provenance and are
    not treated as missing encoded frames.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.run_id = self.path.name
        self.session = json.loads((self.path / "session.json").read_text(encoding="utf-8-sig"))
        self.index = _read_csv(self.path / "live_video_index.csv")

    def iter_frames(self) -> Iterator[Frame]:
        video_path = self.path / "live_source.mp4"
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"cannot open encoded video: {video_path}")
        try:
            previous_capture = previous_acquired = None
            for expected, row in enumerate(self.index):
                encoded_no = int(row["video_frame"])
                if encoded_no != expected:
                    raise ValueError(f"{self.run_id}: index video_frame {encoded_no} at row {expected}")
                ok, image = cap.read()
                if not ok or image is None:
                    raise ValueError(f"{self.run_id}: video ended before indexed frame {expected}")
                # source_frame is the acquisition sequence in the recorder's
                # current schema. It is not an ordinal into the encoded MP4.
                source_video_frame = int(row["source_video_frame"]) if row.get("source_video_frame") else encoded_no
                if source_video_frame != encoded_no:
                    raise ValueError(
                        f"{self.run_id}: source_video_frame {source_video_frame} does not match playable encoded ordinal {encoded_no}"
                    )
                source_frame = int(row["source_frame"]) if row.get("source_frame") else None
                capture_timestamp = float(row["capture_timestamp"])
                acquired_timestamp = float(row["acquired_timestamp"])
                if not math.isfinite(capture_timestamp) or not math.isfinite(acquired_timestamp):
                    raise ValueError(f"{self.run_id}: nonfinite frame timestamp at video_frame {encoded_no}")
                if previous_capture is not None and capture_timestamp <= previous_capture:
                    raise ValueError(f"{self.run_id}: nonmonotone capture_timestamp at video_frame {encoded_no}")
                if previous_acquired is not None and acquired_timestamp < previous_acquired:
                    raise ValueError(f"{self.run_id}: nonmonotone acquired_timestamp at video_frame {encoded_no}")
                if acquired_timestamp < capture_timestamp:
                    raise ValueError(f"{self.run_id}: acquired_timestamp precedes capture at video_frame {encoded_no}")
                previous_capture, previous_acquired = capture_timestamp, acquired_timestamp
                yield Frame(self.run_id, encoded_no, source_video_frame, source_frame,
                            capture_timestamp, acquired_timestamp, image, row)
            ok, _ = cap.read()
            if ok:
                raise ValueError(f"{self.run_id}: video contains frames beyond index length {len(self.index)}")
        finally:
            cap.release()


def normalize_key_actions(run_id: str, events: list[dict[str, str]], session: dict) -> tuple[list[dict], list[str]]:
    """Pair key transitions into stable-ID intervals; preserve partial/error rows."""
    issues: list[str] = []
    rows: list[dict] = []
    active: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for key in session.get("initial_held_keys", []) or []:
        active[str(key)] = {"down": float(session["start_timestamp"]), "initial": True, "repeat": 0,
                            "focused": "", "injected": "", "scan_code": ""}
    ordered = sorted(enumerate(events), key=lambda pair: (float(pair[1]["timestamp"]), pair[0]))
    for _, e in ordered:
        key, action = e["key"], e["action"]
        t = float(e["timestamp"])
        if action == "key_down":
            if key in active:
                active[key]["repeat"] += 1
                issues.append(f"repeat_key_down:{key}@{t:.6f}")
                continue
            active[key] = {"down": t, "initial": False, "repeat": 0,
                           "focused": e.get("focused", ""), "injected": e.get("injected", ""),
                           "scan_code": e.get("scan_code", "")}
        elif action == "key_up":
            if key not in active:
                issues.append(f"unpaired_key_up:{key}@{t:.6f}")
                counts[key] = counts.get(key, 0) + 1
                rows.append(_action_row(run_id, key, counts[key], None, t, e, status="unpaired_up", repeat=0,
                                        start_timestamp=float(session["start_timestamp"])))
                continue
            start = active.pop(key)
            counts[key] = counts.get(key, 0) + 1
            rows.append(_action_row(run_id, key, counts[key], start, t, e, status="initial_held" if start["initial"] else "complete", repeat=start["repeat"],
                                    start_timestamp=float(session["start_timestamp"])))
        else:
            issues.append(f"unknown_action:{action}@{t:.6f}")
    stop = float(session.get("stopped_timestamp", session.get("start_timestamp", 0)))
    for key, start in active.items():
        counts[key] = counts.get(key, 0) + 1
        rows.append(_action_row(run_id, key, counts[key], start, stop, {}, status="initial_held_partial_at_stop" if start["initial"] else "partial_at_stop", repeat=start["repeat"],
                                start_timestamp=float(session["start_timestamp"])))
        issues.append(f"held_at_stop:{key}")
    rows.sort(key=lambda r: (r["down_timestamp"] is None, r["down_timestamp"] if r["down_timestamp"] is not None else r["up_timestamp"], r["key"], r["action_id"]))
    return rows, issues


def _action_row(run_id, key, number, start, end, up_event, status, repeat, start_timestamp):
    down = start["down"] if start else None
    up = end if end is not None else None
    return {"run_id": run_id, "action_id": f"{run_id}:{key}:{number:06d}", "key": key,
            "down_timestamp": down, "up_timestamp": up,
            "duration_s": max(0.0, up - down) if down is not None and up is not None else None,
            "status": status, "initial_held": bool(start and start["initial"]), "repeat_down_count": repeat,
            "down_focused": start.get("focused", "") if start else "",
            "up_focused": up_event.get("focused", ""),
            "down_injected": start.get("injected", "") if start else "",
            "up_injected": up_event.get("injected", ""),
            "scan_code": (start.get("scan_code", "") if start else up_event.get("scan_code", "")),
            "down_elapsed_s": down - start_timestamp if down is not None else None,
            "up_elapsed_s": up - start_timestamp if up is not None else None,
            "source_event_count": (int(bool(start and not start["initial"])) + int(bool(up_event)))}
