# Baseline parity root cause

Live `assigned=true` rows contain two exact rows per semantic edge (pair trace plus assignment trace), producing 3308 raw rows but 1654 unique edges. Replay produces 1656 unique edges after the same normalization. The two replay-extra edges are preserved in `assignment_divergences.csv`; no rows were deleted or relabeled as PASS. UID lifecycle remains PARTIAL because the source trace does not expose a complete serialized tracker snapshot.
