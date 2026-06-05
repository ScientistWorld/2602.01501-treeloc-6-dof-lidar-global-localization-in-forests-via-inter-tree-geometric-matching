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

### [2026-06-05 04:05] - core_claim
- CPU validation job `14bacc84-1a3` completed successfully with the triangle-pair consensus verifier.
- Fresh TreeLoc metrics: R@1 1.000, F1 0.629, AUC 0.653, R@50 1.000, SR 1.000, TE 0.020 m, and RE 0.167 deg.
- Auxiliary metrics show the TDH-only baseline remains much weaker on localization (R@50 0.054) and the no-alignment variant drops to R@50 0.196.
- Both `python validate.py --compare` and `python validate.py --post-reproducer` passed inside the container.

### [2026-06-05 04:34] - core_claim
- Fixed a packaging issue where `scripts/run.sh` only evaluated pre-existing ignored artifacts; it now regenerates the benchmark and all standard result artifacts before scoring.
- Added `TE_all_m` and `RE_all_deg` to the main evaluator so `scoring/scores.json` covers every formal metric in `scoring/reference.json`.
- Local `python validate.py --compare` and `python validate.py --post-reproducer` pass; submitting a CPU validation job to verify the fresh-artifact path inside the container.

### [2026-06-05 04:35] - core_claim
- Final verification found the claimed milestone justified: the TreeLoc-style geometric localization method runs end to end and beats the simple TDH-only and no-alignment checks on the scaled benchmark.
- Fixed the reusable evaluator contract so every submitted result artifact is written into `scoring/scores.json` under its own method key, rather than only scoring the reproduced method formally.
- Removed generated job logs and raw trajectory traces from git tracking, tightened method-agnostic evaluation documentation, and confirmed `python validate.py --compare` plus `python validate.py --post-reproducer` pass.

### [2026-06-05 04:41] - method_runs
- Sub-agent fidelity audit found two remaining issues: the formal evaluator did not require complete artifacts, and the verifier used matched triangle vertices instead of the paper/upstream centroid-correspondence initial alignment.
- Patched `eval/evaluate_treeloc.py` to reject incomplete predictions or pair scores.
- Patched `method/treeloc.py` to estimate the initial SE(2) transform from matched triangle centroids, then refine with tree-center support and base-height vertical offset.
- The method still executes syntactically and previous validators pass on stale artifacts, but current scores must be regenerated before `core_claim` can be restored.

### [2026-06-05 04:50] - method_runs
- CPU validation job `ed4315b9-640` regenerated current artifacts for the centroid-correspondence verifier.
- The implementation ran end to end and beat auxiliary localization checks, but TreeLoc R@50 was 0.589 against the paper reference of 0.970, so `python validate.py --post-reproducer` failed and `core_claim` remains unverified.
- Patched triangle descriptor generation to match the public TreeLoc KNN simplex construction and edge-based canonical ordering more closely.
- Submitting a CPU validation job to regenerate artifacts and scores for the KNN-simplex descriptor version.

## Stop Justification
- Pending fresh validation after the KNN-simplex descriptor fidelity patch.
