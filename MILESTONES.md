# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-06-05 02:58] - core_claim
- Verified the current workspace with `python validate.py`; scoring and structural checks pass.
- TreeLoc runs end to end on the scaled procedural tree-inventory benchmark and supports the core localization claim with R@50 1.000 versus the TDH-only baseline's lack of successful localization.

### [2026-06-05 03:20] - core_claim
- Audited the implementation against the paper's TreeLoc pipeline: axis-based scene alignment, TDH coarse retrieval, 2D triangle fine retrieval, and two-step geometric verification are implemented in `method/treeloc.py`.
- Updated the evaluator so independent baseline artifacts are included in `scoring/scores.json` when present.

### [2026-06-05 03:45] - method_runs
- Continuation audit found a real TreeLoc implementation rather than a surrogate: tree-axis alignment, TDH coarse retrieval, 2D triangle hashing, geometric verification, and 6-DoF composition are present.
- Existing `scores.json` is stale relative to the latest evaluator and ID-free dataset changes, so a CPU test job is required before restoring `core_claim`.

### [2026-06-05 04:05] - method_runs
- CPU job `c54eee6a-aab` ran the method and regenerated artifacts successfully, but failed validation because auxiliary methods appeared in `scores.json` without matching `reference.json` entries.
- Patched evaluation so reference-backed scores and auxiliary baseline sanity metrics are written separately.

## Stop Justification
- Current continuation milestone is `method_runs` pending a fresh container run of the updated pipeline.
