"""Separate visual crossing, game judgment, and input deadline clocks.

The estimator is conservative: until enough labeled game judgments exist it
returns the baseline crossing time unchanged and reports ``shadow`` status.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median


@dataclass(frozen=True)
class JudgmentEstimate:
    visual_crossing_at: float
    game_judgment_at: float
    effective_input_deadline: float
    status: str


class JudgmentTimeEstimator:
    def __init__(self, *, enabled=False, mode="shadow", offset_ms=0.0,
                 input_latency_ms=0.0, min_samples=20):
        self.enabled = bool(enabled)
        self.mode = str(mode)
        self.offset_s = float(offset_ms) / 1000
        self.input_latency_s = float(input_latency_ms) / 1000
        self.min_samples = int(min_samples)
        self.samples: list[float] = []

    @property
    def status(self):
        if not self.enabled:
            return "disabled"
        if len(self.samples) < self.min_samples:
            return "shadow_insufficient_samples"
        return "active" if self.mode == "active" else "shadow"

    def add_labeled_sample(self, visual_crossing_at: float, game_judgment_at: float):
        error = float(game_judgment_at) - float(visual_crossing_at)
        if math.isfinite(error):
            self.samples.append(error)
        return error

    def estimate(self, visual_crossing_at: float) -> JudgmentEstimate:
        crossing = float(visual_crossing_at)
        if not math.isfinite(crossing):
            raise ValueError("visual crossing timestamp must be finite")
        offset = self.offset_s
        if len(self.samples) >= self.min_samples:
            offset = median(self.samples)
        judgment = crossing + offset
        deadline = judgment - self.input_latency_s
        status = self.status
        if status != "active":
            # Baseline behavior remains unchanged until calibration is valid.
            judgment = crossing
            deadline = crossing
        return JudgmentEstimate(crossing, judgment, deadline, status)
