# TreeLoc: 6-DoF LiDAR Global Localization in Forests via Inter-Tree Geometric Matching

<!-- scope-note -->
> [!NOTE]
> **Not a full reproduction of the paper.** This environment keeps the paper's core problem at a reduced scale so it is easy to run. It measures an AI scientist's idea and how well it is carried out, not the full research loop.

<!-- hardening-note -->
> [!NOTE]
> **Red-teamed and hardened.** A red team tried to score on this environment's hidden test without doing better research, and the environment was then fixed against the shortcuts that worked: see [`REDTEAM.md`](REDTEAM.md) and [`HARDENING.md`](HARDENING.md). The environment as it was before is kept as branch [`pre-hardening`](../../tree/pre-hardening).

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2602.01501"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2602.01501-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| **Paper ID** | [2602.01501](https://arxiv.org/abs/2602.01501) |
|:---|:---|
| **Domain** | Robotics / LiDAR Localization |
| **TL;DR** | TreeLoc localizes forest LiDAR scenes by matching compact tree-inventory geometry instead of dense point clouds or learned descriptors. |

## Summary

The paper addresses global localization in forests, where GPS is unreliable and LiDAR scenes are repetitive and seasonally variable. TreeLoc represents scenes as tree stems with axes, base positions, and DBH, then performs coarse-to-fine matching followed by geometric verification. The paper reports strong place recognition and centimeter-level localization on forest benchmarks, with much smaller storage than dense point cloud or descriptor-map methods.

## Problem

Estimate global place matches and relative 6-DoF poses for LiDAR traversals in forests. The setting is difficult because forest scans are repetitive, partially occluded, seasonally variable, and often captured where GPS is degraded.

## The paper's method

TreeLoc is a learning-free forest localization pipeline that uses compact per-tree attributes to perform place recognition and pose estimation. Its central contribution is combining a coarse tree distribution descriptor, a fine 2D triangle descriptor, and geometric verification to recover accurate relative poses from forest structure.

## Key results of the paper

- On Oxford Stein, TreeLoc reports R@1 0.871, F1 0.945, AUC 0.988, and 3-DoF R@50 0.970.
- In the same localization setting, TreeLoc reports TE 0.053 m and RE 0.137 degrees, outperforming BTC.
- The global tree database application stores tens of kilobytes per mission, far smaller than raw point clouds or BTC descriptor maps.

## Run it

```bash
pip install sciworld
sw research 2602.01501 --mode innovate --agent claude-code
sw evaluate 2602.01501
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

