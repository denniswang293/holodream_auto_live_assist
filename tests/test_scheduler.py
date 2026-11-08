from src.scheduler import Action, MockActuator, Scheduler


class Clock:
    def __init__(self, value=10.): self.value = value
    def __call__(self): return self.value
    def set(self, value): self.value = value


def ready(s, c):
    s.update_context(c(), True, True, True)
    assert s.toggle()
    s.poll()
    assert s.armed


def action(uid, key, at, kind="tap", release=None, uncertainty=.005):
    return Action(uid, key, kind, at, uncertainty, release)


def test_simultaneous_distinct_keys_and_same_key_conflict():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("a", "S", 10.01))
    assert s.offer(action("b", "D", 10.01))
    assert s.offer(action("c", "S", 10.01)).reason == "same_key_conflict"
    c.set(10.01); s.poll()
    assert a.calls == [("down", "S"), ("down", "D")]
    assert s.sent_taps == 2


def test_repeat_same_uid_and_tap_hold_mix_require_release():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("tap", "S", 10.01))
    assert s.offer(action("repeat", "S", 10.01)).reason == "same_key_conflict"
    c.set(10.01); s.poll()
    assert s.offer(action("hold", "S", 10.02, "hold")).reason == "same_key_conflict"
    c.set(10.035); s.poll()
    assert a.calls == [("down", "S"), ("up", "S")]


def test_release_updates_step_total_freeze_expiry_and_hard_limit():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("h", "J", 10.01, "hold", 10.5))
    c.set(10.01); s.poll()
    assert s.update_release("h", 10.54)
    assert s.update_release("h", 10.59).reason == "release_update_bound"
    assert s.update_release("h", 10.7).reason == "release_update_bound"
    c.set(10.511); assert s.update_release("h", 10.55).reason == "release_frozen"
    c.set(10.54); assert s.update_release("h", 10.56).reason == "release_expired"
    c.set(16.011); s.update_context(c(), True, True); s.poll()
    assert a.calls[-1] == ("up", "J")
    assert s.drain_releases() == [("h", "tail_release")]


def test_uncertainty_lateness_and_stale_or_unfocused_arm():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c)
    s.update_context(9.9, True, True)
    assert s.toggle().reason == "stale_capture"
    s.update_context(10., True, False)
    assert s.toggle().reason == "frame_unfocused"
    s.update_context(10., True, True); assert s.toggle(); s.poll()
    assert s.offer(action("bad", "S", 10.01, uncertainty=.061)).reason == "invalid_action"
    assert s.offer(action("late", "D", 10.01))
    c.set(10.026); s.poll()
    assert a.calls == []
    s.update_context(9., True, True); s.poll()
    assert not s.armed


def test_inflight_does_not_block_committed_action_with_fresh_validated_context():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("h", "S", 10.01, "hold"))
    c.set(10.01); s.poll(); assert a.calls == [("down", "S")]
    s.offer(action("next", "D", 10.03))
    c.set(10.02); s.begin_frame(10.02)
    c.set(10.03); s.poll()
    assert a.calls == [("down", "S"),("down", "D")]
    s.update_context(10.02, True, True); s.poll()
    assert a.calls[-1] == ("down", "D")


def test_inflight_timestamp_cannot_authorize_down_from_stale_decision():
    c,a=Clock(),MockActuator();s=Scheduler(a,c);ready(s,c)
    assert s.offer(action('next','D',10.08))
    c.set(10.05);s.begin_frame(10.05)
    c.set(10.08);s.poll()
    assert not a.calls
    c.set(10.081);s.update_context(10.05,True,True);s.poll()
    assert a.calls==[('down','D')]


def test_failed_key_up_still_attempts_every_held_key_and_closes_safely():
    class FailingUp(MockActuator):
        def key_up(self, key):
            self.calls.append(("up", key))
            if key == "S": raise OSError("synthetic")
    c, a = Clock(), FailingUp(); s = Scheduler(a, c); ready(s, c)
    s.offer(action("s", "S", 10.01, "hold")); s.offer(action("d", "D", 10.01, "hold"))
    c.set(10.01); s.poll(); s.disarm("test")
    assert ("up", "S") in a.calls and ("up", "D") in a.calls
    assert s.error is not None and not s.armed
    # The module has no OSC or OS input integration: only the mock actuator ran.
    assert all(kind in ("down", "up") for kind, _ in a.calls)


def test_stale_pauses_physical_input_without_restarting_released_hold():
    c,a=Clock(),MockActuator();s=Scheduler(a,c);ready(s,c)
    assert s.offer(action('hold','S',10.01,'hold'))
    c.set(10.01);s.poll()
    c.set(10.071);s.poll()
    assert a.calls==[('down','S'),('up','S')]
    assert s.armed and s.snapshot()['paused']
    c.set(10.08);s.update_context(c(),True,True);s.poll()
    assert s.armed and not s.snapshot()['paused']
    assert s.offer(action('hold','S',10.1,'hold')).reason=='uid_used'
    c.set(10.15);s.poll();c.set(10.351);s.poll()
    assert not s.armed


def test_constructor_action_ranges_and_single_key_validation():
    c, a = Clock(), MockActuator()
    for kwargs in ({"max_age": .061}, {"max_lateness": .016}, {"max_hold_s": float("nan")}):
        try: Scheduler(a, c, **kwargs)
        except ValueError: pass
        else: assert False, kwargs
    s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("multi", "SD", 10.01)).reason == "invalid_action"
    assert s.offer(action("uncertain", "S", 10.01, uncertainty=.041)).reason == "invalid_action"
    assert s.offer(action("now", "D", 10.)).reason == "invalid_action"
    assert s.offer(action("far", "F", 10.451)).reason == "invalid_action"


def test_future_same_key_taps_can_be_queued_but_tap_hold_overlap_cannot():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("one", "S", 10.1))
    assert s.offer(action("two", "S", 10.2))
    assert s.offer(action("overlap", "S", 10.12, "hold", 10.3)).reason == "same_key_conflict"
    assert s.offer(action("hold", "D", 10.1, "hold", 10.3))
    assert s.offer(action("tap", "D", 10.2)).reason == "same_key_conflict"


def test_same_uid_amendment_freeze_step_total_and_consumed_cannot_revive():
    c, a = Clock(), MockActuator(); s = Scheduler(a, c); ready(s, c)
    assert s.offer(action("x", "S", 10.1))
    assert s.offer(action("x", "S", 10.12)).reason == "updated"
    assert s.offer(action("x", "S", 10.161)).reason == "deadline_update_bound"
    assert s.offer(action("x", "D", 10.13)).reason == "pending_key_or_kind_frozen"
    c.set(10.091); s.update_context(c(), True, True)
    assert s.offer(action("x", "S", 10.14)).reason == "deadline_freeze_window"
    c.set(10.121); s.update_context(c(), True, True); s.poll()
    assert s.offer(action("x", "S", 10.2)).reason == "uid_used"


def test_modifiers_checked_again_immediately_before_each_down():
    c, a = Clock(), MockActuator(); state = {"mods": False}
    s = Scheduler(a, c, modifiers_check=lambda: state["mods"]); ready(s, c)
    assert s.offer(action("x", "S", 10.01))
    state["mods"] = True
    c.set(10.01); s.poll()
    assert a.calls == []
    assert not s.armed


def test_recorded_eight_second_hold_is_not_cut_at_six_seconds():
    c,a=Clock(),MockActuator();s=Scheduler(a,c);ready(s,c)
    assert s.offer(action('long_reference','J',10.01,'hold'))
    c.set(10.01);s.poll()
    # REF7 J:000001 is visibly sustained for 8.854s. Fresh validated contexts
    # are essential throughout; this does not relax stale/focus protection.
    for i in range(1,222):
        c.set(10.01+i*.04);s.update_context(c(),True,True);s.poll()
    assert a.calls==[('down','J')]
    c.set(19.011);s.update_context(c(),True,True);s.poll()
    assert a.calls==[('down','J'),('up','J')]
    assert s.drain_releases()==[('long_reference','hold_hard_timeout')]


def test_expired_alias_is_not_reported_as_an_actual_down():
    c,a=Clock(),MockActuator();s=Scheduler(a,c);ready(s,c)
    assert s.offer(action('original','J',10.3))
    assert s.offer(action('fragment','K',10.01))
    c.set(10.027);s.update_context(c(),True,True);s.poll()
    snapshot=s.snapshot()
    assert 'fragment' in snapshot['consumed'] and 'fragment' not in snapshot['fired']
    assert snapshot['pending']['original'].press_at==10.3 and not a.calls


def test_consuming_image_alias_preserves_original_deadline_and_prevents_revive():
    c,a=Clock(),MockActuator();s=Scheduler(a,c);ready(s,c)
    s.offer(action('original','J',10.1));s.offer(action('fragment','K',10.12))
    assert s.consume_alias('fragment','original')
    assert s.snapshot()['pending']['original'].press_at==10.1
    assert s.offer(action('fragment','K',10.2)).reason=='uid_used'
