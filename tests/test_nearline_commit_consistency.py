from dataclasses import replace

from src.live_input import ActionIntent
from src.tracker import Track
from tests.test_pf_schedule_integration import make_engine


def test_committed_tap_survives_compatible_cyan_yellow_fragment(make_candidate):
    engine, scheduler, _ = make_engine()
    engine.commit_entry_y = 290
    original = make_candidate(y=300, keys=["F"], appearance="cyan_bar")
    current = replace(original, appearance="yellow_bar", bbox=(original.bbox[0], 295,
                     original.bbox[2], 5), note_type="unknown")
    track = Track(1, current, history=[(1.1, 300., .5)], bbox=current.bbox,
                  status="tentative", stable_keys=["F"], confirmed_note_type="tap",
                  identity_state="TAP_COASTING")
    intent = ActionIntent("test:1", ("F",), 1.2, .01, "tap")
    commit = (intent, scheduler.arm_generation, 1.215,
              (original.u_min, original.u_max), "cyan_bar", original.bbox, "tap")
    assert engine._commit_still_valid(track, commit, 1.11)
    assert intent.hit_at == 1.2 and intent.keys == ("F",)
    scheduler.close()


def test_committed_tap_does_not_absorb_unrelated_lane_or_unknown_color(make_candidate):
    engine, scheduler, _ = make_engine()
    engine.commit_entry_y = 290
    original = make_candidate(y=300, keys=["F"], appearance="cyan_bar")
    unrelated = make_candidate(y=300, u=.9, keys=["L"], appearance="neutral_candidate")
    track = Track(2, unrelated, history=[(1.1, 300., .9)], bbox=unrelated.bbox,
                  status="tentative", stable_keys=["L"], confirmed_note_type="tap",
                  identity_state="TAP_COASTING")
    intent = ActionIntent("test:2", ("F",), 1.2, .01, "tap")
    commit = (intent, scheduler.arm_generation, 1.215,
              (original.u_min, original.u_max), "cyan_bar", original.bbox, "tap")
    assert not engine._commit_still_valid(track, commit, 1.11)
    scheduler.close()
