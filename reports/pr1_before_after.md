# PR1 before / after

Before: Tap actions had ordinary action names, while Hold start/end semantics were harder to distinguish in the action CSV.

After: `live_key_actions.csv` and `input_actions.csv` include `lifecycle_state`. Hold rows use `HOLD_SCHEDULED`, `HOLD_DOWN`, `HOLD_TAIL_SEEN`, `HOLD_UP`, or `HOLD_REJECTED`; Tap rows use `SCHEDULED`, `FIRED`, `RELEASED`, `CANCELED`, or `REJECTED` where applicable.

No scheduler timing, input advance, Particle gate, focus check, freshness rule, or Hold safety behavior was changed.
