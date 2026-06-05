# Verification Report

## Initial Assessment

The workspace previously reached `core_claim` on a scaled tree-inventory benchmark, with passing validators and reproduced TreeLoc-style localization results. A later fidelity patch changed geometric verification to the paper/upstream centroid-correspondence initial alignment, so job `ed4315b9-640` regenerated current artifacts. That job confirmed the method runs end to end, but the strict post-reproducer check rejected the remaining primary-metric gap to the paper reference.

## Issues Found

- Critical: CPU validation job `ed4315b9-640` produced current artifacts for the centroid-correspondence verifier, but `python validate.py --post-reproducer` failed because TreeLoc R@50 was 0.589 while the paper reference is 0.970. The workspace should not be signed off at `core_claim` until this fidelity/performance gap is fixed or the reference is shown to be mis-transcribed.
- Minor: the prior verification report still stated `core_claim` and ready-for-gym status, which conflicted with `MILESTONES.md` and `action.yaml`.

## Fixes Applied

- Confirmed `python validate.py --compare` passes structurally on regenerated artifacts and that `python validate.py --post-reproducer` is correctly blocking the current primary-metric gap.
- Confirmed static gym checks: no committed `shared/` references, `eval/` and `data/` do not import from `method/`, `scripts/download.sh` has no external URLs or shared-cache dependencies, train/test evaluators are present and method-independent, and method-agnostic documentation does not reveal implementation details.
- Removed temporary upstream-reference files from `tmp/`.
- Replaced the stale verification report with this current report.
- Patched `method/treeloc.py` to use local-KNN simplex construction, edge-based canonical triangle ordering, and deterministic centroid-correspondence ordering, matching the public TreeLoc descriptor stage more closely.
- Left `action.yaml` set to submit a CPU test job that runs `scripts/run.sh`, regenerates artifacts and train/test/formal scores, and executes both validators.

## Final Judgment

Final approval is pending the CPU validation job because the KNN-simplex descriptor patch has not yet produced current scores. The workspace structure and scoring design are otherwise ready for gym use. If the pending job restores the previous localization gap over the TDH-only and no-alignment baselines and passes validators, the appropriate milestone is `core_claim`.

- Milestone: method_runs
- Ready for gym use: partial
- Confidence: medium
- Key limitation: scaled synthetic tree-inventory benchmark rather than the full original robotics datasets; current KNN-simplex descriptor scores are pending validation.
