# Frame 385/546 parity investigation

Both replay-extra edges are reproducible from the retained candidate stream: a `candidate_final` exists, but the retained Live association-attempt trace has zero rows for the same candidate. The raw Live trace also has duplicate pair/assignment rows (3308 raw versus 1654 unique semantic edges). This is evidence of a trace-semantic/write-point difference, not enough evidence to call an algorithmic false assignment.

Missing serialized Tracker/PF state prevents reconstructing the exact live tie-break, update order, and posterior at the first divergence. Therefore parity remains `PARTIAL_SOURCE_INSUFFICIENT`; the two edges remain visible.
