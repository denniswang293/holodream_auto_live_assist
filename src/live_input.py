"""Hotkey-latched Tap and bounded Hold scheduling for live Assist."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import threading
import time


class NoInputActuator:
    def key_down(self, key):
        raise AssertionError("SHADOW MODE MUST NOT SEND INPUT")

    def key_up(self, key):
        raise AssertionError("SHADOW MODE MUST NOT SEND INPUT")


class MockActuator:
    def __init__(self):
        self.calls = []

    def key_down(self, key):
        self.calls.append(("down", key))

    def key_up(self, key):
        self.calls.append(("up", key))


@dataclass(frozen=True)
class ActionIntent:
    event_id: str
    keys: tuple[str, ...]
    hit_at: float
    uncertainty: float
    note_type: str = "tap"
    path_u: float | None = None
    path_appearance: str | None = None
    revision: int = 0


@dataclass(frozen=True)
class OfferResult:
    accepted: bool
    reason: str
    intent_id: str
    timestamp: float

    def __bool__(self):
        return self.accepted


def verified_keys(config, geometry_sha256):
    """Manual key evidence is pinned to this geometry, never a heuristic score."""
    evidence = config.get("live", {}).get("verified_key_mapping", {})
    if not (evidence.get("geometry_sha256") == geometry_sha256 and
            str(evidence.get("reviewer", "")).strip() and str(evidence.get("evidence", "")).strip()):
        return set()
    keys = evidence.get("keys", [])
    if not isinstance(keys, list) or any(k not in list("SDFJKL") for k in keys):
        raise ValueError("verified_key_mapping.keys must be a list of individually verified S,D,F,J,K,L keys")
    return set(keys)


class TapScheduler:
    def __init__(self, mode="assist", actuator=None, clock=time.perf_counter,
                 focus_check=lambda: True, modifiers_check=lambda: False, on_log=None,
                 max_age=.05, max_lateness=.015, duration=.025, max_uncertainty=.04,
                 max_hold_s=6.):
        if mode != "assist":
            raise ValueError("Only the manually enabled Assist scheduler is supported")
        if not (0 < max_age <= .25 and 0 < max_lateness <= .05 and .005 <= duration <= .1
                and .04 <= max_uncertainty <= .12 and .5 <= max_hold_s <= 8):
            raise ValueError("Invalid freshness/lateness/tap duration")
        self.mode, self.actuator = mode, actuator or NoInputActuator()
        self.clock, self.focus_check, self.modifiers_check = clock, focus_check, modifiers_check
        self.on_log = on_log or (lambda row: None)
        self.max_age, self.max_lateness, self.duration = max_age, max_lateness, duration
        self.max_uncertainty = max_uncertainty
        self.max_hold_s = max_hold_s
        self.lock = threading.RLock()
        self.armed = self.arm_requested = False
        self.arm_generation = 0
        self.context = (-math.inf, "NOT_PLAYING", False, False)
        self.processing_capture = None
        self.waiting_for_decision = False
        self.decision_wait_started_at = None
        self.waiting_for_arm_frame = False
        self.arm_frame_wait_started_at = None
        self.pending, self.held = {}, {}
        # LiveEngine may pause a pending action during a visual dropout. It
        # must explicitly resume or withdraw the frozen key/deadline; the
        # scheduler never invents a replacement action.
        self.suspended = set()
        self.pending_reservations = {}
        self.consumed = set()
        self.recent = deque(maxlen=256)
        self.last_reason = "disabled_at_startup"
        self.stop_event = threading.Event()
        self.thread = None
        self.error = None
        self.sent = 0
        self.sent_taps = 0
        self.sent_holds = 0

    def _log(self, action, reason="", intent=None, key=""):
        note_type = intent.note_type if intent else ""
        if note_type == "hold":
            lifecycle = {"scheduled": "HOLD_SCHEDULED", "key_down": "HOLD_DOWN",
                         "hold_end": "HOLD_TAIL_SEEN", "key_up": "HOLD_UP",
                         "canceled": "HOLD_REJECTED"}.get(action, "")
        else:
            lifecycle = {"scheduled": "SCHEDULED", "key_down": "FIRED",
                         "key_up": "RELEASED", "canceled": "CANCELED",
                         "abstain": "REJECTED"}.get(action, "")
        self.on_log({"action": action, "reason": reason, "timestamp": self.clock(),
                     "event_id": intent.event_id if intent else "", "key": key,
                     "scheduled_hit": intent.hit_at if intent else "", "armed": self.armed,
                     "note_type": note_type, "lifecycle_state": lifecycle,
                     "revision": intent.revision if intent else 0})

    def _ready(self, now):
        return not self._readiness_failure(now)

    def _readiness_failure(self, now):
        captured, state, focused, roi = self.context
        if state != 'PLAYING':return 'game_state_not_playing'
        if not focused:return 'frame_focus_lost'
        if not roi:return 'roi_invalid'
        if not 0 <= now-captured <= self.max_age:return 'validated_capture_expired'
        if not self.focus_check():return 'foreground_window_changed'
        return ''

    def _log_readiness_failure(self, now, reason):
        inflight = ('none' if self.processing_capture is None else
                    f'{(now-self.processing_capture)*1000:.2f}')
        self._log('input_not_ready',f'{reason};decision_age_ms={(now-self.context[0])*1000:.2f};'
                  f'inflight_capture_ms={inflight};state={self.context[1]};'
                  f'frame_focused={self.context[2]};roi_valid={self.context[3]}')

    def update_context(self, captured_at, state, focused, roi_valid=True):
        with self.lock:
            self.context = captured_at, state, focused, roi_valid
            self.processing_capture = None
            if state != "PLAYING" or not focused or not roi_valid:
                self.disarm("game_state_or_focus_or_roi_loss")

    def begin_decision(self, captured_at):
        """Announce a fresh frame being checked without authorizing input."""
        with self.lock:
            now = self.clock()
            if (self.armed and math.isfinite(captured_at) and
                    self.context[0] < captured_at <= now and now-captured_at <= self.max_age):
                self.processing_capture = captured_at

    def toggle(self):
        with self.lock:
            if self.armed or self.arm_requested:
                self.disarm("hotkey_disabled")
                return False
            if not self._ready(self.clock()):
                self.last_reason = "hotkey_rejected_not_ready"
                self._log("arm_rejected", self.last_reason)
                return False
            self.arm_requested = True
            self.last_reason = "release_hotkey_modifiers_to_arm"
            self._log("arm_requested", self.last_reason)
            return True

    def _release(self, key, now):
        _, intent = self.held[key]
        self.actuator.key_up(key)
        del self.held[key]
        self._log("key_up", intent=intent, key=key)

    def release_hold(self, event_id, reason="visible_tail_end"):
        with self.lock:
            for key, (_, intent) in list(self.held.items()):
                if intent.event_id == event_id and intent.note_type == 'hold':
                    self._log('hold_end',reason,intent,key)
                    self._release(key,self.clock())
                    return True
            return False

    def disarm(self, reason):
        with self.lock:
            had_state = self.armed or self.arm_requested or bool(self.pending) or bool(self.held)
            self.armed = self.arm_requested = False
            self.processing_capture = None
            self.waiting_for_decision = False
            self.decision_wait_started_at = None
            self.waiting_for_arm_frame = False
            self.arm_frame_wait_started_at = None
            self.last_reason = reason
            for intent in self.pending.values():
                self.consumed.add(intent.event_id)
                self._log("canceled", reason, intent)
                self._remove_pending_reservation(intent.event_id)
            self.pending.clear()
            self.suspended.clear()
            self.pending_reservations.clear()
            for key in list(self.held):
                try:
                    self._release(key, self.clock())
                except Exception as error:
                    # Attempt EVERY held key even if one release fails. Keep
                    # failed keys for another shutdown release attempt.
                    self.error = self.error or error
                    self._log("release_failed", str(error), key=key)
            if had_state:
                self._log("disarmed", reason)

    def offer(self, intent):
        with self.lock:
            now = self.clock()
            if self.mode != "assist":
                reason = "assist_mode_required"
            elif not self.armed:
                reason = "assist_disarmed"
            else:
                reason = self._readiness_failure(now)
                if not reason and self.modifiers_check():
                    reason = "physical_modifier_held"
            if reason:
                return OfferResult(False, reason, intent.event_id, now)
            if (intent.note_type not in ("tap","hold") or len(intent.keys) != 1 or intent.keys[0] not in list("SDFJKL") or
                    not math.isfinite(intent.hit_at) or not math.isfinite(intent.uncertainty) or
                    not 0 <= intent.uncertainty <= self.max_uncertainty or not now < intent.hit_at <= now+.45):
                return OfferResult(False, "invalid_intent_or_timing", intent.event_id, now)
            if intent.note_type == 'hold' and (intent.path_u is None or
                    not math.isfinite(intent.path_u) or not 0 <= intent.path_u <= 1):
                return OfferResult(False, "invalid_hold_path_position", intent.event_id, now)
            if intent.note_type == 'hold' and intent.path_appearance not in (None,'green_candidate','yellow_bar'):
                return OfferResult(False, "invalid_hold_appearance", intent.event_id, now)
            if intent.event_id in self.consumed:
                return OfferResult(False, "intent_already_consumed", intent.event_id, now)
            if intent.event_id not in self.pending:
                if len(self.pending) >= 32:
                    self._log("abstain", "pending_limit", intent)
                    return OfferResult(False, "pending_limit", intent.event_id, now)
                # Separate simultaneous single-key notes are allowed. A second
                # track on the same key/time is not a new physical-note proof.
                if any(key == intent.keys[0] and abs(hit-intent.hit_at) < .035
                       for key, hit in self.recent):
                    self.consumed.add(intent.event_id)
                    self._log("abstain", "possible_duplicate_physical_note", intent)
                    return OfferResult(False, "possible_duplicate_physical_note", intent.event_id, now)
                self.recent.append((intent.keys[0], intent.hit_at))
                self.pending_reservations[intent.event_id] = (intent.keys[0],intent.hit_at)
                self._log("scheduled", intent=intent, key=intent.keys[0])
            else:
                # A prediction may move while the action remains pending.
                # Its old deadline is not evidence of a press at that time.
                reservation = self.pending_reservations.get(intent.event_id)
                updated = (intent.keys[0],intent.hit_at)
                if reservation != updated:
                    self._remove_pending_reservation(intent.event_id)
                    self.recent.append(updated)
                    self.pending_reservations[intent.event_id] = updated
            self.pending[intent.event_id] = intent
            return OfferResult(True, "accepted", intent.event_id, now)

    def amend_pending(self, intent, *, expected_revision=0, freeze_window_s=0.0):
        """Atomically replace a pending deadline while preserving its key."""
        with self.lock:
            now = self.clock()
            current = self.pending.get(intent.event_id)
            if current is None:
                return OfferResult(False, "pending_intent_missing", intent.event_id, now)
            if current.revision != expected_revision:
                return OfferResult(False, "stale_intent_revision", intent.event_id, now)
            if current.keys != intent.keys:
                return OfferResult(False, "pending_key_is_frozen", intent.event_id, now)
            if now >= current.hit_at - max(0.0, freeze_window_s):
                return OfferResult(False, "deadline_freeze_window", intent.event_id, now)
            if not math.isfinite(intent.hit_at) or not now < intent.hit_at <= now + .45:
                return OfferResult(False, "invalid_amended_deadline", intent.event_id, now)
            if intent.revision <= current.revision:
                return OfferResult(False, "non_monotonic_intent_revision", intent.event_id, now)
            reservation = self.pending_reservations.get(intent.event_id)
            if reservation is not None:
                self._remove_pending_reservation(intent.event_id)
            self.recent.append((intent.keys[0], intent.hit_at))
            self.pending_reservations[intent.event_id] = (intent.keys[0], intent.hit_at)
            self.pending[intent.event_id] = intent
            self._log("amended", f"revision={intent.revision}", intent, intent.keys[0])
            return OfferResult(True, "amended", intent.event_id, now)

    def _remove_pending_reservation(self, event_id):
        reservation = self.pending_reservations.pop(event_id,None)
        if reservation in self.recent:
            self.recent.remove(reservation)

    def suspend(self, event_id):
        """Pause a pending key-down without discarding its frozen intent."""
        with self.lock:
            if event_id in self.pending:
                self.suspended.add(event_id)

    def resume(self, event_id):
        with self.lock:
            self.suspended.discard(event_id)

    def withdraw(self, event_id, reason, *, retryable=False):
        with self.lock:
            intent = self.pending.pop(event_id, None)
            self.suspended.discard(event_id)
            if intent:
                # A canceled action never pressed this key. Remove its time
                # reservation even if the event itself cannot be retried.
                self._remove_pending_reservation(event_id)
                if not retryable:
                    self.consumed.add(event_id)
                self._log("canceled", reason, intent)

    def _release_due(self, now):
        for key, (release_at, intent) in list(self.held.items()):
            if now >= release_at:
                if intent.note_type == 'hold':
                    self._log('hold_end','max_hold_timeout',intent,key)
                self._release(key, now)

    def poll(self):
        with self.lock:
            now = self.clock()
            failure = self._readiness_failure(now)
            if failure:
                captured, state, focused, roi = self.context
                if (self.arm_requested and failure == 'validated_capture_expired' and
                        state == 'PLAYING' and focused and roi and self.focus_check()):
                    # Keep the manual Arm request pending across a brief capture
                    # gap. The latch remains OFF until a fresh, valid frame is
                    # processed; focus/gameplay checks still cancel it.
                    if not self.waiting_for_arm_frame:
                        self.waiting_for_arm_frame = True
                        self.arm_frame_wait_started_at = now
                        self._log('arm_waiting_for_fresh_frame',
                                  f'decision_age_ms={(now-captured)*1000:.2f}')
                    if now-self.arm_frame_wait_started_at <= .2:
                        return
                if (self.armed and failure == 'validated_capture_expired' and
                        state == 'PLAYING' and focused and roi and self.focus_check()):
                    # Pause input during a brief capture gap without dropping
                    # the manual Arm latch. Holds are released by disarm below;
                    # no new key-down is allowed until a fresh frame arrives.
                    self._release_due(now)
                    if not self.held:
                        if not self.waiting_for_decision:
                            self.waiting_for_decision = True
                            self.decision_wait_started_at = now
                            self._log('decision_wait',
                                      f'old_decision_ms={(now-captured)*1000:.2f};key_down_paused')
                        if now-self.decision_wait_started_at <= .2:
                            return
                if self.armed or self.arm_requested:
                    self._log_readiness_failure(now,failure)
                self.disarm("stale_frame_or_focus_loss")
                return
            if self.waiting_for_arm_frame:
                self.waiting_for_arm_frame = False
                self.arm_frame_wait_started_at = None
                self._log('arm_resumed_on_fresh_frame', 'fresh_validated_context')
            if self.waiting_for_decision:
                self.waiting_for_decision = False
                self.decision_wait_started_at = None
                self._log('decision_resumed','fresh_validated_context')
            if self.modifiers_check():
                # Do not synthesize Ctrl+S/Alt+F while hotkey modifiers remain
                # held. Keep the latch until Q toggles it, but drop pending keys.
                for event_id in list(self.pending):
                    self.withdraw(event_id, "physical_modifier_held")
                for key in list(self.held):
                    self._release(key, now)
                return
            if self.arm_requested:
                self.arm_requested, self.armed = False, True
                self.arm_generation += 1
                self.last_reason = "enabled_by_hotkey"
                self._log("armed", self.last_reason)
            self._release_due(now)
            if not self.armed:
                return
            for event_id, intent in list(self.pending.items()):
                if event_id in self.suspended:
                    continue
                if now < intent.hit_at:
                    continue
                del self.pending[event_id]
                self.consumed.add(event_id)
                if now-intent.hit_at > self.max_lateness or intent.keys[0] in self.held:
                    self._remove_pending_reservation(event_id)
                    self._log("abstain", "late_or_key_already_held", intent)
                    continue
                # Re-check focus and capture freshness immediately before down.
                checked_at = self.clock()
                failure = self._readiness_failure(checked_at)
                if failure:
                    self._remove_pending_reservation(event_id)
                    self._log_readiness_failure(checked_at,failure)
                    self.disarm("focus_or_freshness_changed")
                    break
                self.pending_reservations.pop(event_id,None)
                key = intent.keys[0]
                # Retain for emergency release even if SendInput raises.
                self.held[key] = now+(self.max_hold_s if intent.note_type=='hold' else self.duration), intent
                self.actuator.key_down(key)
                self.sent += 1
                if intent.note_type=='hold':self.sent_holds += 1
                else:self.sent_taps += 1
                self._log("key_down", intent=intent, key=key)

    def start(self):
        def run():
            try:
                # On this Windows host Event.wait(2ms) wakes about every
                # 15.6ms, enough to miss the unchanged 15ms lateness budget.
                # time.sleep uses finer timing here (~2ms measured).
                # Check stop again after sleep so shutdown cannot send a key.
                while not self.stop_event.is_set():
                    time.sleep(.002)
                    if self.stop_event.is_set():
                        break
                    if self.error:
                        self.disarm("input_backend_error")
                        return
                    self.poll()
            except Exception as error:
                self.error = error
                try:
                    self.disarm("scheduler_error")
                finally:
                    self.stop_event.set()
        self.thread = threading.Thread(target=run, name="holodream-taps", daemon=False)
        self.thread.start()
        return self

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                raise RuntimeError("Tap scheduler did not stop")
        self.disarm("shutdown")
