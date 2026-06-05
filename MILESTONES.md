# Reproduction Milestones

**Current: method_runs**

## Progress Log

### [2026-06-05 03:50] - method_runs
- Audited the existing TreeLoc reproduction and confirmed it implements the paper's real tree-geometry localization pipeline rather than a learned or hardcoded surrogate.
- Tightened method fidelity toward the paper/upstream implementation: raw TDH chi-square, overlapping TDH bins, triangle side-plus-area hashing, common-hash fine retrieval, centroid-based planar verification, and post-refinement support recomputation.
- Replaced the synthetic forest generator's NumPy dependency with standard-library matrix math so `scripts/download.sh` works before container setup.
- Submitting a CPU validation job to regenerate artifacts and determine whether the revised implementation restores `core_claim`.

### [2026-06-05 03:53] - method_runs
- Continuation audit found the implementation and evaluation structure sound, and both `python validate.py --compare` and `python validate.py --post-reproducer` pass.
- The existing formal score artifacts predate the latest `method/treeloc.py` and `data/forest_scenes.json` edits, so `core_claim` cannot be restored from those stale numbers.
- Submitting a CPU validation job to rerun `scripts/reproduce.sh` and regenerate current artifacts/scores.

## Stop Justification
- Not stopped; validation job pending for the revised implementation.
