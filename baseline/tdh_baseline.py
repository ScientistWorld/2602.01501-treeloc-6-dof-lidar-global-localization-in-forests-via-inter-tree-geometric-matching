#!/usr/bin/env python3
"""Global-descriptor-only baseline: retrieve the database frame with the closest
tree distribution histogram (TDH) and report an identity relative pose.

This is the coarse retrieval stage alone, without triangle matching or geometric
verification (no pose estimation). It is self-contained (no method/ imports).

Usage: python baseline/tdh_baseline.py --input in.json --output out.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

SPATIAL_BINS = [(0.0, 7.0), (5.0, 13.0), (11.0, 19.0), (17.0, 25.0), (23.0, 30.0)]
_STEP = 0.8 / 9
DBH_BINS = [(i * _STEP, i * _STEP + 0.15) for i in range(7)] + [(7 * _STEP, math.inf)]


def aligned_trees(frame: dict, f: dict) -> tuple[np.ndarray, np.ndarray]:
    rows = [
        (t[f["x"]], t[f["y"]], t[f["z"]], t[f["axis_x"]], t[f["axis_y"]], t[f["axis_z"]],
         t[f["dbh"]] if t[f["dbh"]] is not None else t[f["dbh_approximation"]], t[f["reconstructed"]])
        for t in frame["trees"]
        if abs(t[f["x"]]) <= 30.0 and abs(t[f["y"]]) <= 30.0
    ]
    arr = np.array(rows, dtype=float).reshape(-1, 8)
    rec = arr[arr[:, 7] == 1]
    if len(rec) == 0:
        return np.zeros((0, 2)), np.zeros(0)
    a = rec[:, 3:6].mean(axis=0)
    a = a / (np.linalg.norm(a) + 1e-12)
    if a[2] < 0:
        a = -a
    v = np.cross(a, [0.0, 0.0, 1.0])
    c = float(a[2])
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    r = np.eye(3) + vx + vx @ vx / (1.0 + c)
    pos = rec[:, 0:3] @ r.T
    return pos[:, :2], rec[:, 6]


def tdh(centers: np.ndarray, dbh: np.ndarray) -> np.ndarray:
    hist = np.zeros((5, 8))
    for (x, y), d in zip(centers, dbh):
        r = math.hypot(x, y)
        si = next((i for i, (lo, hi) in enumerate(SPATIAL_BINS) if lo < r <= hi), -1)
        dj = next((j for j, (lo, hi) in enumerate(DBH_BINS) if lo < d <= hi), -1)
        if si >= 0 and dj >= 0:
            hist[si, dj] += 1.0
    out = np.zeros_like(hist)
    for i in range(5):
        for j in range(8):
            out[i, j] = hist[i : i + 2, j : j + 2].sum()
    return out.ravel()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text())
    f = {name: i for i, name in enumerate(payload["tree_fields"])}
    predictions = []
    for seq in payload["sequences"]:
        db_ids = [fr["id"] for fr in seq["database"]]
        db = np.stack([tdh(*aligned_trees(fr, f)) for fr in seq["database"]])
        for fr in seq["queries"]:
            h = tdh(*aligned_trees(fr, f))
            chi = ((db - h) ** 2 / (db + h + 1e-10)).sum(axis=1)
            best = int(np.argmin(chi))
            predictions.append(
                {
                    "query": fr["id"],
                    "candidate": db_ids[best],
                    "score": float(-chi[best]),
                    "rotation": np.eye(3).tolist(),
                    "translation": [0.0, 0.0, 0.0],
                }
            )
    Path(args.output).write_text(json.dumps({"method": "tdh_baseline", "predictions": predictions}))


if __name__ == "__main__":
    main()
