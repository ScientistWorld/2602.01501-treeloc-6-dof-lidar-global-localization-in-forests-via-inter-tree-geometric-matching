#!/usr/bin/env python3
"""Generate a reusable tree-inventory localization benchmark.

The paper evaluates on extracted tree databases from LiDAR sequences. This
generator creates the same kind of method-agnostic input: scenes containing
per-tree local position, stem axis, base height, DBH, and ground-truth poses.
It intentionally uses only the Python standard library so scripts/download.sh
can run before the container's Python packages are installed.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path


Matrix3 = list[list[float]]
Vector3 = list[float]


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def matmul3(a: Matrix3, b: Matrix3) -> Matrix3:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def matvec3(a: Matrix3, v: Vector3) -> Vector3:
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def transpose3(a: Matrix3) -> Matrix3:
    return [[a[j][i] for j in range(3)] for i in range(3)]


def vec_sub(a: Vector3, b: Vector3) -> Vector3:
    return [a[i] - b[i] for i in range(3)]


def norm3(v: Vector3) -> float:
    return math.sqrt(sum(x * x for x in v))


def normalize3(v: Vector3) -> Vector3:
    n = norm3(v)
    return [x / (n + 1e-12) for x in v]


def rot_x(a: float) -> Matrix3:
    c, s = math.cos(a), math.sin(a)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def rot_y(a: float) -> Matrix3:
    c, s = math.cos(a), math.sin(a)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def rot_z(a: float) -> Matrix3:
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def pose_matrix(x: float, y: float, z: float, roll: float, pitch: float, yaw: float) -> list[list[float]]:
    r = matmul3(matmul3(rot_z(yaw), rot_y(pitch)), rot_x(roll))
    return [
        [r[0][0], r[0][1], r[0][2], x],
        [r[1][0], r[1][1], r[1][2], y],
        [r[2][0], r[2][1], r[2][2], z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def pose_rotation(pose: list[list[float]]) -> Matrix3:
    return [row[:3] for row in pose[:3]]


def pose_translation(pose: list[list[float]]) -> Vector3:
    return [pose[i][3] for i in range(3)]


def linspace(start: float, stop: float, count: int) -> list[float]:
    if count == 1:
        return [start]
    step = (stop - start) / (count - 1)
    return [start + i * step for i in range(count)]


def make_forest(rng: random.Random, n_trees: int = 720) -> list[dict]:
    trees = []
    for _ in range(n_trees):
        x = rng.uniform(-20.0, 260.0)
        y = rng.uniform(-55.0, 55.0)
        z = 0.7 * math.sin(x / 31.0) + 0.35 * math.cos(y / 17.0)
        dbh = clip(rng.gauss(0.34 + 0.04 * math.sin(x / 40.0), 0.09), 0.12, 0.72)
        lean_roll = rng.gauss(0.0, math.radians(2.0))
        lean_pitch = rng.gauss(0.0, math.radians(2.0))
        axis = matvec3(matmul3(rot_y(lean_pitch), rot_x(lean_roll)), [0.0, 0.0, 1.0])
        trees.append({"pos": [x, y, z], "axis": axis, "dbh": dbh})
    return trees


def scene_from_pose(
    name: str,
    pose: list[list[float]],
    trees: list[dict],
    rng: random.Random,
    radius: float,
    dropout: float,
    pos_noise: float,
    dbh_noise: float,
) -> dict:
    r_inv = transpose3(pose_rotation(pose))
    t = pose_translation(pose)
    local_trees = []
    for tree in trees:
        p_world = tree["pos"]
        p_local = matvec3(r_inv, vec_sub(p_world, t))
        if math.hypot(p_local[0], p_local[1]) > radius:
            continue
        if rng.random() < dropout:
            continue
        noisy_p = [p_local[i] + rng.gauss(0.0, pos_noise) for i in range(3)]
        axis_local = normalize3(matvec3(r_inv, tree["axis"]))
        local_trees.append(
            {
                "position": noisy_p,
                "axis": axis_local,
                "dbh": max(0.05, tree["dbh"] + rng.gauss(0.0, dbh_noise)),
                "base_height": noisy_p[2],
            }
        )
    return {"name": name, "pose": pose, "trees": local_trees}


def build_sequences(seed: int) -> dict:
    rng = random.Random(seed)
    trees = make_forest(rng)
    database, query = [], []
    for i, x in enumerate(linspace(0.0, 220.0, 56)):
        y = 9.0 * math.sin(x / 38.0)
        z = 0.7 * math.sin(x / 31.0) + 0.35 * math.cos(y / 17.0) + 1.0
        yaw = 0.08 * math.sin(x / 22.0)
        pose = pose_matrix(x, y, z, 0.0, 0.0, yaw)
        database.append(scene_from_pose(f"db_{i:03d}", pose, trees, rng, 31.0, 0.08, 0.035, 0.015))

        qx = x + rng.gauss(0.0, 1.4)
        qy = y + rng.gauss(0.0, 1.0)
        qz = 0.7 * math.sin(qx / 31.0) + 0.35 * math.cos(qy / 17.0) + 1.0 + rng.gauss(0.0, 0.10)
        qyaw = yaw + rng.gauss(0.0, math.radians(5.0))
        qroll = rng.gauss(0.0, math.radians(5.0))
        qpitch = rng.gauss(0.0, math.radians(4.0))
        qpose = pose_matrix(qx, qy, qz, qroll, qpitch, qyaw)
        query.append(scene_from_pose(f"query_{i:03d}", qpose, trees, rng, 31.0, 0.22, 0.06, 0.025))

    return {
        "description": "Procedural forest tree-inventory scenes for TreeLoc reproduction.",
        "positive_distance_m": 10.0,
        "localization_translation_threshold_m": 0.5,
        "localization_rotation_threshold_deg": 5.0,
        "database": database,
        "query": query,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/forest_scenes.json")
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    payload = build_sequences(args.seed)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"wrote {out} with {len(payload['query'])} queries and {len(payload['database'])} database scenes")


if __name__ == "__main__":
    main()
