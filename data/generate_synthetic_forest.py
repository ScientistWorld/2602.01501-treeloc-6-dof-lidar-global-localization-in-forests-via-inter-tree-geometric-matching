#!/usr/bin/env python3
"""Generate a reusable tree-inventory localization benchmark.

The paper evaluates on extracted tree databases from LiDAR sequences. This
generator creates the same kind of method-agnostic input: scenes containing
per-tree local position, stem axis, base height, DBH, and ground-truth poses.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np


def rot_x(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def rot_y(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def pose_matrix(x: float, y: float, z: float, roll: float, pitch: float, yaw: float) -> np.ndarray:
    t = np.eye(4)
    t[:3, :3] = rot_z(yaw) @ rot_y(pitch) @ rot_x(roll)
    t[:3, 3] = np.array([x, y, z])
    return t


def make_forest(rng: np.random.Generator, n_trees: int = 720) -> list[dict]:
    trees = []
    for i in range(n_trees):
        x = rng.uniform(-20.0, 260.0)
        y = rng.uniform(-55.0, 55.0)
        # Mild terrain undulation gives the vertical offset estimation a real job.
        z = 0.7 * math.sin(x / 31.0) + 0.35 * math.cos(y / 17.0)
        dbh = float(np.clip(rng.normal(0.34 + 0.04 * math.sin(x / 40.0), 0.09), 0.12, 0.72))
        lean_roll = rng.normal(0.0, math.radians(2.0))
        lean_pitch = rng.normal(0.0, math.radians(2.0))
        axis = rot_y(lean_pitch) @ rot_x(lean_roll) @ np.array([0.0, 0.0, 1.0])
        trees.append({"id": i, "pos": [float(x), float(y), float(z)], "axis": axis.tolist(), "dbh": dbh})
    return trees


def scene_from_pose(
    name: str,
    pose: np.ndarray,
    trees: list[dict],
    rng: np.random.Generator,
    radius: float,
    dropout: float,
    pos_noise: float,
    dbh_noise: float,
) -> dict:
    inv_pose = np.linalg.inv(pose)
    local_trees = []
    for tree in trees:
        p_world = np.array(tree["pos"])
        p_local = (inv_pose @ np.r_[p_world, 1.0])[:3]
        if np.linalg.norm(p_local[:2]) > radius:
            continue
        if rng.random() < dropout:
            continue
        noisy_p = p_local + rng.normal(0.0, pos_noise, size=3)
        axis_local = inv_pose[:3, :3] @ np.array(tree["axis"])
        axis_local = axis_local / (np.linalg.norm(axis_local) + 1e-12)
        local_trees.append(
            {
                "id": int(tree["id"]),
                "position": noisy_p.tolist(),
                "axis": axis_local.tolist(),
                "dbh": float(max(0.05, tree["dbh"] + rng.normal(0.0, dbh_noise))),
                "base_height": float(noisy_p[2]),
            }
        )
    return {"name": name, "pose": pose.tolist(), "trees": local_trees}


def build_sequences(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    random.seed(seed)
    trees = make_forest(rng)
    database, query = [], []
    xs = np.linspace(0.0, 220.0, 56)
    for i, x in enumerate(xs):
        y = 9.0 * math.sin(x / 38.0)
        z = 0.7 * math.sin(x / 31.0) + 0.35 * math.cos(y / 17.0) + 1.0
        yaw = 0.08 * math.sin(x / 22.0)
        pose = pose_matrix(float(x), float(y), float(z), 0.0, 0.0, yaw)
        database.append(scene_from_pose(f"db_{i:03d}", pose, trees, rng, 31.0, 0.08, 0.035, 0.015))

        qx = x + rng.normal(0.0, 1.4)
        qy = y + rng.normal(0.0, 1.0)
        qz = 0.7 * math.sin(qx / 31.0) + 0.35 * math.cos(qy / 17.0) + 1.0 + rng.normal(0.0, 0.10)
        qyaw = yaw + rng.normal(0.0, math.radians(5.0))
        qroll = rng.normal(0.0, math.radians(9.0))
        qpitch = rng.normal(0.0, math.radians(7.0))
        qpose = pose_matrix(float(qx), float(qy), float(qz), float(qroll), float(qpitch), float(qyaw))
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
