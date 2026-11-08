"""Small fail-closed scheduler for explicitly armed keyboard actions.

The scheduler has no platform input implementation. ``actuator`` must be
provided by an explicit live-input integration; tests and replay use
``MockActuator`` only.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import threading
import time


def _isfinite(value):
    try: return math.isfinite(value)
    except (TypeError, ValueError): return False


@dataclass(frozen=True)
class Action:
    uid: str
    key: str
    kind: str
    press_at: float
    uncertainty: float
    release_at: float | None = None


@dataclass(frozen=True)
class Result:
    accepted: bool
    reason: str
    uid: str = ""

    def __bool__(self):
        return self.accepted


class MockActuator:
    """In-memory actuator for tests and replay; never sends OS input."""
    def __init__(self):
        self.calls = []
    def key_down(self, key): self.calls.append(("down", key))
    def key_up(self, key): self.calls.append(("up", key))


class Scheduler:
    TAP_S = .025
    FREEZE_S = .030
    MAX_UPDATE_STEP = .040
    MAX_UPDATE_TOTAL = .080
    MAX_EVENTS = 512

    def __init__(self, actuator, clock=time.monotonic, focus_check=lambda: True,
                 modifiers_check=lambda: False, on_event=lambda event: None,
                 max_age=.060, max_lateness=.015, max_hold_s=9.):
        if (not _isfinite(max_age) or max_age <= 0 or max_age > .060 or
                not _isfinite(max_lateness) or max_lateness < 0 or max_lateness > .015 or
                not _isfinite(max_hold_s) or not .5<=max_hold_s<=9):
            raise ValueError("invalid scheduler safety limits")
        self.actuator, self.clock = actuator, clock
        self.focus_check, self.modifiers_check = focus_check, modifiers_check
        self.on_event = on_event
        self.max_age, self.max_lateness, self.max_hold_s = max_age, max_lateness, max_hold_s
        self.lock = threading.RLock()
        self.armed = False
        self.arm_generation = 0
        self.arm_requested = False
        self.context = (None, False, False, False)  # capture, playing, focused, ROI
        self.inflight = None
        self.paused_since = None
        self._down_at = {}
        self.pending, self.held = {}, {}
        self.consumed = set()
        self.fired = set()  # Accepted actuator downs, never game-hit truth.
        self.sent_taps = self.sent_holds = 0
        self.events, self._dispatch = [], []
        self._release_notifications = []
        self.error = None
        self.stop_event, self.thread = threading.Event(), None
        self._updates = {}
        self._origins = {}
        self._deadline_changes = {}
        self._event_sequence = 0

    def _event(self, name, **data):
        self._event_sequence += 1
        row = {"event": name, "at": self.clock(), "event_sequence": self._event_sequence,
               "decision_capture_timestamp": self.context[0], **data}
        self.events.append(row)
        if len(self.events) > self.MAX_EVENTS: del self.events[:len(self.events) - self.MAX_EVENTS]
        self._dispatch.append(row)

    def _flush(self):
        """Callbacks run outside the scheduler lock and must not block."""
        with self.lock:
            rows, self._dispatch = self._dispatch, []
        for row in rows:
            try:
                self.on_event(row)
            except Exception as exc:
                with self.lock:
                    self.error = self.error or exc
                    self._disarm_locked("event_callback_error", notify=False)

    def _valid_context(self, now, allow_inflight=False):
        captured, playing, focused, roi = self.context
        if allow_inflight and self.inflight is not None and (captured is None or self.inflight > captured):
            captured = self.inflight
        if not playing: return "not_playing"
        if not focused: return "frame_unfocused"
        if not roi: return "roi_invalid"
        try: fresh = captured is not None and math.isfinite(captured) and 0 <= now-captured <= self.max_age
        except (TypeError, ValueError): fresh = False
        if not fresh:
            return "stale_capture"
        try:
            if not self.focus_check(): return "focus_lost"
        except Exception: return "focus_check_error"
        return ""

    def begin_frame(self, captured_at, focused=True, roi_valid=True):
        with self.lock:
            now = self.clock()
            valid_time = self._valid_timestamp(captured_at, now)
            self.inflight = captured_at if valid_time else None
            if (not valid_time or not focused or not roi_valid):
                self._disarm_locked("frame_context_invalid")
        self._flush()

    def update_context(self, captured_at, playing, focused, roi_valid=True):
        with self.lock:
            previous=self.context[0]
            invalid_order=(previous is not None and _isfinite(captured_at) and captured_at<previous)
            self.context = (captured_at, bool(playing), bool(focused), bool(roi_valid))
            self.inflight = None
            if (not self._valid_timestamp(captured_at, self.clock()) or
                    invalid_order or not playing or not focused or not roi_valid):
                self._disarm_locked("context_invalid")
        self._flush()

    @staticmethod
    def _valid_timestamp(captured_at, now):
        try: return math.isfinite(captured_at) and captured_at <= now
        except (TypeError, ValueError): return False

    def _validate_action(self, action, now):
        if not isinstance(action, Action): return "invalid_action"
        if (not isinstance(action.uid, str) or not action.uid or
                not isinstance(action.key, str) or len(action.key) != 1 or action.key not in "SDFJKL" or
                action.kind not in ("tap", "hold")):
            return "invalid_action"
        if (not _isfinite(action.press_at) or not _isfinite(action.uncertainty) or
                action.uncertainty < 0 or action.uncertainty > .040 or
                not now < action.press_at <= now + .45):
            return "invalid_action"
        if action.release_at is not None:
            if (not _isfinite(action.release_at) or action.release_at <= action.press_at or
                    action.kind != "hold"):
                return "invalid_action"
        if action.kind == "hold" and action.release_at is not None and action.release_at > action.press_at + self.max_hold_s:
            return "hold_too_long"
        return ""

    def _same_key_conflict(self, action, exclude_uid=None):
        """Reserve time intervals, allowing only known nonoverlapping taps."""
        start = action.press_at
        end = (action.release_at if action.kind == "hold" and action.release_at is not None
               else start + (self.max_hold_s if action.kind == "hold" else self.TAP_S + self.max_lateness))
        for uid, other in self.pending.items():
            if uid == exclude_uid or other.key != action.key: continue
            oend = (other.release_at if other.kind == "hold" and other.release_at is not None
                    else other.press_at + (self.max_hold_s if other.kind == "hold" else self.TAP_S + self.max_lateness))
            if start < oend and other.press_at < end: return True
        for key, other in self.held.items():
            if key != action.key or other.uid == exclude_uid: continue
            down = self._down_at.get(other.uid, other.press_at)
            oend = (other.release_at if other.kind == "hold" and other.release_at is not None
                    else down + (self.max_hold_s if other.kind == "hold" else self.TAP_S))
            if start < oend: return True
        return False

    def toggle(self):
        with self.lock:
            if self.armed or self.arm_requested:
                self._disarm_locked("manual_toggle_off")
                result = Result(False, "disarmed")
            else:
                failure = self._valid_context(self.clock())
                if failure:
                    result = Result(False, failure)
                    self._event("arm_rejected", reason=result.reason)
                else:
                    self.arm_requested = True
                    self._event("arm_requested", reason="waiting_for_modifier_release")
                    result = Result(True, "arm_requested")
        self._flush()
        return result

    def _arm_if_ready(self, now):
        if not self.arm_requested: return
        failure = self._valid_context(now)
        try: modifiers = self.modifiers_check()
        except Exception: modifiers = True
        if failure:
            self._disarm_locked(failure)
        elif not modifiers:
            self.arm_requested, self.armed = False, True
            self.arm_generation += 1
            self._event("armed", generation=self.arm_generation)

    def offer(self, action):
        uid = getattr(action, "uid", "")
        with self.lock:
            now = self.clock()
            self._arm_if_ready(now)
            why = "" if self.armed else "disarmed"
            if not why: why = self._valid_context(now, allow_inflight=True)
            if not why:
                try:
                    if self.modifiers_check(): why = "modifiers_held"
                except Exception: why = "modifiers_check_error"
            if not why: why = self._validate_action(action, now)
            current = self.pending.get(uid) if isinstance(uid, str) else None
            if not why and uid in self.consumed: why = "uid_used"
            if not why and current is not None:
                if action.key != current.key or action.kind != current.kind:
                    why = "pending_key_or_kind_frozen"
                elif now >= current.press_at - self.FREEZE_S:
                    why = "deadline_freeze_window"
                elif (abs(action.press_at - current.press_at) > self.MAX_UPDATE_STEP or
                      abs(action.press_at - self._origins.get(uid, current.press_at)) > self.MAX_UPDATE_TOTAL):
                    why = "deadline_update_bound"
                elif self._same_key_conflict(action, exclude_uid=uid):
                    why = "same_key_conflict"
                else:
                    self.pending[uid] = action
                    self._deadline_changes[uid] = self._deadline_changes.get(uid, 0) + 1
                    self._event("updated", uid=uid, key=action.key, kind=action.kind, scheduled_press=action.press_at)
                    result = Result(True, "updated", uid)
            if not why and current is None and self._same_key_conflict(action): why = "same_key_conflict"
            if not why and current is None:
                self.pending[uid] = action
                self._origins[uid] = action.press_at
                self._deadline_changes[uid] = 0
                self._event("accepted", uid=uid, key=action.key, kind=action.kind, scheduled_press=action.press_at)
                result = Result(True, "accepted", uid)
            elif why: result = Result(False, why, uid)
        self._flush()
        return result

    def update_release(self, uid, release_at):
        with self.lock:
            now = self.clock()
            pair = next(((k, a) for k, a in self.held.items() if a.uid == uid and a.kind == "hold"), None)
            if not pair: result = Result(False, "hold_not_held", uid)
            else:
                key, action = pair
                hardmax = self._down_at.get(uid, action.press_at) + self.max_hold_s
                old = action.release_at if action.release_at is not None else hardmax
                first_estimate = action.release_at is None
                origin, total = self._updates.get(uid, (release_at if first_estimate else old, 0.0))
                if not _isfinite(release_at): reason = "invalid_release_at"
                elif now >= old: reason = "release_expired"
                else:
                    delta = release_at - old
                    reason = ""
                if not reason and now >= old - self.FREEZE_S: reason = "release_frozen"
                elif not reason and not first_estimate and (abs(delta) > self.MAX_UPDATE_STEP or abs(total + delta) > self.MAX_UPDATE_TOTAL): reason = "release_update_bound"
                elif not reason and (release_at <= now or release_at > hardmax): reason = "invalid_release_at"
                if not reason:
                    self.held[key] = replace(action, release_at=release_at)
                    self._updates[uid] = (origin, 0.0 if first_estimate else total + delta)
                    result = Result(True, "updated", uid)
                    reason = ""
                if reason: result = Result(False, reason, uid)
        self._flush()
        return result

    def consume_alias(self,uid,canonical_uid):
        """Retire an image-proven duplicate before it fires; keep the original action."""
        with self.lock:
            if uid==canonical_uid or uid in self.consumed or any(a.uid==uid for a in self.held.values()):
                return Result(False,'alias_already_used',uid)
            self.pending.pop(uid,None);self.consumed.add(uid)
            self._origins.pop(uid,None);self._deadline_changes.pop(uid,None)
            self._event('identity_alias',uid=uid,canonical_uid=canonical_uid,
                        reason='observed_complete_face_after_fragmentation')
        self._flush()
        return Result(True,'alias_consumed',uid)

    def release_hold(self,uid,reason='observed_tail_crossing'):
        with self.lock:
            key=next((k for k,a in self.held.items() if a.uid==uid and a.kind=='hold'),None)
            if key is None:return Result(False,'hold_not_held',uid)
            self._up_locked(key,reason)
        self._flush()
        return Result(key not in self.held,'released' if key not in self.held else 'release_failed',uid)

    def _up_locked(self, key, reason):
        action = self.held[key]
        try:
            self.actuator.key_up(key)
        except Exception as exc:
            self.error = self.error or exc
            self._event("key_up_error", uid=action.uid, key=key)
        else:
            del self.held[key]
            self._down_at.pop(action.uid, None)
            self._release_notifications.append((action.uid, reason))
            self._updates.pop(action.uid, None)
            self._event("released", uid=action.uid, key=key, kind=action.kind,
                        scheduled_press=action.press_at, reason=reason)

    def _disarm_locked(self, reason, notify=True):
        active = self.armed or self.arm_requested or bool(self.pending) or bool(self.held)
        self.armed = self.arm_requested = False
        self.paused_since=None
        for uid in self.pending: self.consumed.add(uid)
        self.pending.clear()
        self._origins.clear(); self._deadline_changes.clear()
        for key in list(self.held): self._up_locked(key, reason)
        if notify and active: self._event("disarmed", reason=reason)
    def disarm(self, reason):
        with self.lock: self._disarm_locked(reason)
        self._flush()
    def drain_releases(self):
        with self.lock: rows, self._release_notifications = self._release_notifications, []
        return rows
    def drain_events(self):
        with self.lock: rows, self.events = self.events, []
        return rows
    def poll(self):
        with self.lock:
            now = self.clock()
            if self.error: self._disarm_locked("scheduler_error")
            self._arm_if_ready(now)
            # Existing holds may be retained during an in-flight fresh frame,
            # but stale capture, focus, ROI or play state always releases them.
            failure = self._valid_context(now, allow_inflight=True)
            if failure=='stale_capture' and self.armed:
                # Stop physical input at 60ms immediately. Retain only the
                # user's latch for the same bounded 200ms recovery used by
                # the previous runtime; released Holds remain consumed.
                if self.paused_since is None:self.paused_since=now
                for key in list(self.held):self._up_locked(key,'stale_capture')
                for uid,action in list(self.pending.items()):
                    if now>action.press_at+self.max_lateness:
                        self.pending.pop(uid);self.consumed.add(uid)
                        self._event('rejected',uid=uid,reason='expired_while_stale')
                if now-self.paused_since>=.2:self._disarm_locked('stale_timeout')
            elif failure and (self.armed or self.held or self.pending): self._disarm_locked(failure)
            else:
                self.paused_since=None
                for key, action in list(self.held.items()):
                    down_at = self._down_at.get(action.uid, action.press_at)
                    deadline = action.release_at if action.release_at is not None else down_at + self.max_hold_s
                    deadline = min(deadline, down_at + self.max_hold_s)
                    if action.kind == "tap": deadline = down_at + self.TAP_S
                    if now >= deadline:
                        reason='tap_end' if action.kind=='tap' else (
                            'hold_hard_timeout' if action.release_at is None or action.release_at>=down_at+self.max_hold_s else 'tail_release')
                        self._up_locked(key,reason)
                if self.error: self._disarm_locked("actuator_error")
                if self.armed:
                    # A newer frame being processed does not invalidate an
                    # already committed action. Only the last fully validated
                    # context may authorize a down; an in-flight timestamp
                    # must NEVER make an old decision fresh enough to press.
                    can_press = not self._valid_context(now)
                    for uid, action in list(self.pending.items()):
                        if not can_press: break
                        if now < action.press_at: continue
                        self.pending.pop(uid); self.consumed.add(uid)
                        failure = self._valid_context(self.clock())
                        if failure:
                            self._disarm_locked(failure); break
                        try: modifiers = self.modifiers_check()
                        except Exception: modifiers = True
                        checked_at = self.clock()
                        failure = self._valid_context(checked_at)
                        if failure or modifiers:
                            self._disarm_locked(failure or "modifiers_held"); break
                        if checked_at-action.press_at > self.max_lateness:
                            self._event("rejected", uid=uid, reason="late"); continue
                        if action.key in self.held:
                            self._event("rejected", uid=uid, reason="key_already_held"); continue
                        self.held[action.key] = action  # retained before down for emergency cleanup
                        self._down_at[uid] = checked_at
                        try: self.actuator.key_down(action.key)
                        except Exception as exc:
                            self.error = self.error or exc
                            self._event("key_down_error", uid=uid, key=action.key)
                            self._disarm_locked("key_down_error"); break
                        if action.kind == "tap": self.sent_taps += 1
                        else: self.sent_holds += 1
                        self.fired.add(uid)
                        self._event("pressed", uid=uid, key=action.key, kind=action.kind,
                                    scheduled_press=action.press_at,
                                    injection_started_at=checked_at,
                                    lateness_ms=(now-action.press_at)*1000)
        self._flush()
    def start(self):
        if self.thread and self.thread.is_alive(): return self
        self.stop_event.clear()
        def run():
            while not self.stop_event.is_set():
                time.sleep(.002)
                if not self.stop_event.is_set():
                    try: self.poll()
                    except Exception as exc:
                        with self.lock:
                            self.error = self.error or exc
                            self._disarm_locked("scheduler_error")
                        self._flush()
        self.thread = threading.Thread(target=run, name="rebuild-scheduler", daemon=True)
        self.thread.start(); return self
    def close(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=2)
        self.disarm("shutdown")
    def snapshot(self):
        with self.lock:
            return {"armed": self.armed, "paused":self.paused_since is not None, "arm_generation": self.arm_generation,
                    "pending": dict(self.pending), "held": dict(self.held),
                    "consumed": set(self.consumed), "fired":set(self.fired), "sent_taps": self.sent_taps,
                    "sent_holds": self.sent_holds, "error": self.error}
