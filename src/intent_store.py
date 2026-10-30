"""Small immutable revision record used by pending Tap amendments."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentRevision:
    note_uid: str
    arm_generation: int
    revision: int
    key: str
    predicted_hit_at: float
    input_deadline: float
    evidence_at: float
    uncertainty: float
