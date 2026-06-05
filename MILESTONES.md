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

### [2026-06-05 03:57] - method_runs
- CPU validation job `d38f1f38-8fc` completed successfully inside the container.
- Fresh TreeLoc metrics on the scaled tree-inventory benchmark: R@1 0.750, F1 0.629, AUC 0.653, R@50 0.554, SR 0.738, TE 0.119 m, and RE 0.475 deg.
- Auxiliary sanity metrics show TDH-only baseline R@50 0.054 and no-alignment TreeLoc R@50 0.107, so geometric verification and axis alignment provide the claimed localization benefit.
- `python validate.py --compare` passed, but `python validate.py --post-reproducer` rejected the R@50 gap against the paper's Oxford score, so `core_claim` is not restored yet.

### [2026-06-05 04:02] - method_runs
- Patched geometric verification to generate SE(2) hypotheses from matched triangle pairs with all vertex permutations, then select and refine the transform by tree-support consensus.
- Submitting another CPU validation job to test whether the more faithful TreeLoc verification closes the primary localization gap.

## Stop Justification
- Not stopped; the post-reproducer validator requires a smaller primary-metric gap, and a verifier fix is pending validation.
