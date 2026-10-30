# Particle Filter Tap ETA

Ordinary confirmed cyan/yellow Tap tracks use a per-track, vectorized particle
filter as their primary position and trigger-line ETA estimator. The estimate
uses host capture timestamps. Tracker confirmation, observed note type, lane/key
evidence, LiveEngine eligibility, and all TapScheduler safety checks remain
independent gates. A PF estimate cannot establish those facts.

## Run and rollback

From the project root, start Assist in the default particle mode:

```powershell
python -m src.live --predictor particle
```

Input starts OFF. The existing Ctrl+Shift+Alt+Q manual latch is still required;
Esc/F12, lost focus, stale capture, invalid ROI, and game-state loss keep their
existing disarm and release behavior. Hold detection and its visible-tail key
release path remain unchanged. The input target remains `y=310.5`, with the
existing 15 px advance to the measured physical line near `y=325.5`.

To roll back the estimator at startup without changing files:

```powershell
python -m src.live --predictor legacy
```

This selects the previous Theil–Sen/MAD Predictor. The selection is written to
the run's configuration snapshot. The default is configured in
`config/live_assist_v5.json`; `--predictor` overrides it for that process.

## Configuration

The initial config uses 128 particles, a Student-t observation likelihood,
systematic resampling below 50% ESS, four real observations before PF readiness,
90 ms maximum coast, 40 ms P10–P90 maximum width, and 95% minimum valid crossing
mass. Particle noise is explicit in the JSON files. A rejected/invalid PF
prediction does not silently fall back to legacy; it abstains. Select `legacy`
explicitly to roll back.

The PF reports trigger-line P10/P50/P90 ETA and absolute `hit_at`, valid crossing
mass, ESS, real observation count, measurement status, coast duration, and a
separate physical judgment-line time. `hit_time` continues to mean the trigger
line for compatible LiveEngine and Scheduler use. The physical line is
diagnostic only and does not retarget the scheduled key.

## Offline paired replay

Use a paired Assist run containing `live_source.mp4`, `live_video_index.csv`,
and `live_run.json`:

```powershell
python -m tools.evaluate_particle_eta `
  --run-dir output/assist/run_YYYYMMDDTHHMMSS_ffffffZ `
  --out output/assist/particle_filter_YYYYMMDD
```

The tool decodes the same source frames and uses the recorded capture timestamps
for legacy and 64/128/256-particle MockActuator runs. It writes frame diagnostics,
event/action timelines, a benchmark JSON, and a tracker-ID-only comparison. The
offline Mock arm is simulated only while indexed PLAYING/focus are valid; it
does not use Windows input. Encoded-video replay and tracker IDs are not physical
ground truth. It cannot establish hit accuracy or game judgments.

Run the regression suite with:

```powershell
python -m pytest -q
```

## Controlled live check

1. Start `python -m src.live --predictor particle` and leave Assist disarmed.
2. Use a simple song for 15–30 seconds. Check the new `live_events.csv`
   particle columns, stable PLAYING FPS, and that Hold heads still follow the
   existing visible-tail rule.
3. Only after the disarmed observation looks normal, manually arm with
   Ctrl+Shift+Alt+Q and release the modifiers. Test 15–30 seconds, then stop with
   Esc/F12 if there is any duplicate, wrong-lane action, stuck key, or unstable
   ETA.
4. Review `live_key_actions.csv`, the game judgments, and the video together.
   Count only manually matched physical notes. Do not treat scheduler key-downs
   or PF confidence as hits.
5. Repeat for 30–60 seconds only if the short test has no safety issue. Use
   `--predictor legacy` for the immediate fallback.

No real game run was performed by this implementation. Accuracy and live
particle-mode FPS remain UNVERIFIED until the user performs the controlled
test.
