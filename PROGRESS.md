# Progress

## What Works

- Implemented a scaled TreeLoc reproduction on tree-inventory scenes: axis-based roll/pitch correction, TDH coarse retrieval, triangle-descriptor fine retrieval, and two-step geometric verification with DBH and base-height checks.
- Added a deterministic procedural forest benchmark that provides the same input abstraction used after the paper's tree extraction stage.
- Added a TDH-only baseline and a method-independent evaluator that writes `scoring/scores.json`.
- First CPU container smoke job completed successfully, so the paper's actual localization algorithm runs end to end.

## Results

- First smoke run before final 6-DoF composition fix: TreeLoc scored R@1 0.732, F1 0.715, AUC 0.765, R@50 0.125, SR 0.171, TE 0.048 m, RE 2.58 degrees.
- Second smoke run after final 6-DoF composition fix: TreeLoc scored R@1 0.732, F1 0.715, AUC 0.765, R@50 0.357, SR 0.488, TE 0.105 m, RE 0.437 degrees.
- The TDH-only baseline had strong top-1 retrieval on this simple synthetic trajectory but no pose-estimation capability, so R@50 and SR were 0. This confirmed the evaluator distinguishes retrieval-only methods from localization methods.

## Remaining

- Rerun after replacing bulk centroid alignment with bounded triangle-pair transform hypotheses and support-based verification.
- If pose success improves enough to support accurate localization, update milestone to `core_claim`.
- If results are weak, tune the synthetic benchmark noise/occlusion or matching thresholds while preserving the paper's algorithm.

## Issues

- The paper does not specify numeric values for scan aggregation `k/v/s`, TDH bin overlaps, triangle side-length quantization, or RANSAC iterations. The reproduction documents and fixes reasonable values for the scaled benchmark.
- The original public robotics datasets are large and require raw LiDAR processing/tree extraction dependencies. This first environment uses a deterministic tree-inventory substitute to validate the localization algorithm itself.
- First verifier implementation aligned all matched triangle centroids in one SVD step, which ran but produced too many false transforms. It has been replaced with per-triangle-pair hypotheses followed by tree-support verification, matching the intended geometric verification more closely.

## Deviations from Paper

- Data scale: the paper evaluates on Oxford Forest, Wild-Places, and BotanicGarden LiDAR sequences after tree reconstruction. This reproduction uses deterministic procedural tree inventories because downloading and processing the full robotics datasets plus RealtimeTrees is too large for the first smoke run. The method starts from the same per-tree attributes used by TreeLoc after extraction.
- Preprocessing scale: raw LiDAR payload aggregation and RealtimeTrees extraction are not reproduced in this first iteration. The implemented localization algorithm from tree inventories is the paper's actual TDH/triangle/geometric-verification pipeline.
- Unspecified thresholds: triangle hash quantization and some overlap details are fixed in code because the paper text does not provide numeric values.
