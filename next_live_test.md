# Next live test — gated, short Simple Core trial

## Before the run

1. Review `output/v7_simple_core_ab/simple_core_duplicate_note_audit.csv`; manually classify each candidate pair from the original source frames. Do not label an overlap as a duplicate solely from key/time/span.
2. Add a small independent annotation set for physical note ID, lane, note type, crossing time and visible game judgment. Keep uncertain rows `UNVERIFIED`.
3. Only run Simple Core after that review finds no unexplained wrong-key or duplicate action. Keep V6 config unchanged for rollback.

## 30–60 second procedure

1. Start an easy song in `hololive-Dreams` with the game window in the foreground.
2. From the project root run the controlled linear Simple route:

   ```powershell
   python -m src.live --config config.json --live-config config/live_assist_v5.json --geometry config/geometry_live_assist.json --tap-core simple --predictor legacy --out output/assist
   ```

3. Confirm the window shows `ASSIST INPUT OFF`, the correct game, and calibrated six-lane overlay. Do not Arm if the lanes or gameplay-state label are wrong.
4. Start the song. After the game reports PLAYING, press and release `Ctrl+Shift+Alt+Q` once to Arm. Observe one 30–60 second segment. Do not use a difficult chart for the first run.
5. Press `Esc` or `F12` to stop. The scheduler must release any held key immediately. If any wrong key, stuck Hold, duplicate press or focus issue appears, stop at once and do not repeat.
6. Save and review that run's `live_run.json`, `live_events.csv`, `live_key_actions.csv`, `live_frames.csv` and `live_diagnostics.md`.

Record physical-note truth separately: true MISS, game judgment, wrong key, repeated action, Tap/Hold counts, FPS, dropped frames and latency P95. A scheduler key-down count is not an accuracy score. Do not push run output; the runtime `output/` tree is now ignored.
