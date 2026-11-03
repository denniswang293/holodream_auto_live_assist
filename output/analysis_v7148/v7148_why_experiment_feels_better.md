# V7.14.8 Why tap-earlier may feel better

This report reconstructs deadline changes from the two user A/B runs.
It separates accepted action changes from inferred/shadow estimates and never treats key_down/FIRED as game hit truth.

## Run availability
- baseline: `output\assist\v7147_baseline\run_20261103T054928_927271Z` → `OK`
- experiment: `output\assist\v7147_experiment\run_20261103T055219_493952Z` → `OK`

## Per-group ledger metrics
### baseline
- UIDs: 187; accepted earlier amendment actions: 0 across 0 UIDs.
- Earlier delta P10/P50/P90: UNKNOWN / UNKNOWN / UNKNOWN ms.
- Final net shift P10/P50/P90: 0.0 / 5.125518364366144 / 39.08950220211409 ms.
- UIDs with direction reversals: 0; no-input UIDs: 1; FIRED state UIDs: 177 (not hit truth).
### experiment
- UIDs: 183; accepted earlier amendment actions: 779 across 144 UIDs.
- Earlier delta P10/P50/P90: -20.989997312426567 / -4.070493421750143 / -0.5042183620389544 ms.
- Final net shift P10/P50/P90: -41.32757905172184 / -6.767971935914829 / 19.164697389351254 ms.
- UIDs with direction reversals: 135; no-input UIDs: 0; FIRED state UIDs: 144 (not hit truth).

## Attribution
- **H1 late-only bias — SUPPORTED at the software-path level / outcome UNRESOLVED:** experiment actions show real earlier amendments, while baseline shows none. This demonstrates the switch changes stale-deadline handling; absent game grades, it cannot prove fewer SLOW results.
- **H2 amendment oscillation — POSSIBLE:** reversal rows are listed below. A large reversal count or near-zero net shift means the extra amendments may be noise rather than a stable correction.
- **H3 fixed 60ms / geometry — UNRESOLVED:** both runs share 60ms and the same geometry hash; the A/B cannot validate the anchor or hit line.
- **H4 execution delay — SUPPORTED as a small software offset only:** the prior baseline key-down/final-deadline median was about 2ms; this is not a game FAST/SLOW label.

## High-oscillation examples
- experiment `d04061fe0afa:simple:1000133`: earlier=11, later=12, reversals=18, net=-43.86877454817295ms, final=NOT_SCHEDULED.
- experiment `d04061fe0afa:simple:1000234`: earlier=11, later=13, reversals=17, net=-39.15562911424786ms, final=FIRED.
- experiment `d04061fe0afa:simple:1000235`: earlier=12, later=11, reversals=16, net=-23.12910632463172ms, final=FIRED.
- experiment `d04061fe0afa:simple:1000151`: earlier=11, later=12, reversals=15, net=-12.836195499403402ms, final=FIRED.
- experiment `d04061fe0afa:simple:1000267`: earlier=12, later=13, reversals=15, net=-19.48681948124431ms, final=NOT_SCHEDULED.
- experiment `d04061fe0afa:simple:1000226`: earlier=10, later=11, reversals=15, net=-34.26709939958528ms, final=NOT_SCHEDULED.
- experiment `d04061fe0afa:simple:1000233`: earlier=8, later=15, reversals=14, net=-14.754808915313333ms, final=FIRED.
- experiment `d04061fe0afa:simple:1000154`: earlier=9, later=15, reversals=13, net=-15.034806216135621ms, final=FIRED.
- experiment `d04061fe0afa:simple:1000012`: earlier=9, later=12, reversals=13, net=-19.54847775050439ms, final=NOT_SCHEDULED.
- experiment `d04061fe0afa:simple:1000129`: earlier=14, later=7, reversals=13, net=-51.01914660190232ms, final=FIRED.

## No-input / counterexamples
- baseline `ece191a2844c:simple:1000092`: amendments=0, net=0.0ms, reason flags hold/conflict=False.

## Conclusion
B's internal path is measurably different and consistent with the user's subjective improvement, but no quantitative game improvement can be claimed until at least 30 one-to-one Tap grades per group are manually confirmed. Keep `tap-earlier` opt-in and retain `stable` as the immediate rollback.
