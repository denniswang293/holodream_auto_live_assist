# V7.14.3 Global miss root-cause replay

Run: `output\run_20261102T155854_233302Z`

Replay uses recorded matched observations and capture timestamps; it does not send input.
FIRED/key_down and replay eligibility are not game HIT evidence; game result remains **UNKNOWN**.

UID rows: 61
New replay first-available UID count: 36
New replay first-eligible UID count: 36

## Candidate game-MISS windows

| window | key_down count | keys | classification |
|---|---:|---|---|
| 13.7-14.3 | 0 |  | UNRESOLVED |
| 35.5-36.2 | 1 | F | UNRESOLVED |
| 41.8-42.2 | 0 |  | UNRESOLVED |

## Interpretation

The three windows require visual frame review against the supplied video before any NO_INPUT or timing classification.
Rows with an improved replay eligibility are candidate scheduling evidence only; they do not authorize bypassing uncertainty, key, Hold, focus, or stale gates.
Per-UID CSV: `v7143_uid_before_after.csv`
