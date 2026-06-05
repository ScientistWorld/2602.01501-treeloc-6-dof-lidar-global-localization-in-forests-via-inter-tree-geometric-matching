# Overview

- **Paper ID:** 2602.01501
- **Title:** TreeLoc: 6-DoF LiDAR Global Localization in Forests via Inter-Tree Geometric Matching
- **Domain:** Robotics / LiDAR Localization
- **TL;DR:** TreeLoc localizes forest LiDAR scenes by matching compact tree-inventory geometry instead of dense point clouds or learned descriptors.

## Short Summary

The paper addresses global localization in forests, where GPS is unreliable and LiDAR scenes are repetitive and seasonally variable. TreeLoc represents scenes as tree stems with axes, base positions, and DBH, then performs coarse-to-fine matching followed by geometric verification. The paper reports strong place recognition and centimeter-level localization on forest benchmarks, with much smaller storage than dense point cloud or descriptor-map methods.

## Key Results

- On Oxford Stein, TreeLoc reports R@1 0.871, F1 0.945, AUC 0.988, and 3-DoF R@50 0.970.
- In the same localization setting, TreeLoc reports TE 0.053 m and RE 0.137 degrees, outperforming BTC.
- The global tree database application stores tens of kilobytes per mission, far smaller than raw point clouds or BTC descriptor maps.
