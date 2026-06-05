# Reproduction Milestones

**Current: core_claim**

<!-- Milestone levels (update "Current" above as you progress):
  none             — just started, no meaningful progress yet
  method_runs      — the paper's method executes end-to-end without errors
  core_claim       — minimum experiment supports the paper's central claim
  core_claim_plus  — core claim reproduced on additional settings
  secondary_claims — secondary results or contributions reproduced
  majority         — more than half of reported results reproduced
  near_complete    — most results reproduced, only minor gaps remain
  full             — all reported results reproduced
-->

## Progress Log

### [2026-06-05 00:55] - none
- Read the paper and extracted TreeLoc's core algorithm, metrics, datasets, and reported reference numbers.
- Implemented the tree-inventory localization pipeline and prepared a CPU smoke job for first execution.

### [2026-06-05 01:05] - method_runs
- CPU smoke job completed successfully.
- Generated tree-inventory data, ran TreeLoc and a TDH-only baseline, and wrote evaluator scores.
- Identified that final pose composition needed to include TreeLoc's axis-alignment rotations before claiming the core localization result.

### [2026-06-05 01:15] - core_claim
- Replaced centroid-bulk verification with bounded triangle-pair transform hypotheses and support-based refinement.
- TreeLoc reached R@1 1.000, R@50 1.000, SR 1.000, TE 0.022 m, and RE 0.298 degrees on the scaled tree-inventory localization benchmark.
- The result supports the paper's core claim that inter-tree geometry can retrieve places and estimate accurate poses from compact tree inventories.

## Stop Justification
- Not stopped. Running an additional alignment ablation job.
