from tools.replay_lane_filter_measured import stale_event_counts


def test_stale_event_counts_selects_only_matching_scheduler_events():
    events = [
        {"event": "input_paused", "reason": "stale_capture"},
        {"event": "input_paused", "reason": "other"},
        {"event": "disarmed", "reason": "stale_timeout"},
        {"event": "disarmed", "reason": "replay_end"},
    ]

    assert stale_event_counts(events) == {
        "stale_pause_events": 1,
        "stale_timeout_disarms": 1,
    }
