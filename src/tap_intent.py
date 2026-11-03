"""Single-owner, immutable lifecycle for accepted Simple Core Tap actions."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from .live_input import ActionIntent
from .intent_store import IntentRevision
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
    revision: int = 0
    initial_hit_at: float | None = None
    total_amend_ms: float = 0.0
    state: str = "PENDING"
    transitions: list[dict] = field(default_factory=list)
    valid_keys: tuple[str, ...] = ()
    physical_cross_at: float | None = None
    lead_ms: float = 0.0
    timing_source: str = "global_trigger_legacy"
    speed_epoch: int = 0
    timing_group_id: str = ""

    def action(self):
        return ActionIntent(self.note_uid, (self.key,), self.hit_at,
                            self.uncertainty, "tap", revision=self.revision)

    def revision_record(self):
        return IntentRevision(self.note_uid, self.arm_generation, self.revision,
                              self.key, self.hit_at, self.hit_at, self.created_at,
                              self.uncertainty)


class TapIntentManager:
    """Own accepted Tap actions until they fire, cancel, or expire.

    Observations can update diagnostics but never change an accepted key or
    deadline. Tracker loss by itself is intentionally not a cancellation.
    """

    def __init__(self, on_transition=None, *, amend_enabled=False,
                 freeze_window_ms=30, max_amend_step_ms=40, max_total_amend_ms=80,
                 allow_earlier_amend=False):
        self.intents: dict[str, TapIntent] = {}
        self.on_transition = on_transition or (lambda row: None)
        self.last_rejections: dict[str, str] = {}
        self._seen: set[str] = set()
        self._confirmed: set[str] = set()
        self.amend_enabled = bool(amend_enabled)
        self.freeze_window_s = float(freeze_window_ms) / 1000
        self.max_amend_step_s = float(max_amend_step_ms) / 1000
        self.max_total_amend_s = float(max_total_amend_ms) / 1000
        self.allow_earlier_amend = bool(allow_earlier_amend)

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
            rejected = {p.note_uid: "assist_disarmed" for p in proposals.values()}
            for proposal in proposals.values():
                self._emit(proposal.note_uid, "NOT_SCHEDULED", now, rejected[proposal.note_uid],
                           key=proposal.key, hit_at=proposal.hit_at)
            self.last_rejections = dict(rejected)
            return accepted, rejected
        readiness = scheduler._readiness_failure(now)
        if readiness:
            rejected = {p.note_uid: readiness for p in proposals.values()}
            for proposal in proposals.values():
                self._emit(proposal.note_uid, "NOT_SCHEDULED", now, readiness,
                           key=proposal.key, hit_at=proposal.hit_at)
            self.last_rejections = dict(rejected)
            return accepted, rejected
        generation = scheduler.arm_generation
        for proposal in sorted(proposals.values(), key=lambda p: (p.hit_at, p.note_uid)):
            old = self.intents.get(proposal.note_uid)
            if old is not None:
                if old.state == "PENDING":
                    if self.amend_enabled and old.key == proposal.key:
                        delta = proposal.hit_at - old.hit_at
                        amend_data = {
                            "amend_direction": "earlier" if delta < 0 else "later" if delta > 0 else "none",
                            "proposed_delta_ms": delta * 1000.0,
                            "old_deadline": old.hit_at,
                            "new_deadline": proposal.hit_at,
                            "freeze_remaining_ms": max(0.0, (old.hit_at - now - self.freeze_window_s) * 1000.0),
                        }
                        if delta < 0 and not self.allow_earlier_amend:
                            self._emit(proposal.note_uid, "REJECTED", now,
                                       "amend_earlier_disabled", key=old.key,
                                       hit_at=proposal.hit_at, revision=old.revision,
                                       previous_hit_at=old.hit_at, **amend_data)
                        elif abs(delta) > self.max_amend_step_s:
                            self._emit(proposal.note_uid, "REJECTED", now,
                                       "amend_step_too_large", key=old.key, hit_at=proposal.hit_at,
                                       revision=old.revision, **amend_data)
                        elif abs(proposal.hit_at - (old.initial_hit_at or old.hit_at)) > self.max_total_amend_s:
                            self._emit(proposal.note_uid, "REJECTED", now,
                                       "amend_total_limit", key=old.key, hit_at=proposal.hit_at,
                                       revision=old.revision, **amend_data)
                        elif proposal.hit_at != old.hit_at:
                            revision = old.revision + 1
                            amended = TapIntent(old.note_uid, old.key, proposal.hit_at,
                                old.arm_generation, old.created_at, proposal.uncertainty,
                                proposal.evidence, old.lane_span, old.appearance,
                                proposal.observed_y, revision, old.initial_hit_at or old.hit_at,
                                old.total_amend_ms + abs(delta) * 1000,
                                old.state, list(old.transitions), old.valid_keys,
                                proposal.physical_cross_at, proposal.lead_ms,
                                proposal.timing_source, proposal.speed_epoch,
                                proposal.timing_group_id)
                            result = scheduler.amend_pending(amended.action(),
                                expected_revision=old.revision,
                                freeze_window_s=self.freeze_window_s)
                            if result.accepted:
                                self.intents[proposal.note_uid] = amended
                                amended.transitions = list(old.transitions) + [{
                                    "state": "AMENDED", "timestamp": now,
                                    "reason": "deadline_updated", "revision": revision,
                                    "previous_hit_at": old.hit_at,
                                    "hit_at": amended.hit_at,
                                    "direction": "later" if delta > 0 else "earlier"}]
                                self._emit(proposal.note_uid, "AMENDED", now, "deadline_updated",
                                           key=amended.key, hit_at=amended.hit_at,
                                           revision=revision, previous_hit_at=old.hit_at,
                                           **amend_data)
                            else:
                                self._emit(proposal.note_uid, "REJECTED", now, result.reason,
                                           key=old.key, hit_at=proposal.hit_at,
                                           revision=old.revision, **amend_data)
                    continue
                rejected[proposal.note_uid] = "intent_terminal_no_reschedule"
                self._emit(proposal.note_uid, "NOT_SCHEDULED", now,
                           rejected[proposal.note_uid], key=proposal.key, hit_at=proposal.hit_at)
                continue
            if proposal.hit_at <= now:
                rejected[proposal.note_uid] = "deadline_already_passed"
                self._emit(proposal.note_uid, "NOT_SCHEDULED", now,
                           rejected[proposal.note_uid], key=proposal.key, hit_at=proposal.hit_at)
                continue
            intent = TapIntent(proposal.note_uid, proposal.key, proposal.hit_at,
                               generation, now, proposal.uncertainty, proposal.evidence,
                               proposal.lane_span, proposal.appearance, proposal.observed_y,
                               0, proposal.hit_at, 0.0, valid_keys=tuple(proposal.valid_keys),
                               physical_cross_at=proposal.physical_cross_at,
                               lead_ms=proposal.lead_ms,
                               timing_source=proposal.timing_source,
                               speed_epoch=proposal.speed_epoch,
                               timing_group_id=proposal.timing_group_id)
            result = scheduler.offer(intent.action())
            if result.accepted:
                self.intents[proposal.note_uid] = intent
                intent.transitions.append({"state": "PENDING", "timestamp": now,
                                           "reason": "scheduler_accepted"})
                self._emit(proposal.note_uid, "PENDING", now, "scheduler_accepted",
                           key=proposal.key, hit_at=proposal.hit_at,
                           arm_generation=generation)
                self._emit(proposal.note_uid, "SCHEDULED", now, "scheduler_accepted",
                           key=proposal.key, hit_at=proposal.hit_at,
                           arm_generation=generation, evidence=proposal.evidence,
                           lane_span=proposal.lane_span, appearance=proposal.appearance,
                           observed_y=proposal.observed_y)
                accepted.append(intent)
            else:
                reason = result.reason
                rejected[proposal.note_uid] = reason
                self._emit(proposal.note_uid, "NOT_SCHEDULED", now, reason,
                           key=proposal.key, hit_at=proposal.hit_at,
                           arm_generation=generation)
        self.last_rejections = dict(rejected)
        return accepted, rejected

    def rekey_for_hold_conflict(self, note_uid: str, new_key: str, scheduler,
                                now: float, *, hold_until: float | None = None,
                                expected_revision: int | None = None,
                                blocked_event_ids: set[str] | None = None):
        """Atomically move one pending Tap to a previously verified key.

        This is deliberately separate from normal ETA amendment.  It is only
        called by the LiveEngine after a new Hold has been accepted, and it
        never changes the Tap deadline or invents a key from geometry.
        """
        intent = self.intents.get(note_uid)
        if intent is None or intent.state != "PENDING":
            return scheduler.rekey_result(False, "tap_not_pending", note_uid, now)
        if blocked_event_ids and note_uid in blocked_event_ids:
            return scheduler.rekey_result(False, "tap_already_committed", note_uid, now)
        if expected_revision is not None and intent.revision != expected_revision:
            return scheduler.rekey_result(False, "stale_intent_revision", note_uid, now)
        valid = set(intent.valid_keys) & set("SDFJKL")
        if new_key not in valid:
            return scheduler.rekey_result(False, "alternative_key_not_verified", note_uid, now)
        if new_key == intent.key:
            return scheduler.rekey_result(False, "alternative_key_same_as_current", note_uid, now)
        if hold_until is not None and not intent.hit_at < hold_until:
            return scheduler.rekey_result(False, "hold_interval_no_overlap", note_uid, now)
        amended = replace(intent, key=new_key, revision=intent.revision + 1)
        result = scheduler.rekey_pending(
            amended.action(), expected_revision=intent.revision,
            expected_arm_generation=intent.arm_generation,
            old_key=intent.key, hold_until=hold_until)
        if not result.accepted:
            return result
        amended.transitions = list(intent.transitions) + [{
            "state": "REKEYED", "timestamp": now,
            "reason": "tap_rekey_for_hold_conflict",
            "old_key": intent.key, "new_key": new_key,
            "revision": amended.revision,
            "hit_at": amended.hit_at}]
        self.intents[note_uid] = amended
        self._emit(note_uid, "REKEYED", now, "tap_rekey_for_hold_conflict",
                   key=new_key, old_key=intent.key, hit_at=amended.hit_at,
                   revision=amended.revision)
        return result

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
