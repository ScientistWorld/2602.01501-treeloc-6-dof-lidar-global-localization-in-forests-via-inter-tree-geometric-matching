# Verification Report

## Initial Assessment

The workspace previously reached `core_claim` on a scaled tree-inventory benchmark, then a fidelity audit temporarily lowered the milestone while centroid-correspondence verification and stricter artifact validation were tested. Job `8db7236c-81e` regenerated current artifacts for the KNN-simplex descriptor plus centroid-correspondence verifier and passed both validators.

## Issues Found

- Critical, fixed: CPU validation job `ed4315b9-640` produced current artifacts for the centroid-correspondence verifier, but `python validate.py --post-reproducer` failed because TreeLoc R@50 was 0.589 while the paper reference is 0.970. The descriptor stage was then patched to match the public TreeLoc local-KNN simplex construction more closely, and job `8db7236c-81e` passed the strict validator.
- Minor, fixed: generated job logs and raw trajectory traces were tracked in git despite being ignored execution artifacts.

## Fixes Applied

- Confirmed `python validate.py --compare` and `python validate.py --post-reproducer` pass on regenerated artifacts from job `8db7236c-81e`.
- Confirmed static gym checks: no committed `shared/` references, `eval/` and `data/` do not import from `method/`, `scripts/download.sh` has no external URLs or shared-cache dependencies, train/test evaluators are present and method-independent, and method-agnostic documentation does not reveal implementation details.
- Removed temporary upstream-reference files from `tmp/`.
- Replaced the stale verification report with this current report.
- Patched `method/treeloc.py` to use local-KNN simplex construction, edge-based canonical triangle ordering, and deterministic centroid-correspondence ordering, matching the public TreeLoc descriptor stage more closely.
- Removed tracked `jobs/` logs and `trajectory/session.json` from git tracking; they remain ignored execution artifacts.
- Updated `MILESTONES.md`, `PROGRESS.md`, and `action.yaml` to reflect restored `core_claim`.

## Final Judgment

The workspace is ready to serve as a research gym for the scaled TreeLoc problem. The method is a real implementation of the paper's tree-geometry pipeline rather than a surrogate; evaluation is independent from `method/`; scoring includes both benefit and constraint-style localization metrics; and the reproduced method clearly outperforms TDH-only and no-alignment checks on the formal benchmark. From-scratch agents can use the method-agnostic problem/evaluation/data files without seeing the paper method, while improve-mode agents have the reproduced method and current scores.

- Milestone: core_claim
- Ready for gym use: yes
- Confidence: medium
- Key limitation: scaled synthetic tree-inventory benchmark rather than the full original robotics datasets.
