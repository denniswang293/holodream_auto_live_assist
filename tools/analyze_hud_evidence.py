"""Read-only HUD evidence extraction from a recorded Assist run.

This recognizes visible judgment text and measures life-bar changes, saving
short frame strips for temporal cross-checks.
It never changes the live input path or equates a key-down with a game hit.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np

TEMPLATE_DIR = Path(__file__).with_name("hud_templates")
GRADE_LABELS = ("MISS", "BAD", "GOOD", "GREAT", "PERFECT")
TIMING_LABELS = ("FAST", "SLOW")
GRADE_EVENT_FIELDS = ("run", "first_frame", "last_frame", "capture_timestamp",
                      "grade", "peak_score", "direction", "direction_peak_score",
                      "life_drop_px_next_800ms", "recent_canceled_hold_ids",
                      "nearby_hold_key_downs", "nearby_tap_key_downs",
                      "combo_value", "physical_note_uid")


def load_grade_templates() -> dict[str, np.ndarray]:
    templates = {}
    for label in GRADE_LABELS:
        image = cv2.imread(str(TEMPLATE_DIR / f"{label}.png"), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(TEMPLATE_DIR / f"{label}.png")
        templates[label] = image
    return templates


def load_timing_templates() -> dict[str, np.ndarray]:
    templates = {}
    for label in TIMING_LABELS:
        image = cv2.imread(str(TEMPLATE_DIR / f"{label}.png"), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise FileNotFoundError(TEMPLATE_DIR / f"{label}.png")
        templates[label] = image
    return templates


def grade_in_frame(frame: np.ndarray, templates: dict[str, np.ndarray]) -> tuple[str, float]:
    """Recognize fixed-position game text; uncertain frames stay UNKNOWN."""
    if frame.shape[:2] != (404, 720):
        return "UNKNOWN", 0.0
    region = cv2.cvtColor(frame[238:274, 290:430], cv2.COLOR_BGR2GRAY)
    scores = {label: float(cv2.minMaxLoc(cv2.matchTemplate(
        region, template, cv2.TM_CCOEFF_NORMED))[1])
        for label, template in templates.items()}
    ranked = sorted(scores, key=scores.get, reverse=True)
    best = ranked[0]
    minimum = .60 if best == "GREAT" else .70
    if scores[best] < minimum or scores[best] - scores[ranked[1]] < .08:
        return "UNKNOWN", scores[best]
    return best, scores[best]


def timing_in_frame(frame: np.ndarray, templates: dict[str, np.ndarray]) -> tuple[str, float]:
    if frame.shape[:2] != (404, 720):
        return "UNKNOWN", 0.0
    region = cv2.cvtColor(frame[264:287, 325:395], cv2.COLOR_BGR2GRAY)
    scores = {label: float(cv2.minMaxLoc(cv2.matchTemplate(
        region, template, cv2.TM_CCOEFF_NORMED))[1])
        for label, template in templates.items()}
    ranked = sorted(scores, key=scores.get, reverse=True)
    best = ranked[0]
    if scores[best] < .78 or scores[best] - scores[ranked[1]] < .07:
        return "UNKNOWN", scores[best]
    return best, scores[best]


def life_fill_px(frame: np.ndarray) -> int | None:
    """Return the right edge of the green LIFE fill at 720x404."""
    if frame.shape[:2] != (404, 720):
        return None
    row = frame[33, 560:649]
    blue, green, red = (row[:, i].astype(np.int16) for i in range(3))
    filled = (green > 145) & (blue > 115) & (green > red + 55)
    indices = np.flatnonzero(filled)
    return int(indices[-1] + 1) if indices.size else None


def read_index(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {int(row["video_frame"]): row for row in csv.DictReader(stream)}


def scan_run(run_dir: Path, out_dir: Path) -> dict[str, int]:
    index = read_index(run_dir / "live_video_index.csv")
    templates = load_grade_templates()
    timing_templates = load_timing_templates()
    with (run_dir / "input_actions.csv").open(encoding="utf-8-sig", newline="") as stream:
        actions = list(csv.DictReader(stream))
    video = cv2.VideoCapture(str(run_dir / "live_source.mp4"))
    if not video.isOpened():
        raise RuntimeError(f"Cannot read video: {run_dir}")
    rows: list[dict[str, object]] = []
    frame_number = 0
    while True:
        ok, frame = video.read()
        if not ok:
            break
        entry = index.get(frame_number, {})
        grade, grade_score = grade_in_frame(frame, templates)
        direction, direction_score = timing_in_frame(frame, timing_templates)
        rows.append({"run": run_dir.name, "video_frame": frame_number,
                     "capture_timestamp": entry.get("capture_timestamp", ""),
                     "gameplay_state": entry.get("gameplay_state", ""),
                     "life_fill_px": life_fill_px(frame),
                     "grade": grade if entry.get("gameplay_state") == "PLAYING" else "UNKNOWN",
                     "grade_score": round(grade_score, 3),
                     "direction": direction if entry.get("gameplay_state") == "PLAYING" else "UNKNOWN",
                     "direction_score": round(direction_score, 3)})
        frame_number += 1
    video.release()
    if not rows:
        raise RuntimeError(f"Video has no decoded frames: {run_dir}")

    # Suppress one-frame animation/compression fluctuations. A persistent
    # two-pixel loss is large enough to suggest lost life, not a proven MISS.
    values = [row["life_fill_px"] for row in rows]
    smoothed = [None] * len(values)
    for i in range(2, len(values) - 2):
        window = [v for v in values[i - 2:i + 3] if v is not None]
        if len(window) >= 3:
            smoothed[i] = int(np.median(window))
    grade_events: list[dict[str, object]] = []
    active_label = "UNKNOWN"
    for i, row in enumerate(rows):
        label = str(row["grade"])
        if label != active_label:
            if active_label != "UNKNOWN":
                grade_events[-1]["last_frame"] = i - 1
            if label != "UNKNOWN":
                grade_events.append({"run": run_dir.name, "first_frame": i,
                                     "last_frame": i, "capture_timestamp": row["capture_timestamp"],
                                     "grade": label, "peak_score": row["grade_score"],
                                     "direction": "UNKNOWN", "direction_peak_score": 0.0})
            active_label = label
        elif active_label != "UNKNOWN":
            grade_events[-1]["last_frame"] = i
            grade_events[-1]["peak_score"] = max(float(grade_events[-1]["peak_score"]),
                                                   float(row["grade_score"]))
        if active_label not in ("UNKNOWN", "PERFECT", "MISS") and row["direction"] != "UNKNOWN":
            if float(row["direction_score"]) > float(grade_events[-1]["direction_peak_score"]):
                grade_events[-1]["direction"] = row["direction"]
                grade_events[-1]["direction_peak_score"] = row["direction_score"]
    events: list[dict[str, object]] = []
    last_edge: int | None = None
    last_event_frame = -100
    for i, value in enumerate(smoothed):
        if rows[i]["gameplay_state"] != "PLAYING" or value is None:
            continue
        if last_edge is not None and value <= last_edge - 2 and i - last_event_frame >= 6:
            events.append({"run": run_dir.name, "video_frame": i,
                           "capture_timestamp": rows[i]["capture_timestamp"],
                           "before_life_fill_px": last_edge, "after_life_fill_px": value,
                           "delta_px": value - last_edge,
                           "game_grade": "UNKNOWN", "grade_frame": "",
                           "grade_to_life_ms": "", "note_uid": "UNKNOWN"})
            last_event_frame = i
        last_edge = value

    for event in events:
        timestamp = float(event["capture_timestamp"])
        preceding = [g for g in grade_events if g["grade"] in {"MISS", "BAD"} and
                     -.10 <= timestamp - float(g["capture_timestamp"]) <= .80]
        if preceding:
            nearest = min(preceding, key=lambda g: abs(timestamp - float(g["capture_timestamp"])))
            event["game_grade"] = nearest["grade"]
            event["grade_frame"] = nearest["first_frame"]
            event["grade_to_life_ms"] = round(1000 * (timestamp - float(nearest["capture_timestamp"])), 1)

    for grade in grade_events:
        timestamp = float(grade["capture_timestamp"])
        grade["life_drop_px_next_800ms"] = sum(int(e["delta_px"]) for e in events
            if 0 <= float(e["capture_timestamp"]) - timestamp <= .8)
        grade["recent_canceled_hold_ids"] = "|".join(a["event_id"] for a in actions
            if a["action"] == "canceled" and a["note_type"] == "hold" and
            0 <= timestamp - float(a["timestamp"]) <= .7)
        grade["nearby_hold_key_downs"] = sum(1 for a in actions
            if a["action"] == "key_down" and a["note_type"] == "hold" and
            abs(timestamp - float(a["timestamp"])) <= .2)
        grade["nearby_tap_key_downs"] = sum(1 for a in actions
            if a["action"] == "key_down" and a["note_type"] == "tap" and
            abs(timestamp - float(a["timestamp"])) <= .2)
        # The ROI for numeric Combo changes with animation and video art.
        # Retain the visual frame anchor rather than guessing a value.
        grade["combo_value"] = "UNKNOWN"
        grade["physical_note_uid"] = "UNKNOWN"

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{run_dir.name}_hud_life_trace.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    with (out_dir / f"{run_dir.name}_grade_events.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=GRADE_EVENT_FIELDS)
        writer.writeheader(); writer.writerows(grade_events)
    fields = ["run", "video_frame", "capture_timestamp", "before_life_fill_px",
              "after_life_fill_px", "delta_px", "game_grade", "grade_frame",
              "grade_to_life_ms", "note_uid"]
    with (out_dir / f"{run_dir.name}_life_changes.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(events)

    # A single contact sheet makes it cheap to inspect the grade, LIFE and
    # Combo together at each measured drop; native source pixels are retained.
    video = cv2.VideoCapture(str(run_dir / "live_source.mp4"))
    def read_frame(number: int) -> np.ndarray:
        video.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(len(rows) - 1, number)))
        ok, frame = video.read()
        if not ok:
            raise RuntimeError(f"Cannot seek source frame {number}: {run_dir}")
        return frame

    for batch in range(0, len(events), 24):
        strips = []
        for event in events[batch:batch + 24]:
            i = int(event["video_frame"])
            strip = np.concatenate([read_frame(j) for j in (i - 6, i, i + 6)], axis=1)
            cv2.putText(strip, f"frame {i}  life {event['delta_px']}", (8, 396),
                        cv2.FONT_HERSHEY_SIMPLEX, .8, (255, 255, 255), 2)
            strips.append(strip)
        if strips:
            cv2.imwrite(str(out_dir / f"{run_dir.name}_life_review_{batch // 24:02d}.jpg"),
                        np.concatenate(strips, axis=0), [cv2.IMWRITE_JPEG_QUALITY, 85])
    good_events = [event for event in grade_events if event["grade"] == "GOOD"]
    for label, selected in (("good_combo", good_events),
                            ("miss", [event for event in grade_events if event["grade"] == "MISS"])):
        for batch in range(0, len(selected), 12):
            strips = []
            for event in selected[batch:batch + 12]:
                i = int(event["first_frame"])
                strip = np.concatenate([read_frame(j) for j in (i - 12, i, i + 12)], axis=1)
                cv2.putText(strip, f"{event['grade']} frame {i} {event['direction']}", (8, 396),
                            cv2.FONT_HERSHEY_SIMPLEX, .8, (255, 255, 255), 2)
                strips.append(strip)
            if strips:
                cv2.imwrite(str(out_dir / f"{run_dir.name}_{label}_review_{batch // 12:02d}.jpg"),
                            np.concatenate(strips, axis=0), [cv2.IMWRITE_JPEG_QUALITY, 85])
    video.release()
    return {"frames": len(rows), "grade_events": len(grade_events),
            "life_change_candidates": len(events)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("output/analysis_v7151_hud"))
    args = parser.parse_args()
    for run_dir in args.run_dirs:
        print(run_dir, scan_run(run_dir, args.out))


if __name__ == "__main__":
    main()
