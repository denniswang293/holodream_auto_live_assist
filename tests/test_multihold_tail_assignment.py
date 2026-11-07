from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.assist_config import resolve_config
from src.calibration import load_calibration
from src.hold_visual import assign_hold_runs
from src.live_engine import LiveEngine
from src.live_input import ActionIntent, MockActuator, TapScheduler


def test_one_displaced_band_has_one_owner_independent_of_order():
    positions = {'left': .20, 'right': .35}
    assert assign_hold_runs([(.28, .31)], positions) == {'right': (.28, .31)}
    assert assign_hold_runs([(.28, .31)], dict(reversed(list(positions.items())))) == {
        'right': (.28, .31)}


def test_merged_bands_partition_existing_centers_and_split_without_stealing():
    positions = {'left': .20, 'middle': .40, 'right': .60}
    assigned = assign_hold_runs([(.10, .70)], positions)
    assert set(assigned) == set(positions)
    assert assigned['left'][1] == assigned['middle'][0]
    assert assigned['middle'][1] == assigned['right'][0]
    # One remaining ribbon belongs to the middle Hold; neighbors cannot use
    # the same pixels merely because they are within the follow distance.
    assert assign_hold_runs([(.31, .49)], positions) == {'middle': (.31, .49)}


def test_duplicate_upper_row_samples_do_not_create_extra_support_owners():
    assert assign_hold_runs([(.28, .31), (.28, .32), (.29, .31)],
                            {'left': .20, 'right': .35}) == {'right': (.28, .32)}


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('appearance', ['green_candidate', 'yellow_bar'])
def test_two_held_keys_do_not_renew_from_one_displaced_ribbon(monkeypatch, reverse, appearance):
    geometry = load_calibration(Path(__file__).resolve().parents[1]/'config/geometry_live_assist.json')
    frame = np.zeros((404, 720, 3), np.uint8)
    clock = SimpleNamespace(now=1000.)
    actuator = MockActuator()
    scheduler = TapScheduler('assist', actuator, clock=lambda: clock.now)
    scheduler.update_context(clock.now, 'PLAYING', True)
    scheduler.toggle(); scheduler.poll()
    engine = LiveEngine(resolve_config(profile='stable').config, geometry, scheduler,
                        clock=lambda: clock.now)
    intents = [ActionIntent('left', ('S',), 1000.01, .001, 'hold', .20, appearance),
               ActionIntent('right', ('F',), 1000.01, .001, 'hold', .35, appearance)]
    for intent in reversed(intents) if reverse else intents:
        assert scheduler.offer(intent)
    clock.now = 1000.01; scheduler.poll()
    monkeypatch.setattr('src.live_engine.path_runs', lambda *args: [(.14, .25), (.32, .43)])
    engine._update_held_holds(frame, clock.now)
    # The last fragment lies between both previous positions; neither is
    # contained, which bypassed the old neighbor-protection condition.
    monkeypatch.setattr('src.live_engine.path_runs', lambda *args: [(.28, .33)])
    for t in (1000.03, 1000.06, 1000.10):
        clock.now = t
        engine._update_held_holds(frame, t)
    assert set(scheduler.held) == {'F'}
    assert ('up', 'S') in actuator.calls and ('up', 'F') not in actuator.calls
    assert sorted(key for action, key in actuator.calls if action == 'down') == ['F', 'S']
    scheduler.close()
