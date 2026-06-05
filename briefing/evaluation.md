# Evaluation

## Metrics

Place recognition is measured with Recall@1, maximum F1 over score thresholds, and AUC/average precision using a 10 m ground-truth proximity threshold. Localization is measured with R@50, the fraction of queries whose estimated pose has translation error at most 0.5 m and rotation error at most 5 degrees. Success rate is the fraction of top-ranked true positives that also satisfy the R@50 pose thresholds. Translation error and rotation error are averaged over successful localizations; lower is better.

## Baselines and Targets

The paper compares against global descriptors, local descriptors, and learning-based place recognition methods. The reference target used in this gym is the paper's Oxford Stein setting: TreeLoc reports R@1 0.871, F1 0.945, AUC 0.988, R@50 0.970, SR 0.987, TE 0.053 m, and RE 0.137 degrees. BTC is the local-descriptor baseline reference with R@1 0.611, F1 0.774, AUC 0.803, R@50 0.638, SR 0.780, TE 0.225 m, and RE 0.641 degrees.

## Evaluation Protocol

For this scaled reproduction, the evaluator reads a fixed tree-inventory dataset from `data/forest_scenes.json` and method outputs from `artifacts/*.json`. It computes all metrics without importing method code. The benchmark contains query and database scenes with known global poses; a retrieved pair is positive when the two scene origins are within 10 m. The output format is reusable: each method writes top predictions and pairwise retrieval scores, then `scripts/evaluate.sh` writes `scoring/scores.json`.
