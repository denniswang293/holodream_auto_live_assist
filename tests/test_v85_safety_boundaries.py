from src.scheduler import Action, MockActuator, Scheduler


class FakeClock:
    def __init__(self, value=10.0):
        self.value = value

    def __call__(self):
        return self.value


def _armed_scheduler(*, focused=lambda: True):
    clock = FakeClock()
    actuator = MockActuator()
    scheduler = Scheduler(actuator, clock=clock, focus_check=focused)
    scheduler.update_context(clock.value - 0.01, playing=True, focused=True, roi_valid=True)
    assert scheduler.toggle().reason == "arm_requested"
    scheduler.poll()
    assert scheduler.armed
    return clock, actuator, scheduler


def _schedule_and_press_hold(clock, scheduler):
    action = Action("hold:1", "D", "hold", clock.value + 0.02, 0.005,
                    release_at=clock.value + 0.50)
    assert scheduler.offer(action)
    clock.value = action.press_at
    scheduler.update_context(clock.value - 0.01, playing=True, focused=True, roi_valid=True)
    scheduler.poll()
    assert scheduler.snapshot()["held"]
    return action


def test_unfocused_frame_context_cannot_arm_or_send_keys():
    clock = FakeClock()
    actuator = MockActuator()
    scheduler = Scheduler(actuator, clock=clock)
    scheduler.update_context(clock.value, playing=True, focused=False, roi_valid=True)

    result = scheduler.toggle()

    assert not result
    assert result.reason == "frame_unfocused"
    assert not scheduler.armed
    assert actuator.calls == []


def test_live_focus_loss_releases_held_key_and_disarms():
    focus = {"value": True}
    clock, actuator, scheduler = _armed_scheduler(focused=lambda: focus["value"])
    _schedule_and_press_hold(clock, scheduler)

    focus["value"] = False
    scheduler.poll()

    assert actuator.calls == [("down", "D"), ("up", "D")]
    assert not scheduler.armed
    assert scheduler.snapshot()["held"] == {}
    assert any(event.get("reason") == "focus_lost" for event in scheduler.events)


def test_stop_hotkey_disarm_releases_held_key():
    clock, actuator, scheduler = _armed_scheduler()
    _schedule_and_press_hold(clock, scheduler)

    scheduler.disarm("stop_hotkey")

    assert actuator.calls == [("down", "D"), ("up", "D")]
    assert not scheduler.armed
    assert scheduler.snapshot()["held"] == {}
    assert any(event.get("reason") == "stop_hotkey" for event in scheduler.events)


def test_hold_beyond_hard_timeout_is_rejected_before_key_down():
    clock, actuator, scheduler = _armed_scheduler()
    action = Action("hold:too-long", "F", "hold", clock.value + 0.05, 0.005,
                    release_at=clock.value + 0.05 + scheduler.max_hold_s + 0.001)

    result = scheduler.offer(action)

    assert not result
    assert result.reason == "hold_too_long"
    assert actuator.calls == []
    assert scheduler.snapshot()["pending"] == {}


def test_stale_capture_releases_held_key_then_disarms_at_existing_timeout():
    clock, actuator, scheduler = _armed_scheduler()
    _schedule_and_press_hold(clock, scheduler)

    clock.value = 10.08  # The last fully validated capture is older than 60 ms.
    scheduler.poll()

    assert actuator.calls == [("down", "D"), ("up", "D")]
    assert scheduler.armed
    assert scheduler.snapshot()["paused"]
    assert scheduler.snapshot()["held"] == {}

    clock.value = 10.281  # More than 200 ms in the stale pause.
    scheduler.poll()

    assert not scheduler.armed
    assert any(event.get("reason") == "stale_timeout" for event in scheduler.events)
    assert actuator.calls == [("down", "D"), ("up", "D")]
