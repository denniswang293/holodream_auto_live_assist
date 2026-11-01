# V7.8.7 parity root cause

Frame 385 and 546 replay-extra edges are preserved as `TRACE_SEMANTICS`: the candidate exists in `live_candidate_trace.csv`, but no corresponding candidate assignment attempt row exists in the retained Live trace. The live assignment rows also contain exact pair/assignment duplicates (3308 raw vs 1654 semantic). No replay edge was deleted and parity remains PARTIAL. Complete serialized Tracker/PF state is still missing, so UID lifecycle cannot be upgraded to PASS.
