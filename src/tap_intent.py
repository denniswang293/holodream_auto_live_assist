"""Single-owner, immutable lifecycle for accepted Simple Core Tap actions."""
from __future__ import annotations

from dataclasses import dataclass, field

from .live_input import ActionIntent
from .tap_planner import TapProposal


TERMINAL = {"FIRED", "CANCELED", "EXPIRED"}


@dataclass
class TapIntent:
    note_uid: str
    key: str
    hit_at: float
    arm_generation: int
    created_at: float
    uncertainty: float
    evidence: str
    lane_span: tuple[float, float]
    appearance: str
    observed_y: float | None
    state: str = "PENDING"
    transitions: list[dict] = field(default_factory=list)

    def action(self):
        return ActionIntent(self.note_uid, (self.key,), self.hit_at,
                            self.uncertainty, "tap")


class TapIntentManager:
    """Own accepted Tap actions until they fire, cancel, or expire.

    Observations can update diagnostics but never change an accepted key or
    deadline. Tracker loss by itself is intentionally not a cancellation.
    """

    def __init__(self, on_transition=None):
        self.intents: dict[str, TapIntent] = {}
        self.on_transition = on_transition or (lambda row: None)
        self.last_rejections: dict[str, str] = {}
        self._seen: set[str] = set()
        self._confirmed: set[str] = set()

    def note_seen(self, note_uid: str, timestamp: float):
        if note_uid not in self._seen:
            self._seen.add(note_uid)
            self._emit(note_uid, "DETECTED", timestamp, "simple_track_created")

    def note_confirmed(self, note_uid: str, timestamp: float):
        if note_uid not in self._confirmed:
            self._confirmed.add(note_uid)
            self._emit(note_uid, "CONFIRMED", timestamp, "ordinary_tap_motion_confirmed")

    def _emit(self, note_uid: str, state: str, timestamp: float, reason: str, **data):
        self.on_transition({"note_uid": note_uid, "state": state,
                            "timestamp": timestamp, "reason": reason, **data})

    def schedule(self, proposals: dict[int, TapProposal], scheduler, now: float):
        accepted, rejected = [], {}
        self.last_rejections = {}
        if not scheduler.armed:
            return accepted, {p.note_uid: "assist_disarmed" for p in proposals.values()}
        readiness = scheduler._readiness_failure(now)
        if readiness:
            return accepted, {p.note_uid: readiness for p in proposals.values()}
        generation = scheduler.arm_generation
        for proposal in sorted(proposals.values(), key=lambda p: (p.hit_at, p.note_uid)):
            old = self.intents.get(proposal.note_uid)
            if old is not None:
                if old.state == "PENDING":
                    continue
                rejected[proposal.note_uid] = "intent_terminal_no_reschedule"
                continue
            if proposal.hit_at <= now:
                rejected[proposal.note_uid] = "deadline_already_passed"
                continue
            intent = TapIntent(proposal.note_uid, proposal.key, proposal.hit_at,
                               generation, now, proposal.uncertainty, proposal.evidence,
                               proposal.lane_span, proposal.appearance, proposal.observed_y)
            if scheduler.offer(intent.action()):
                self.intents[proposal.note_uid] = intent
                intent.transitions.append({"state": "PENDING", "timestamp": now,
                                           "reason": "scheduler_accepted"})
                self._emit(proposal.note_uid, "SCHEDULED", now, "scheduler_accepted",
                           key=proposal.key, hit_at=proposal.hit_at,
                           arm_generation=generation, evidence=proposal.evidence,
                           lane_span=proposal.lane_span, appearance=proposal.appearance,
                           observed_y=proposal.observed_y)
                accepted.append(intent)
            else:
                reason = scheduler.last_reason or "scheduler_rejected"
                rejected[proposal.note_uid] = reason
                self._emit(proposal.note_uid, "NOT_SCHEDULED", now, reason,
                           key=proposal.key, hit_at=proposal.hit_at,
                           arm_generation=generation)
        self.last_rejections = dict(rejected)
        return accepted, rejected

    def record_action(self, action: dict):
        note_uid = action.get("event_id", "")
        intent = self.intents.get(note_uid)
        if intent is None or intent.state != "PENDING":
            return
        kind = action.get("action", "")
        state = {"key_down": "FIRED", "canceled": "CANCELED",
                 "abstain": "EXPIRED"}.get(kind)
        if state is None:
            return
        reason = action.get("reason", "")
        intent.state = state
        intent.transitions.append({"state": state,
                                   "timestamp": action.get("timestamp", intent.created_at),
                                   "reason": reason})
        self._emit(note_uid, state, action.get("timestamp", intent.created_at),
                   reason, key=intent.key, hit_at=intent.hit_at,
                   arm_generation=intent.arm_generation)

    def fixed_key(self, note_uid: str):
        intent = self.intents.get(note_uid)
        return intent.key if intent and intent.state == "PENDING" else None

    def state_for(self, note_uid: str):
        intent = self.intents.get(note_uid)
        return intent.state if intent else "UNSCHEDULED"
