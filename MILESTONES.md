# Reproduction Milestones

**Current: method_runs**

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

## Stop Justification
- Not stopped. First compute-container run is pending.
