# Verification Report

## Initial Assessment

The workspace previously reached `core_claim` on a scaled tree-inventory benchmark, with passing validators and reproduced TreeLoc-style localization results. At the start of this verification pass, however, `method/treeloc.py` and `eval/evaluate_treeloc.py` were newer than `artifacts/treeloc_results.json` and `scoring/scores.json`. The current formal scores therefore come from the pre-patch verifier and cannot certify the latest method implementation.

## Issues Found

- Critical: current score artifacts are stale relative to the latest method/evaluator patch. The latest code changed geometric verification to the paper/upstream centroid-correspondence initial alignment and tightened formal artifact validation, so `core_claim` must be revalidated by regenerating artifacts.
- Minor: the prior verification report still stated `core_claim` and ready-for-gym status, which conflicted with `MILESTONES.md` and `action.yaml`.

## Fixes Applied

- Confirmed `python validate.py --compare` and `python validate.py --post-reproducer` pass structurally, but only against stale artifacts.
- Confirmed static gym checks: no committed `shared/` references, `eval/` and `data/` do not import from `method/`, `scripts/download.sh` has no external URLs or shared-cache dependencies, train/test evaluators are present and method-independent, and method-agnostic documentation does not reveal implementation details.
- Removed temporary upstream-reference files from `tmp/`.
- Replaced the stale verification report with this current report.
- Left `action.yaml` set to submit a CPU test job that runs `scripts/run.sh`, regenerates artifacts and train/test/formal scores, and executes both validators.

## Final Judgment

Final approval is pending the CPU validation job because the latest method code has not yet produced current scores. The workspace structure and scoring design are otherwise ready for gym use. If the pending job restores the previous localization gap over the TDH-only and no-alignment baselines and passes validators, the appropriate milestone is `core_claim`.

- Milestone: method_runs
- Ready for gym use: partial
- Confidence: medium
- Key limitation: scaled synthetic tree-inventory benchmark rather than the full original robotics datasets; current scores are stale after the centroid-verification patch.
