"""Small continuity gate for visual Hold head/body evidence.

It does not press keys. It only prevents a single isolated colored fragment
from becoming a Hold candidate and retains accepted identity across a short
dropout for the existing safe tracker.
"""
from __future__ import annotations

from dataclasses import dataclass


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
            evidence.observations += 1
            evidence.max_path_px = max(evidence.max_path_px, candidate.hold_path_px)
            evidence.continuity_confidence = min(1.0, evidence.observations / self.min_head_observations)
            evidence.accepted = (evidence.observations >= self.min_head_observations and
                                 (evidence.max_path_px >= self.min_path_px or
                                  candidate.path_bbox is not None))
            seen.add(id(evidence))
            if evidence.accepted:
                accepted.append(candidate)
        self.evidence = [e for e in self.evidence
                         if timestamp - e.last_seen <= self.max_gap_s + self.dropout_grace_s]
        return accepted
