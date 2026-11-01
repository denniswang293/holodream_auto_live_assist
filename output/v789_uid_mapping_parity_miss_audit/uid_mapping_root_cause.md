# UID mapping root cause

The reviewed rescue cases reuse the same `candidate_id` and source frame in the Live and offline traces, while the UID namespaces differ (`simple:1000xxx` versus `simple:5`/`simple:12`). This supports a **time-local ambiguous mapping**, not a global UID equivalence. The source run has no serialized cross-run Tracker/PF snapshot, so the audit does not claim false attach, double ownership, or a causally proven game hit.

Frame 408 (`408:candidate:0`) and frame 525 (`525:candidate:4`) are retained as explicit candidate-ownership cases. A human `SAME_PHYSICAL_NOTE` label is reported separately from software continuity and does not promote the mapping to PASS.
