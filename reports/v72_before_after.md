# V7.2 before / after

## Baseline

Run `output/run_20261031T014240_674759Z`: 1,251 processed / 1,274 acquired;
23 dropped, 0 stale; capture/processing 60.679/54.737 FPS; latency P50/P95
9.173/27.371 ms. Simple Tap had 70 detected, 33 confirmed, 18 scheduled,
16 fired, and 2 canceled. Hold had 5 key-down actions. Game judgments are
unverified.

## Implemented

- PR0: offline `tools/replay_run.py` and `reports/v72_replay/` note fates and
  fixed suspect timelines. Counts are unique note_uid outcomes, not frame rows.
- PR1: bounded Hold pending coasting keeps an already accepted Hold through a
  short confirmed-head dropout. It does not extend the deadline, change the
  key, or bypass focus/PLAYING/ROI/freshness checks. Expiry records the original
  deadline, remaining time, last valid head, and association reason.
- PR2: scheduler records process/in-flight timing fields and distinguishes a
  stale-context timeout from a focus/ROI disarm. The pause remains bounded at
  200 ms and never authorizes an in-flight frame by itself.
- PR3: Tap decision traces now include `first_possible_schedule_at` and
  `last_safe_schedule_at`; existing Particle gates remain unchanged.
- PR4: reservations carry their owning note UID during planning, so a pending
  note does not conflict with its own reservation while other notes still do.
  Amendments remain revisioned, atomic, key-frozen, and bounded.

No game hit rate is inferred from FIRED or key-down counts. No Git branch or
commit was created.
