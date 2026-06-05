# Research Direction

## Research Problem
This gym studies global localization in forest-like LiDAR scenes represented by stable object-level tree inventories. The research question is how to retrieve correct places and estimate accurate relative poses when the environment is repetitive, partially observed, and subject to viewpoint variation.

## Core Contribution
The paper's contribution is geometry-based forest localization from compact tree attributes. Improvements should remain in this family: using persistent tree-level structure and inter-object geometry to solve retrieval and pose estimation without relying on dense point cloud maps.

## Approach Scope
Scientist agents may change descriptors, hashing, matching, robust estimation, candidate ranking, filtering thresholds, or geometric verification as long as the method operates on the provided tree-inventory scene representation and solves the same retrieval-plus-pose task.

## Out of Bounds
Using ground-truth poses to rank or align scenes is out of bounds. Replacing the benchmark with dense point cloud registration, image-based localization, or a supervised model trained on labels from this test split is out of bounds because it sidesteps the paper's compact tree-geometry thesis.
