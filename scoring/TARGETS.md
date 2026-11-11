# Evaluation Targets

All targets are scored by `bash scripts/evaluate_test.sh` (hidden test, `scoring/scores_test.json`) and can be developed against with `bash scripts/evaluate_train.sh` (`scoring/scores_train.json`). Every metric below appears under each experiment's `results` in both files.

## Primary: intra_session_localization (weight 0.6)
Place recognition and 6-DoF localization for revisits within one forest traversal (hidden test: Oxford Stein am Rhein).
- **Benefit metrics**: `R_at_50` (primary), `R_at_1`, `F1`, `AUC`, `SR` — higher is better.
- **Constraint metrics**: `TE_m`, `RE_deg` (errors of correct, successful poses) and `TE_all_m`, `RE_all_deg` (errors over all queries) — lower is better.

## Primary: inter_session_localization (weight 0.4)
Place recognition and 6-DoF localization across sessions ~6 months apart (hidden test: Wild-Places Venman official test regions).
- **Benefit metrics**: `R_at_1` (primary), `F1`, `AUC`, `R_at_50`, `SR` — higher is better.
- **Constraint metrics**: `TE_m`, `RE_deg`, `TE_all_m`, `RE_all_deg` — lower is better.

## Ablation / baseline targets
Scored in the same files under their own method keys:
- `treeloc_no_alignment`: the reference method without its tree-axis roll/pitch correction (paper Table V, "no alignment"); expected below the reference, most strongly on `R_at_50`.
- `tdh_baseline`: global-descriptor-only retrieval with an identity pose; expected far below the reference on every localization metric.
