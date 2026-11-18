#!/usr/bin/env python3
"""Render a human-authored geometry Scene JSON to a blank-canvas MP4."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class SceneError(ValueError):
    pass


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise SceneError(message)


def validate_scene(scene: Any) -> dict[str, Any]:
    """Validate and return Scene v1. Coordinates are canvas pixels, origin top-left."""
    _need(isinstance(scene, dict), "scene must be a JSON object")
    _need(scene.get("schema_version") == 1, "schema_version must be 1")
    _need(isinstance(scene.get("title"), str), "title must be a string")
    fps, frames = scene.get("fps"), scene.get("frame_count")
    _need(isinstance(fps, (int, float)) and not isinstance(fps, bool) and 0 < fps <= 240, "fps must be in (0, 240]")
    _need(isinstance(frames, int) and not isinstance(frames, bool) and frames > 0, "frame_count must be a positive integer")
    canvas = scene.get("canvas")
    _need(isinstance(canvas, dict), "canvas is required")
    w, h = canvas.get("width"), canvas.get("height")
    _need(all(isinstance(v, int) and not isinstance(v, bool) and v >= 64 for v in (w, h)), "canvas width and height must be integers >= 64")
    _need(canvas.get("background", "#000000") == "#000000", "only the blank black background is supported")
    guides = scene.get("track_guides")
    _need(isinstance(guides, list) and len(guides) == 6, "track_guides must contain exactly six guides")
    previous_at_y: dict[float, float] = {}
    for i, guide in enumerate(guides):
        if _number(guide):
            _need(0 <= guide < w, f"track_guides[{i}] x coordinate must be inside the canvas")
            points = [[guide, 0], [guide, h - 1]]
        else:
            _need(isinstance(guide, list) and len(guide) >= 2, f"track_guides[{i}] must be an x coordinate or a polyline")
            points = guide
        prev_y = -math.inf
        for j, point in enumerate(points):
            _need(isinstance(point, list) and len(point) == 2 and all(_number(v) for v in point), f"track_guides[{i}][{j}] must be a finite [x, y] point")
            x, y = point
            _need(0 <= x < w and 0 <= y < h, f"track_guides[{i}][{j}] must be inside the canvas")
            _need(y > prev_y, f"track_guides[{i}] points must have strictly increasing y")
            prev_y = y
            if y in previous_at_y:
                _need(x > previous_at_y[y], f"track guides must remain strictly left-to-right at y={y}")
            previous_at_y[y] = x
    judgement = scene.get("judgment_line")
    if _number(judgement):
        _need(0 <= judgement < h, "judgment_line y coordinate must be inside the canvas")
    else:
        _need(isinstance(judgement, dict), "judgment_line must be a y coordinate or a line segment")
        start, end = judgement.get("from"), judgement.get("to")
        _need(
            isinstance(start, list) and isinstance(end, list) and len(start) == len(end) == 2
            and all(_number(v) for v in start + end)
            and all(0 <= x < w and 0 <= y < h for x, y in (start, end))
            and start != end,
            "judgment_line segment requires distinct in-canvas from/to points",
        )
    notes = scene.get("notes")
    _need(isinstance(notes, list), "notes must be an array")
    ids: set[str] = set()
    for i, n in enumerate(notes):
        p = f"notes[{i}]"
        _need(isinstance(n, dict), f"{p} must be an object")
        _need(isinstance(n.get("id"), str) and n["id"] and n["id"] not in ids, f"{p}.id must be a unique non-empty string")
        ids.add(n["id"])
        _need(n.get("type") in ("Tap", "Hold"), f"{p}.type must be Tap or Hold")
        _need(isinstance(n.get("lane"), int) and not isinstance(n.get("lane"), bool) and 0 <= n["lane"] < 6, f"{p}.lane must be 0..5")
        _need(_number(n.get("confidence")) and 0 <= n["confidence"] <= 1, f"{p}.confidence must be in [0,1]")
        _need(isinstance(n.get("source"), dict) and isinstance(n["source"].get("coordinate_system"), str) and n["source"]["coordinate_system"], f"{p}.source.coordinate_system is required")
        _need(isinstance(n["source"].get("provenance"), str) and n["source"]["provenance"], f"{p}.source.provenance is required")
        spans = n.get("intervals")
        _need(isinstance(spans, list) and bool(spans), f"{p}.intervals must be a non-empty array")
        end = -1
        for j, span in enumerate(spans):
            _need(isinstance(span, dict) and span.get("state") in ("visible", "occluded"), f"{p}.intervals[{j}].state must be visible or occluded")
            a, b = span.get("start_frame"), span.get("end_frame")
            _need(isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= frames, f"{p}.intervals[{j}] must be a valid half-open frame range")
            labels = span.get("labels", [])
            _need(isinstance(labels, list) and all(isinstance(label, str) for label in labels), f"{p}.intervals[{j}].labels must be an array of strings")
            inference_labels = {"INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"}
            present = inference_labels.intersection(labels)
            _need(not present or (span["state"] == "occluded" and inference_labels.issubset(set(labels))), f"{p}.intervals[{j}] inferred occlusion must be occluded and carry both INFERRED_OCCLUSION and OFFLINE_RETROSPECTIVE labels")
            _need(a >= end, f"{p}.intervals must be ordered and non-overlapping")
            end = b
        keys = n.get("keyframes")
        _need(isinstance(keys, list) and bool(keys), f"{p}.keyframes must be a non-empty array")
        prev = -1
        for j, k in enumerate(keys):
            _need(isinstance(k, dict), f"{p}.keyframes[{j}] must be an object")
            f = k.get("frame")
            _need(isinstance(f, int) and 0 <= f < frames and f > prev, f"{p}.keyframes frame numbers must be increasing and in range")
            prev = f
            _need(_number(k.get("head_x")) and _number(k.get("head_y")), f"{p}.keyframes[{j}] requires finite head_x/head_y")
            has_width, has_height = "head_width" in k, "head_height" in k
            _need(has_width == has_height, f"{p}.keyframes[{j}] must provide both head_width and head_height")
            if has_width:
                _need(_number(k["head_width"]) and _number(k["head_height"]) and k["head_width"] > 0 and k["head_height"] > 0,
                      f"{p}.keyframes[{j}] head_width/head_height must be finite and positive")
            if n["type"] == "Hold":
                _need(_number(k.get("tail_x")) and _number(k.get("tail_y")), f"{p}.keyframes[{j}] for Hold requires finite tail_x/tail_y")
    return scene


def _number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _at(keys: list[dict[str, Any]], frame: int, field: str) -> float:
    if frame <= keys[0]["frame"]:
        return float(keys[0][field])
    if frame >= keys[-1]["frame"]:
        return float(keys[-1][field])
    for left, right in zip(keys, keys[1:]):
        if left["frame"] <= frame <= right["frame"]:
            t = (frame - left["frame"]) / (right["frame"] - left["frame"])
            return float(left[field]) + t * (float(right[field]) - float(left[field]))
    raise AssertionError("unreachable")


def _strictly_bracketed(keys: list[dict[str, Any]], frame: int) -> bool:
    return any(k["frame"] < frame for k in keys) and any(k["frame"] > frame for k in keys)


def _dashed_line(image: np.ndarray, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int], thickness: int) -> None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    dash, gap = 7.0, 4.0
    pos = 0.0
    while pos < length:
        stop = min(pos + dash, length)
        p1 = (round(start[0] + dx * pos / length), round(start[1] + dy * pos / length))
        p2 = (round(start[0] + dx * stop / length), round(start[1] + dy * stop / length))
        cv2.line(image, p1, p2, color, thickness, cv2.LINE_AA)
        pos += dash + gap


def _dashed_rect(image: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], thickness: int) -> None:
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
    for start, end in zip(corners, corners[1:]):
        _dashed_line(image, start, end, color, thickness)


def _color(hex_color: str) -> tuple[int, int, int]:
    try:
        if len(hex_color) != 7 or not hex_color.startswith("#"):
            raise ValueError
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return b, g, r
    except (ValueError, TypeError):
        raise SceneError(f"invalid color {hex_color!r}; expected #RRGGBB") from None


def render(scene: dict[str, Any], output: Path) -> None:
    scene = validate_scene(scene)
    w, h = scene["canvas"]["width"], scene["canvas"]["height"]
    fps, count = float(scene["fps"]), scene["frame_count"]
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h), True)
    if not writer.isOpened():
        raise RuntimeError(f"could not open MP4 writer for {output}")
    try:
        for frame_no in range(count):
            image = np.zeros((h, w, 3), dtype=np.uint8)
            for guide in scene["track_guides"]:
                points = [[guide, 0], [guide, h - 1]] if _number(guide) else guide
                polyline = np.asarray([[round(x), round(y)] for x, y in points], dtype=np.int32)
                cv2.polylines(image, [polyline], False, (55, 55, 55), 1, cv2.LINE_AA)
            judgment = scene["judgment_line"]
            if _number(judgment):
                start, end = (0, round(judgment)), (w - 1, round(judgment))
            else:
                start = tuple(round(v) for v in judgment["from"])
                end = tuple(round(v) for v in judgment["to"])
            cv2.line(image, start, end, (180, 180, 180), 2, cv2.LINE_AA)
            for note in scene["notes"]:
                visible = any(s["state"] == "visible" and s["start_frame"] <= frame_no < s["end_frame"] for s in note["intervals"])
                inferred = any(
                    s["state"] == "occluded" and s["start_frame"] <= frame_no < s["end_frame"]
                    and {"INFERRED_OCCLUSION", "OFFLINE_RETROSPECTIVE"}.issubset(set(s.get("labels", [])))
                    for s in note["intervals"]
                )
                if not visible and not inferred:
                    continue
                keys = note["keyframes"]
                if inferred and not _strictly_bracketed(keys, frame_no):
                    continue
                color = _color(note.get("color", "#35D5FF" if note["type"] == "Tap" else "#FFB347"))
                hx, hy = round(_at(keys, frame_no, "head_x")), round(_at(keys, frame_no, "head_y"))
                head_width = max(6, round(_at(keys, frame_no, "head_width") if "head_width" in keys[0] else 28))
                head_height = max(4, round(_at(keys, frame_no, "head_height") if "head_height" in keys[0] else 10))
                if note["type"] == "Hold":
                    tx, ty = round(_at(keys, frame_no, "tail_x")), round(_at(keys, frame_no, "tail_y"))
                    body_width = max(6, min(18, round(head_width * 0.10)))
                    tail_width = max(8, round(_at(keys, frame_no, "tail_width") if "tail_width" in keys[0] else head_width * 0.45))
                    tail_height = max(4, round(_at(keys, frame_no, "tail_height") if "tail_height" in keys[0] else head_height * 0.35))
                    if inferred:
                        _dashed_line(image, (hx, hy), (tx, ty), color, max(1, body_width // 3))
                        _dashed_rect(image, tx - tail_width // 2, ty - tail_height // 2, tx + tail_width // 2, ty + tail_height // 2, color, 2)
                        _dashed_rect(image, hx - head_width // 2, hy - head_height, hx + head_width // 2, hy, color, 2)
                    else:
                        cv2.line(image, (hx, hy), (tx, ty), color, body_width, cv2.LINE_AA)  # hold body
                        cv2.rectangle(image, (tx - tail_width // 2, ty - tail_height // 2), (tx + tail_width // 2, ty + tail_height // 2), color, -1, cv2.LINE_AA)
                        cv2.rectangle(image, (hx - head_width // 2, hy - head_height), (hx + head_width // 2, hy), color, -1, cv2.LINE_AA)
                        cv2.line(image, (hx - max(2, head_width // 5), hy - head_height // 2), (hx + max(2, head_width // 5), hy - head_height // 2), (255, 255, 255), max(1, head_height // 8), cv2.LINE_AA)
                else:
                    if inferred:
                        _dashed_rect(image, hx - head_width // 2, hy - head_height, hx + head_width // 2, hy, color, 2)
                    else:
                        cv2.rectangle(image, (hx - head_width // 2, hy - head_height), (hx + head_width // 2, hy), color, -1, cv2.LINE_AA)  # geometric Tap head
                        cv2.line(image, (hx - max(2, head_width // 5), hy - head_height // 2), (hx + max(2, head_width // 5), hy - head_height // 2), (255, 255, 255), max(1, head_height // 8), cv2.LINE_AA)
            writer.write(image)
    finally:
        writer.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", type=Path, help="human-authored Scene JSON")
    parser.add_argument("output", type=Path, help="output MP4 path")
    args = parser.parse_args()
    try:
        scene = validate_scene(json.loads(args.scene.read_text(encoding="utf-8")))
        render(scene, args.output)
    except (OSError, json.JSONDecodeError, SceneError, RuntimeError) as exc:
        parser.error(str(exc))
    print(f"Rendered {scene['frame_count']} frames at {scene['fps']} fps to {args.output}")


if __name__ == "__main__":
    main()
