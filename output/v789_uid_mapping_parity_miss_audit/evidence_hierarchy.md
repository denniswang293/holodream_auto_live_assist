# V7.8.9 evidence hierarchy

1. **Source evidence:** `live_source.mp4` aligned through `live_video_index.csv` using `source_frame` and `capture_timestamp`.
2. **Recorded software trace:** detector candidates, Live track identity, assignment attempts, PF proposals, intent/decision/scheduler/action CSVs.
3. **Offline replay evidence:** Legacy A and isolated Shadow B using the same recorded candidate stream and capture timestamps.
4. **Human identity label:** the reviewed CSV value (`SAME_PHYSICAL_NOTE`, etc.). It does not prove a global UID mapping or a game hit.
5. **Game judgment:** only a directly traceable game judgment source can establish it. User-entered `PERFECT/GOOD/MISS` without such source is `HUMAN_REPORTED_UNVERIFIED`; aggregate accuracy remains `UNKNOWN`.

The 20 unreviewed cases are retained as `OUT_OF_SCOPE_UNREVIEWED` and excluded from denominators. `FIRED`, `key_down`, UID continuity and same-note labels are never converted into game hit or MISS claims.
