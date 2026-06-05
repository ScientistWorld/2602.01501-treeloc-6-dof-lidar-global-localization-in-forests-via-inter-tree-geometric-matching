# Evaluation Targets

## Primary: synthetic_forest_localization
Tests whether a method can retrieve correct forest scene matches and estimate usable relative poses on the benchmark tree-inventory scenes.
- **Metrics**: `R_at_1`, `F1`, `AUC`, `R_at_50`, and `SR` are higher-is-better.
- **Run**: `bash scripts/evaluate.sh` after writing result artifacts in the expected format.

## Constraint: synthetic_forest_localization
Tests whether retrieval gains preserve precise pose estimates rather than returning broad or geometrically inconsistent matches.
- **Metrics**: `TE_m` and `RE_deg` are lower-is-better.
- **Run**: `bash scripts/evaluate.sh` after writing result artifacts in the expected format.

## Ablation: synthetic_alignment_ablation
Tests whether correcting viewpoint-induced roll and pitch improves forest place recognition and localization.
- **Metrics**: `R_at_1`, `F1`, and `R_at_50` are higher-is-better.
- **Run**: `bash scripts/evaluate.sh` after writing both full and no-alignment result artifacts.
