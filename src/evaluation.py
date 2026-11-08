"""Offline note-to-key-action evidence matching for rebuild evaluations.

This module is deliberately separate from the live perception and input path.
Scores are deterministic evidence costs, not probabilities or game judgments.
"""
from __future__ import annotations

import json
import math
from bisect import bisect_left
from typing import Any


_MAX_COST = 5.0
_MIN_MARGIN = 0.8
_TIME_WINDOW = 0.45
_Y_WINDOW = 85.0


def _number(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _samples(value: Any, frames: Any = None) -> list[dict]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    if not isinstance(value, (list, tuple)):
        return []
    if isinstance(frames, str):
        try:
            frames = json.loads(frames)
        except (TypeError, ValueError):
            frames = None
    result = []
    for index, sample in enumerate(value):
        if isinstance(sample, dict):
            t = _number(sample.get("t", sample.get("timestamp")))
            y = _number(sample.get("leading_edge_y", sample.get("trailing_edge_y", sample.get("y"))))
            lo = _number(sample.get("span_lo", sample.get("span_lo0", sample.get("span_lo_0"))))
            hi = _number(sample.get("span_hi", sample.get("span_hi0", sample.get("span_hi_0"))))
            normalized = dict(sample)
        elif isinstance(sample, (list, tuple)) and len(sample) >= 2:
            t, y = _number(sample[0]), _number(sample[1])
            lo = _number(sample[2]) if len(sample) >= 4 else None
            hi = _number(sample[3]) if len(sample) >= 4 else None
            normalized = {}
        else:
            continue
        if t is not None and y is not None:
            if isinstance(frames, (list, tuple)) and index < len(frames):
                normalized.setdefault("source_frame", frames[index])
            result.append({**normalized, "_t": t, "_y": y, "_lo": lo, "_hi": hi,
                           "_index": index})
    return sorted(result, key=lambda row: row["_t"])


def _motion(samples: list[dict], at: float) -> dict | None:
    """Return observed/bracketed or short-extrapolated y with provenance."""
    if not samples:
        return None
    times = [s["_t"] for s in samples]
    pos = bisect_left(times, at)
    if pos < len(samples) and times[pos] == at:
        return {"y": samples[pos]["_y"], "lo": samples[pos]["_lo"], "hi": samples[pos]["_hi"],
                "source": "OBSERVED_SAMPLE", "sample": samples[pos]}
    if pos > 0 and pos < len(samples):
        left, right = samples[pos - 1], samples[pos]
        if right["_t"] == left["_t"]:
            return {"y": left["_y"], "lo": left["_lo"], "hi": left["_hi"],
                    "source": "OBSERVED_SAMPLE", "sample": left}
        ratio = (at - left["_t"]) / (right["_t"] - left["_t"])
        return {"y": left["_y"] + ratio * (right["_y"] - left["_y"]),
                "lo": _interpolate(left["_lo"], right["_lo"], ratio),
                "hi": _interpolate(left["_hi"], right["_hi"], ratio),
                "source": "INTERPOLATED_BRACKET", "sample": left}
    edge = samples[-1] if pos >= len(samples) else samples[0]
    delta = at - edge["_t"]
    if abs(delta) <= 0.12 and len(samples) >= 2:
        pair = samples[-2:] if pos >= len(samples) else samples[:2]
        dt = pair[1]["_t"] - pair[0]["_t"]
        if dt > 0:
            velocity = (pair[1]["_y"] - pair[0]["_y"]) / dt
            return {"y": edge["_y"] + velocity * delta, "lo": edge["_lo"], "hi": edge["_hi"],
                    "source": "SHORT_EXTRAPOLATION", "sample": edge}
    if abs(delta) <= 0.08:
        return {"y": edge["_y"], "lo": edge["_lo"], "hi": edge["_hi"],
                "source": "OBSERVED_NEAREST_SAMPLE", "sample": edge}
    return None


def _interpolate(a: float | None, b: float | None, ratio: float) -> float | None:
    return None if a is None or b is None else a + ratio * (b - a)


def _crossing(samples: list[dict], hit_y: float) -> float | None:
    """Infer a crossing only from adjacent real samples moving downwards."""
    for left, right in zip(samples, samples[1:]):
        if right["_t"] <= left["_t"] or right["_y"] <= left["_y"]:
            continue
        if left["_y"] <= hit_y <= right["_y"]:
            return left["_t"] + (hit_y - left["_y"]) * (right["_t"] - left["_t"]) / (right["_y"] - left["_y"])
    return None


def _keys(note: dict) -> set[str]:
    raw = note.get("keys", "")
    if isinstance(raw, (list, tuple, set)):
        return {str(x).strip() for x in raw if str(x).strip()}
    return {part.strip() for part in str(raw).replace(",", "|").split("|") if part.strip()}


def _id(row: dict, fallback: str) -> str:
    return str(row.get("action_id", row.get("physical_note_id", row.get("note_id", fallback))))


def _candidate(note: dict, action: dict, hit_y: float,
               head: list[dict] | None = None, tail: list[dict] | None = None) -> dict | None:
    action_key = str(action.get("key", ""))
    if action_key not in _keys(note):
        return None
    down = _number(action.get("down_timestamp"))
    up = _number(action.get("up_timestamp"))
    if down is None or str(action.get("status", "complete")) in {"unpaired_up", "partial_at_stop"}:
        return None
    if head is None:
        head = _samples(note.get("head_samples_json", note.get("head_samples", [])),
                        note.get("head_frames_json"))
    if str(note.get('confirmed',True)).lower() not in ('true','1'):
        return None
    if len(head) < 3:
        return None
    displacement = head[-1]["_y"] - head[0]["_y"]
    if displacement < 2.0:  # no evidence of a falling physical head
        return None
    motion = _motion(head, down)
    if motion is None:
        return None
    y_error = abs(motion["y"] - hit_y)
    if y_error > _Y_WINDOW:
        return None
    crossing = _number(note.get("visual_crossing_timestamp"))
    crossing_status = str(note.get("crossing_status", "")).upper()
    inferred_crossing = _crossing(head, hit_y)
    if crossing is None and inferred_crossing is not None:
        crossing = inferred_crossing
        crossing_status = "INTERPOLATED_FROM_HEAD_SAMPLES"
    if crossing is None:
        return None
    dt = abs(down - crossing)
    if dt > _TIME_WINDOW:
        return None

    # A pooled note.keys mask can contain lanes visited at other times. Require
    # the actual interpolated span at this action time to cover its lane.
    lane_index = "SDFJKL".find(action_key)
    if lane_index < 0 or motion["lo"] is None or motion["hi"] is None:
        return None
    lane_lo, lane_hi = lane_index / 6.0, (lane_index + 1) / 6.0
    overlap = min(motion["hi"], lane_hi) - max(motion["lo"], lane_lo)
    if overlap < 0.05:
        return None

    kind = str(note.get("kind", "")).lower()
    tail_y = None
    tail_frame = note.get("last_frame", "")
    if kind == "hold":
        if up is None:
            return None
        if tail is None:
            tail = _samples(note.get("tail_samples_json", note.get("tail_samples", [])))
        tail_cross = _number(note.get("tail_crossing_timestamp"))
        if tail_cross is None:
            tail_cross = _crossing(tail, hit_y)
        if tail_cross is None or abs(up - tail_cross) > 0.4:
            return None
        tail_motion = _motion(tail, up)
        if tail_motion is None or abs(tail_motion["y"] - hit_y) > _Y_WINDOW:
            return None
        tail_y = tail_motion["y"]
    elif kind != "tap":
        return None

    # Time and measured location are independent cues; crossing timestamps are
    # corroboration. Extrapolated positions receive an explicit cost penalty.
    cost = dt / 0.15 + y_error / 42.0
    if crossing_status.startswith("EXTRAPOLATED"):
        cost += 0.8
    if motion["source"] == "SHORT_EXTRAPOLATION":
        cost += 0.7
    return {
        "cost": round(cost, 6), "time_error_s": round(down - crossing, 6),
        "observed_y": round(motion["y"], 3), "tail_observed_y": "" if tail_y is None else round(tail_y, 3),
        "observed_span_lo": round(motion["lo"], 6), "observed_span_hi": round(motion["hi"], 6),
        "key_lane_overlap": round(overlap, 6),
        "y_source": motion["source"], "source_frame": motion["sample"].get("source_frame", note.get("first_frame", "")),
        "crossing_source": crossing_status or "SAMPLE_INTERPOLATION",
        "reason": "legal_key_and_motion_position_and_crossing_time" + ("_with_hold_tail_interval" if kind == "hold" else ""),
    }


def match_reference(notes: list[dict], actions: list[dict], geometry: Any = None) -> list[dict]:
    """Match notes and actual key intervals using legal keys, motion, and time.

    ``geometry`` may be a numeric hit-line y or an object/dict exposing
    ``hit_y``. If omitted, the rebuild's current hit-line estimate (325.5) is
    used. Ambiguous and unsupported rows remain unmatched for review.
    """
    hit_y = 325.5
    if isinstance(geometry, (int, float)):
        hit_y = float(geometry)
    elif isinstance(geometry, dict) and _number(geometry.get("hit_y")) is not None:
        hit_y = float(geometry["hit_y"])
    elif _number(getattr(geometry, "hit_y", None)) is not None:
        hit_y = float(geometry.hit_y)

    notes = list(notes)
    actions = list(actions)
    candidates: dict[tuple[int, int], dict] = {}
    parsed = [( _samples(n.get("head_samples_json", n.get("head_samples", [])), n.get("head_frames_json")),
                _samples(n.get("tail_samples_json", n.get("tail_samples", [])))) for n in notes]
    for ni, note in enumerate(notes):
        for ai, action in enumerate(actions):
            evidence = _candidate(note, action, hit_y, parsed[ni][0], parsed[ni][1])
            if evidence is not None:
                candidates[(ni, ai)] = evidence

    active_n, active_a = set(range(len(notes))), set(range(len(actions)))
    matched: list[tuple[int, int, dict, float]] = []
    # Accept only a unique mutual best with margin on both sides. Repeating
    # this after removing accepted pairs handles ordered same-key sequences.
    while True:
        proposals = []
        for ni in active_n:
            ranked = sorted((e["cost"], ai) for (n, ai), e in candidates.items() if n == ni and ai in active_a)
            if not ranked or ranked[0][0] > _MAX_COST:
                continue
            margin = ranked[1][0] - ranked[0][0] if len(ranked) > 1 else math.inf
            if margin < _MIN_MARGIN:
                continue
            ai = ranked[0][1]
            reverse = sorted((e["cost"], n) for (n, a), e in candidates.items() if a == ai and n in active_n)
            if reverse and reverse[0][1] == ni:
                reverse_margin = reverse[1][0] - reverse[0][0] if len(reverse) > 1 else math.inf
                if reverse_margin >= _MIN_MARGIN:
                    proposals.append((ranked[0][0], ni, ai, min(margin, reverse_margin)))
        if not proposals:
            break
        proposals.sort()
        _, ni, ai, margin = proposals[0]
        evidence = candidates[(ni, ai)]
        matched.append((ni, ai, evidence, margin))
        active_n.remove(ni)
        active_a.remove(ai)

    rows: list[dict] = []
    used_n, used_a = set(), set()
    for ni, ai, evidence, margin in sorted(matched, key=lambda x: (x[1], x[0])):
        note, action = notes[ni], actions[ai]
        used_n.add(ni); used_a.add(ai)
        rows.append({"record_type": "MATCH", "run_id": action.get("run_id", note.get("run_id", "")),
                     "physical_note_id": _id(note, f"note_{ni}"), "action_id": _id(action, f"action_{ai}"),
                     "candidate_note_ids": _id(note, f"note_{ni}"), "candidate_action_ids": _id(action, f"action_{ai}"),
                     **evidence, "margin": 999.0 if math.isinf(margin) else round(margin, 6),
                     "margin_unbounded": math.isinf(margin),
                     "confidence_basis": "numeric_cost_margin_not_probability", "review_status": "AUTOSUPPORTED_NOT_MANUAL",
                     "first_frame": note.get("first_frame", ""), "last_frame": note.get("last_frame", ""),
                     "game_accuracy": "UNVERIFIED"})

    for ni, note in enumerate(notes):
        if ni in used_n:
            continue
        ranked = sorted((e["cost"], ai) for (n, ai), e in candidates.items() if n == ni)
        rows.append({"record_type": "NOTE", "run_id": note.get("run_id", ""),
                     "physical_note_id": _id(note, f"note_{ni}"), "action_id": "",
                     "candidate_note_ids": _id(note, f"note_{ni}"),
                     "candidate_action_ids": "|".join(_id(actions[ai], f"action_{ai}") for _, ai in ranked),
                     "cost": "" if not ranked else ranked[0][0],
                     "margin": "" if len(ranked) < 2 else round(ranked[1][0] - ranked[0][0], 6),
                     "observed_y": "" if not ranked else candidates[(ni, ranked[0][1])]["observed_y"],
                     "reason": "no_supported_candidate" if not ranked else "ambiguous_or_conflict_no_forced_pair",
                     "review_status": "AUTOSUPPORTED_NOT_MANUAL", "game_accuracy": "UNVERIFIED"})
    for ai, action in enumerate(actions):
        if ai in used_a:
            continue
        ranked = sorted((e["cost"], ni) for (ni, a), e in candidates.items() if a == ai)
        rows.append({"record_type": "ACTION", "run_id": action.get("run_id", ""),
                     "physical_note_id": "", "action_id": _id(action, f"action_{ai}"),
                     "candidate_note_ids": "|".join(_id(notes[ni], f"note_{ni}") for _, ni in ranked),
                     "candidate_action_ids": _id(action, f"action_{ai}"),
                     "cost": "" if not ranked else ranked[0][0],
                     "margin": "" if len(ranked) < 2 else round(ranked[1][0] - ranked[0][0], 6),
                     "reason": "no_supported_candidate" if not ranked else "ambiguous_or_conflict_no_forced_pair",
                     "review_status": "AUTOSUPPORTED_NOT_MANUAL", "game_accuracy": "UNVERIFIED"})
    return rows


def evaluate_actions(matches: list[dict], mock_actions: list[dict] | None = None) -> dict:
    """Optional descriptive counts and timing quantiles; never game accuracy."""
    supported = [r for r in matches if r.get("record_type") == "MATCH"]
    errors = sorted(abs(float(r["time_error_s"])) for r in supported if _number(r.get("time_error_s")) is not None)
    def quantile(q: float):
        if not errors:
            return ""
        return round(errors[min(len(errors) - 1, int((len(errors) - 1) * q))], 6)
    return {"reliably_matched": len(supported),
            "unmatched_actions": sum(r.get("record_type") == "ACTION" for r in matches),
            "unmatched_notes": sum(r.get("record_type") == "NOTE" for r in matches),
            "timing_abs_error_p50_s": quantile(.5), "timing_abs_error_p90_s": quantile(.9),
            "mock_action_count": len(mock_actions or []), "game_accuracy": "UNVERIFIED"}
