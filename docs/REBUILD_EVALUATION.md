# Rebuild evaluation ? final offline validation

The authoritative outputs are `output/analysis_reference/rebuild_promoted_validation/`. Actual game accuracy is **UNVERIFIED**. This report supersedes earlier checkpoints and intermediate replay directories.

## Same-data comparison

Both engines processed all **26,259 indexed frames across eight recordings** using real capture/acquired timestamps, a controlled 18ms virtual CPU delay and 2ms scheduler poll. This fixed delay permits comparison; it is not every frame's measured runtime cost. Decode time is measured separately. Only MockActuator was used; human key events were evaluation references, never prediction inputs.

Physical correspondence uses motion, timestamp, appearance and legal lane coverage, not equal tracker integers or nth actions. The baseline's center coordinates and exporter action/track IDs were normalized within that system. A different legal key within the bar is valid. The partial reference population is 1,770 supported operations; the whole chart note count and game hit rate are unknown.

| Metric | Original V7.18 | Rebuilt src |
| --- | ---: | ---: |
| Corresponding reference operations | 1219 | 1262 |
| Supported operations without corresponding action | 551 | 508 |
| Raw duplicate-action candidates | 34 | 1 |
| Same 1057 unique paired cases: median absolute down-time difference vs human | 25.087ms | 17.954ms |
| Same paired cases: signed P10 / P50 / P90 | -21.789 / 19.223 / 63.008ms | -20.933 / 11.627 / 45.257ms |
| Sampled process-only P95, same 512-window method | 18.399ms | 14.080ms |

Negative differences mean earlier than the successful human operation, positive later. Neither automatically means FAST/SLOW or a particular game judgment. Unmatched operations include identity-mapping uncertainty and safety/gate rejection; they are not automatically MISS. Candidate counts and simulated downs are not hit counts. The one remaining candidate is retained as UNKNOWN physical correspondence in `residual_identity_cases.csv`, with both trajectories still included in raw metrics; it was not deleted or forcibly merged to improve results.

## Hold results and regressions

Of 27 corresponding Hold operations, 10 ended through a tail deadline and 17 ended through `stale_capture` safety release. These 17 are safety-censored: comparing their up time to human release does not measure tail prediction accuracy. Reference captures are about 39ms apart with 18?20ms acquisition lag, so a 60ms freshness boundary can expire just before the next available packet without a large raw capture gap. The threshold was not relaxed.

A demonstrated late-release case at REF4 D:000035 kept a stale tail at y260 after the complete face split into a second ID. Reuniting face/bevel pixels preserved that endpoint: the local causal replay changed key-up from 2505.750405 to 2502.566474, compared with human up 2502.633751. This is a traceable operation-time improvement, not proof of a game judgment. Intersecting/occluded ribbons and uncalibrated tail release guard remain limitations. The valid 8.854s yellow Hold is covered by the nine-second emergency ceiling and tests.

The candidate still lacks correspondence for 508 supported operations, and 1,066 human operations have no reliable reference-note match. Some Hold outcomes remain early, late or safety-interrupted. Do not claim that the game will finish without MISS.

## Repeatability, latency and safety

A second full first-song replay reproduced `simulated_actions.csv`, `track_summary.csv` and `frame_decisions.csv` byte-for-byte (3,159 frames); wall-clock CPU observations are excluded from this equality check. See `repeatability_check.json`.

The full-recording 80ms CPU stress processed 1,554 of 3,159 frames, overwrote/dropped 1,605 and issued **zero key-downs**. It kept the same freshness/uncertainty/late-input protections. Source regressions test focus loss, Arm/modifier release, cancellation, expiry, alias races, same-key sequences, simultaneous Tap/Hold, long Hold, observed tail and error cleanup. Real Windows input/capture was not run by Codex.

The final 512-window benchmark includes Engine.observe + Engine.decide, excluding decode: P50/P95/P99 = 9.139/14.080/17.629ms. It is a sampled workload; full-run stage quantiles are in each replay summary. Capture backend, encoder, Windows injection and game timing require live verification.

All eight recordings were inspected during debugging. Only the first four trained timing weights, but the final four are no longer a blind algorithm holdout; chart-disjointness is unknown. Validate on a new live run before making a generalization claim.

## Reproduce

```powershell
python tools/replay_recordings.py --all-recordings output/recording --out output/analysis_reference/new_replay
python tools/compare_rebuild.py --rebuild-dir output/analysis_reference/new_replay --output-dir output/analysis_reference/new_replay
python tools/report_failures.py --results output/analysis_reference/new_replay
python tools/benchmark_rebuild.py --out output/analysis_reference/new_benchmark.json
python -m pytest -q
```

`per_note_comparison.csv`, `per_session_evaluation.csv`, `failure_cases.csv`, `major_cases.csv` and indexed source panels preserve the cases and stage reasons. Source-backed regression fixtures are in `tests/fixtures/` with timestamp/geometry provenance.
