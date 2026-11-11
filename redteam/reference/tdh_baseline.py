#!/usr/bin/env python3
"""Simple TDH-only baseline for the tree localization benchmark."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def skew(v: np.ndarray) -> np.ndarray:
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], dtype=float)


def rotation_align_to_z(axes: np.ndarray) -> np.ndarray:
    if len(axes) == 0:
        return np.eye(3)
    oriented = axes.copy()
    oriented[oriented[:, 2] < 0] *= -1.0
    a = np.median(oriented, axis=0)
    a = a / (np.linalg.norm(a) + 1e-12)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(a, z)
    s = np.linalg.norm(v)
    c = float(np.dot(a, z))
    if s < 1e-10:
        return np.eye(3)
    k = skew(v / s)
    return np.eye(3) + k * s + (k @ k) * (1.0 - c)


def tdh_descriptor(centers: np.ndarray, dbh: np.ndarray) -> np.ndarray:
    hist = np.zeros((5, 8), dtype=float)
    if len(centers) == 0:
        return hist.ravel()
    for dist, diameter in zip(np.linalg.norm(centers[:, :2], axis=1), dbh):
        rb = min(4, max(0, int(dist // 6.0)))
        db = min(7, max(0, int((diameter - 0.10) / ((0.75 - 0.10) / 8))))
        hist[rb, db] += 1.0
    padded = np.pad(hist, ((1, 1), (1, 1)), mode="edge")
    smooth = np.zeros_like(hist)
    for i in range(5):
        for j in range(8):
            smooth[i, j] = padded[i : i + 2, j : j + 2].mean()
    norm = np.linalg.norm(smooth)
    return (smooth / norm if norm > 0 else smooth).ravel()


def chi_square(a: np.ndarray, b: np.ndarray) -> float:
    return float(0.5 * np.sum((a - b) ** 2 / (a + b + 1e-9)))


def make_scene(raw: dict) -> SimpleNamespace:
    positions = np.array([t["position"] for t in raw["trees"]], dtype=float)
    axes = np.array([t["axis"] for t in raw["trees"]], dtype=float)
    dbh = np.array([t["dbh"] for t in raw["trees"]], dtype=float)
    align = rotation_align_to_z(axes)
    aligned = (align @ positions.T).T if len(positions) else np.zeros((0, 3))
    centers = aligned[:, :2] if len(aligned) else np.zeros((0, 2))
    return SimpleNamespace(name=raw["name"], tdh=tdh_descriptor(centers, dbh))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/forest_scenes.json")
    parser.add_argument("--output", default="artifacts/tdh_baseline_results.json")
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text())
    db = [make_scene(s) for s in data["database"]]
    queries = [make_scene(s) for s in data["query"]]
    predictions, pair_scores = [], []
    for q in queries:
        ranked = sorted(((-chi_square(q.tdh, c.tdh), c) for c in db), key=lambda x: -x[0])
        best_score, best = ranked[0]
        predictions.append(
            {
                "query": q.name,
                "candidate": best.name,
                "similarity": float(best_score),
                "estimated_query_to_candidate": {
                    "overlap": 0.0,
                    "translation": [0.0, 0.0, 0.0],
                    "yaw": 0.0,
                    "num_matches": 0,
                },
            }
        )
        for score, cand in ranked:
            pair_scores.append({"query": q.name, "candidate": cand.name, "score": float(score)})
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"method": "tdh_baseline", "predictions": predictions, "pair_scores": pair_scores}, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
