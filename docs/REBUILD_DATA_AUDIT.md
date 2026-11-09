# Rebuild recording data audit

## Source and schema

All eight original `output/recording/run_*` directories were audited. Each contains `session.json`, `live_video_index.csv`, `player_key_events.csv`, `markers.csv` and `live_source.mp4`. The sessions identify HoloDream Player Recorder 1.0.0, manual-player capture, host performance-counter timestamps, nominal video FPS 60, no automatic input and no audio. `game_judgment_accuracy` is `UNKNOWN`.

| File | Fields used | Interpretation |
| --- | --- | --- |
| `live_video_index.csv` | `video_frame`, `source_frame`, capture/acquired timestamps, elapsed time and capture metadata | `video_frame` is the encoded playable ordinal; `source_frame` preserves acquisition sequence. Timestamps are host-clock seconds. |
| `player_key_events.csv` | timestamp, elapsed time, action, key, scan code, injected/focused flags, held keys | Key-down and key-up transitions are normalized into stable action intervals. |
| `markers.csv` | timestamp, elapsed time, kind and note | Recording start defines the elapsed clock; stop records the end of manual capture. |

The indexed reader decodes in encoded/index order and preserves capture/acquired timestamps. It rejects noncontiguous encoded ordinals, timestamp-order violations and an MP4 frame count that differs from the index. Source acquisition gaps do not seek or reorder encoded video. Nominal FPS and MP4 frame numbers are not timing clocks. The reader is [src/recordings.py](../src/recordings.py).

## Findings

- All eight MP4 files decode to 1280×720 frames. Each decoded frame count equals the index row count and the session's verified frame count; encoded ordinals are contiguous.
- Index and key-event elapsed times match host timestamps relative to session start. Capture, acquisition, encoding, marker and key-event timestamps use the host performance-counter clock and are monotone.
- The recordings declare nominal 60 FPS, while median indexed capture intervals are about 39 ms (roughly 25.5 Hz). This metadata/cadence discrepancy is disclosed; indexed timestamps retain usable timing. Long intervals are listed in `clock_anomalies.csv`.
- The eight key traces contain 2,836 downs and 2,836 ups. They are balanced: no duplicate downs, unpaired ups, keys held at stop, focus loss, injected key events or recorder-reported lost events. The normalizer retains stable IDs, host down/up timestamps, elapsed times, duration and completeness status.
- All eight runs classify as usable under the declared recording-quality rule. This describes recording integrity, not game judgment accuracy. Song and difficulty remain unknown where session metadata does not establish them.

## Reference artifacts and limits

The original rebuild generated normalized sessions, player actions, indexed frame timelines, clock anomalies, data-quality reports, visual hypotheses and supported action associations. These generated analysis datasets have since been removed; the source recordings are retained. There are 26,259 indexed frames, 17,090 visual hypotheses, 1,770 supported action associations (including 36 Holds), and 1,066 human actions left unassociated as UNKNOWN. These counts do not claim complete per-note truth or actual game accuracy.

The historical extractor snapshots and command-line analysis utilities have been retired. Current regression examples are self-contained under `tests/fixtures/`. See [ground truth](REBUILD_GROUND_TRUTH.md) for the retained timing-reference provenance.

The capture-to-acquired interval is typically 18–20 ms. The files do not show the exact display exposure time within that interval. Live-backend transfer and downstream device/game timing remain unverified.

