# Rebuild implementation result

The independent core has replaced `src/`. The staging `rebuild/` directory and experimental launcher were removed. There is one Active runtime; it does not import the old engine, Global ETA, PF, intent store, legacy profiles or shadow planners. Only verified Windows operations and the existing geometry were reused.

## Answers to the nine delivery questions

1. **Data:** eight recordings, all usable for indexed analysis, 26,259 frames and 2,836 balanced key intervals. Nominal 60FPS differs from observed ~25.5Hz; actual indexed clocks are used. All 40 original files are byte-identical. Song/difficulty/chart identity remain UNKNOWN where metadata cannot establish them.
2. **Recognition:** shared geometry rectifies the lane region; colored/neutral plate faces and directional ribbon evidence identify notes. Bright symbol gaps and narrow bevel/shadow bands are consolidated, followed by post-union NMS. Sparse indexed real-image fixtures guard against renewed splits.
3. **Tap timing:** robust per-note log-motion fit uses only acquired real observations. Absolute visual crossing, reference-success input target and actual actuator time remain distinct. The learned ?16.536ms input offset is not a game-center estimate; unavailable/stale/uncertain predictions abstain.
4. **Hold/chords:** retain the starting key; use unique body/tail ownership with frame-local component IDs, measured/predicted tail release and a nine-second safety ceiling. Disjoint simultaneous notes and same-key consecutive taps remain independent. A recovered complete Tap face can consolidate a fragmented ID using prior complete-span/motion evidence, without an unconditional time-only merge. Original reservations stay bounded; already fired inputs are distinguished from canceled/expired IDs.
5. **Measured changes:** supported correspondences rose from 1,219 to 1,262; 1,057 unique common cases reduced median absolute operation-time difference from 25.087 to 17.954ms. Raw duplicate candidates fell from 34 to one unresolved pair. Sampled process P95 improved; see REBUILD_EVALUATION.md. Some Hold up-times remain poor/safety-censored; no actual hit-rate improvement is claimed.
6. **Unresolved:** 1,066 human operations and 15,320 visual hypotheses lack reliable physical matching. One final trajectory pair remains UNKNOWN. Labels are retained, not forced or discarded to inflate metrics.
7. **Architecture:** 35 original modules left the runtime; 14 rebuilt modules now form src. The old source is archived locally for rollback/offline comparison and is not a runtime dependency. Required tests and replay/evaluation tools remain.
8. **Start:** use `tools/launch_assist.cmd`, select Y for diagnostic video, focus the game and press/release Ctrl+Shift+Alt+Q. Esc/F12 stops and releases keys. `launch_assist_clean.cmd` uses the same core with no output files. Input always starts OFF.
9. **Still requires real game:** actual result-screen judgments, backend timing transfer, Windows injection latency, curved/overlapping Hold endings and unfamiliar charts. The game hit rate remains UNVERIFIED.

## Files and validation

Core: model, recordings, perception, tracking, timing, engine, scheduler, capture, windows, diagnostics, replay, evaluation, live and package marker. Updated launchers, requirements-dev, pytest configuration, 109 regression/safety tests, four timestamped real-image fixtures and repeatable audit/replay/evaluation tools accompany it. Exact source diff: `output/analysis_reference/rebuild_source_changes.diff`.

Validation: all eight complete causal replays; full first-song repeatability; 80ms full-source stress with no unsafe downs; process-only sampled and full-run stage costs; full pytest. No real SendInput, capture or global hotkey was exercised by the agent. Four Luna high/quick scoped tasks assisted evidence, I/O metadata and documentation; primary integration and acceptance remained with Codex.

Cleanup archived the former runtime and superseded docs, removed the duplicate candidate launcher and staging directory, and cleared local Python caches. Original recordings and historical Output were retained. `original_runtime_rollback.zip` is a verified local rollback package. No Git commands were executed.

## First real-game validation

Run a known easy chart for 30?60 seconds with recording Y, unchanged game settings and the game in foreground. Arm manually after gameplay is ready. Stop with Esc/F12. Compare actual Perfect/Great/Good/Bad/Miss, combo/life and full key-down/up traces against the same chart. Use the new run's source/index and result screen; do not use scheduler-down counts as hits. Test denser/curved Holds only after this short control. Pure no-logs mode is unsuitable for collecting analysis evidence.
