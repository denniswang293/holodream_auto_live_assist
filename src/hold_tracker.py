"""Small continuity gate for visual Hold head/body evidence.

It does not press keys. It only prevents a single isolated colored fragment
from becoming a Hold candidate and retains accepted identity across a short
dropout for the existing safe tracker.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


def select_hold_heads(candidates, *, head_measurement_guard=False, scale_y=1.0):
    """Keep one moving head for duplicate contours of the same visible path.

    A Hold's wide head and thin colored edge can share a path bbox in one
    frame. Sending both to the motion tracker makes them compete for one UID.
    Only exact same-path, same-color, strongly overlapping lane spans merge.
    """
    selected = []
    for candidate in candidates:
        # Near the line a 1--6 px yellow highlight is an edge of the tall head,
        # not its center. Alternating between it and the full head injects
        # a false velocity jump (and can create a second early reservation).
        # Green curves still need their fragment continuity: the eight-player
        # reference replay showed regressions when this was applied to green.
        # Keep distant thin heads and all original contours for visual tail
        # control; this function only selects motion measurements for starts.
        duplicate = None
        if candidate.path_bbox is not None:
            for index, prior in enumerate(selected):
                if (prior.path_bbox != candidate.path_bbox or
                        prior.appearance != candidate.appearance or
                        set(prior.candidate_keys) != set(candidate.candidate_keys)):
                    continue
                overlap = max(0.0, min(prior.u_max, candidate.u_max) -
                              max(prior.u_min, candidate.u_min))
                narrower = min(prior.u_max-prior.u_min,
                               candidate.u_max-candidate.u_min)
                heights = prior.bbox[3], candidate.bbox[3]
                centers = (prior.bbox[1]+heights[0]/2,
                           candidate.bbox[1]+heights[1]/2)
                # Two real heads may share a connected Hold glow. Only a
                # nearby thin edge beside a clearly sized head is removable.
                if (narrower > 0 and overlap / narrower >= .75 and
                        min(heights) <= 6 and max(heights) >= 8 and
                        abs(centers[0]-centers[1]) <= 18):
                    duplicate = index
                    break
        if duplicate is None:
            selected.append(candidate)
            continue
        prior = selected[duplicate]
        head = max((prior, candidate), key=lambda item: item.bbox[2]*item.bbox[3])
        selected[duplicate] = replace(
            head, hold_path_px=max(prior.hold_path_px, candidate.hold_path_px))
    if head_measurement_guard:
        # Merge first so an edge's independently measured path depth remains
        # available to the full head, even though its position is discarded.
        selected = [c for c in selected if not (c.appearance == 'yellow_bar' and
                    c.bbox[3] <= 6 * scale_y and
                    c.bbox[1] + c.bbox[3] / 2 >= 250 * scale_y)]
    return selected


@dataclass
class HoldEvidence:
    appearance: str
    u_min: float
    u_max: float
    first_seen: float
    last_seen: float
    observations: int = 0
    max_path_px: float = 0.0
    accepted: bool = False
    continuity_confidence: float = 0.0


class HoldTracker:
    def __init__(self, *, min_path_px: float, min_head_observations: int = 2,
                 max_gap_s: float = .12, dropout_grace_ms: float = 120):
        self.min_path_px = float(min_path_px)
        self.min_head_observations = max(1, int(min_head_observations))
        self.max_gap_s = float(max_gap_s)
        self.dropout_grace_s = float(dropout_grace_ms) / 1000
        self.evidence: list[HoldEvidence] = []

    @staticmethod
    def _overlap(a, b):
        return max(0.0, min(a.u_max, b.u_max) - max(a.u_min, b.u_min)) / max(
            min(a.u_max - a.u_min, b.u_max - b.u_min), 1e-6)

    def reset(self):
        self.evidence.clear()

    def observe(self, candidates, timestamp):
        accepted = []
        seen = set()
        for candidate in candidates:
            if candidate.appearance not in ("green_candidate", "yellow_bar"):
                continue
            best = None
            for evidence in self.evidence:
                if evidence.appearance != candidate.appearance or timestamp - evidence.last_seen > self.max_gap_s:
                    continue
                overlap = self._overlap(candidate, evidence)
                if overlap >= .25 and (best is None or overlap > best[0]):
                    best = (overlap, evidence)
            if best is None:
                evidence = HoldEvidence(candidate.appearance, candidate.u_min, candidate.u_max,
                                        timestamp, timestamp)
                self.evidence.append(evidence)
            else:
                _, evidence = best
                evidence.u_min = candidate.u_min
                evidence.u_max = candidate.u_max
                evidence.last_seen = timestamp
            # Multiple contours from one frame are not independent temporal
            # evidence. A single frame must not satisfy the two-frame gate.
            if id(evidence) not in seen:
                evidence.observations += 1
            evidence.max_path_px = max(evidence.max_path_px, candidate.hold_path_px)
            evidence.continuity_confidence = min(1.0, evidence.observations / self.min_head_observations)
            # A yellow Tap's complete bar can surround a thin edge contour.
            # That short bbox is not a Hold body. Preserve green early-path
            # continuity; its curved-head evidence follows the existing rule.
            evidence.accepted = (evidence.observations >= self.min_head_observations and
                                 (evidence.max_path_px >= self.min_path_px or
                                  (candidate.path_bbox is not None and
                                   (candidate.appearance != 'yellow_bar' or
                                    candidate.path_bbox[3] >= self.min_path_px))))
            seen.add(id(evidence))
            if evidence.accepted:
                accepted.append(candidate)
        self.evidence = [e for e in self.evidence
                         if timestamp - e.last_seen <= self.max_gap_s + self.dropout_grace_s]
        return accepted
