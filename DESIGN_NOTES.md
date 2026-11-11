> **Superseded (iteration 11).** This note describes the earlier synthetic-forest gym. The gym now uses the
> authors' real tree inventories; see `HARDENING.md`, `briefing/evaluation.md` and `scoring/`.

# Train/Test Evaluation Design Notes

## Checks and Changes

- Checked `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh` side by side. The test script invokes `eval/test/evaluate.py`, writes `scoring/scores_test.json`, and preserves the train-scored method set when `scoring/scores_train.json` exists.
- Checked that both slice evaluators are method-agnostic. They read TreeLoc-format result artifacts with `predictions` and `pair_scores`; they do not import from `method/`.
- Fixed a held-out leakage pattern: the original train and test query lists were exact complementary halves of the 56-query dataset, so a future agent seeing the train IDs and full data could infer the likely test IDs. Both slices now use 24 disjoint, route-spread queries, leaving 8 unused queries so the test slice is not recoverable by complement.
- Added the required `description` field to every active metric in `scoring/reference.json`. The metrics continue to score the scientific localization quantities directly, not agreement with the paper's published numbers.
- Confirmed by grep that there are no paper-agreement metric names such as `deviation_from_paper`, `reproduction_error`, or `fit_to_published`, and no hardcoded `METHOD_NAME` default in the train/test scripts.
- Confirmed `scoring/scores_train.json` and `scoring/scores_test.json` are absent.
- Ran `bash -n scripts/evaluate_train.sh` and `bash -n scripts/evaluate_test.sh`; both passed.

## Runtime Concerns for the Next Iteration

- The train/test split is still built from one small synthetic forest sequence. The non-complement split reduces direct ID leakage, but runtime results should be checked for saturation across `R_at_1`, `R_at_50`, and `SR`; all-1.0 or all-0.0 scores would weaken the anti-shortcut signal.
- `eval/test/` intentionally re-scores existing artifacts rather than rerunning methods. The next runner should verify that every future method artifact contains complete `predictions` and all query/database `pair_scores`, since the evaluator now fails closed on incomplete artifacts.
- The held-out test currently probes the same metric family as train. If future results show small train/test gaps for visibly overfit methods, add a second hidden scoring angle, such as stricter pose thresholds or a rank-specific localization metric, while keeping the method artifact interface unchanged.
