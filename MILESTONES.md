# Reproduction Milestones

**Current: core_claim**

## Progress Log

### [2026-06-05 02:58] - core_claim
- Verified the current workspace with `python validate.py`; scoring and structural checks pass.
- TreeLoc runs end to end on the scaled procedural tree-inventory benchmark and supports the core localization claim with R@50 1.000 versus the TDH-only baseline's lack of successful localization.

### [2026-06-05 03:20] - core_claim
- Audited the implementation against the paper's TreeLoc pipeline: axis-based scene alignment, TDH coarse retrieval, 2D triangle fine retrieval, and two-step geometric verification are implemented in `method/treeloc.py`.
- Updated the evaluator so independent baseline artifacts are included in `scoring/scores.json` when present.

## Stop Justification
- Current validated milestone is `core_claim`; higher milestones would require reproducing additional paper settings or real dataset pipelines beyond the scaled tree-inventory benchmark.
