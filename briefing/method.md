# Paper's Method

## Key Contribution

TreeLoc is a learning-free forest localization pipeline that uses compact per-tree attributes to perform place recognition and pose estimation. Its central contribution is combining a coarse tree distribution descriptor, a fine 2D triangle descriptor, and geometric verification to recover accurate relative poses from forest structure.

## Approach

The method first reconstructs tree instances from aggregated LiDAR payloads, storing each tree's axis, stem position, base height, and diameter at breast height. It aligns each scene's tree axes to a common vertical reference to correct roll and pitch before projecting stem centers to 2D. A tree distribution histogram counts trees by radial distance and DBH for coarse retrieval. Candidate scenes are refined by hashing unordered triples of projected tree centers using sorted side lengths. Geometric verification estimates an initial planar transform from matched triangle centroids, refines it with nearest tree-center correspondences filtered by planar distance and DBH, estimates vertical offset from base heights, and composes the result with the axis-alignment rotations for 6-DoF localization.

## Main Claims

The primary claim is that stable tree-level geometry enables robust forest place recognition and accurate pose estimation without learning or dense point cloud maps. Secondary claims are that DBH, tree-axis alignment, and TDH candidate pruning each improve performance, and that the compact tree database supports efficient long-term map management and multi-session alignment.
