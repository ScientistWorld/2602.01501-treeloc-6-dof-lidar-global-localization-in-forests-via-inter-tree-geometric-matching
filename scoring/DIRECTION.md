# Research Direction

## Research Problem
Global localization in forests from compact, object-level scene representations: recognize which mapped place a tree inventory comes from and recover the 6-DoF relative pose, within a session and across seasons, on real inventories from two forest datasets.

## Core Contribution
The paper's thesis is that stable tree-level structure (stem positions, axes, DBH, and the geometry between neighbouring trees) is enough for robust place recognition and accurate 6-DoF pose estimation, without learning and without dense point clouds. Improvements should stay in this family: better use of the tree inventory for retrieval, matching, verification, confidence estimation, and pose refinement.

## Approach Scope
Changing descriptors, hashing, candidate retrieval and ranking, geometric verification, robust estimation (including roll/pitch and height refinement), confidence scores, and their parameters is in scope, as is fitting parameters on the visible train slice. Spending more computation per query is not by itself a contribution; the paper aims for per-query latencies in the tens of milliseconds. Detailed matching (anything that estimates a transform or correspondences against a database scene) is capped at 100 database scenes per query, independent of database size (see `CONSTRAINTS.md`); whole-database steps must be cheap scoring without transform estimation.

## Out of Bounds
Reading or reconstructing hidden-test answers (anything under `eval/test/`, or the upstream trajectories / poses of these recordings), using scene poses or time order at test time, exhaustive verification (detailed matching of every query against every database scene), editing the evaluator, data or thresholds, and writing score files directly are out of bounds. Replacing the tree-inventory input with dense point clouds or images is out of scope.
