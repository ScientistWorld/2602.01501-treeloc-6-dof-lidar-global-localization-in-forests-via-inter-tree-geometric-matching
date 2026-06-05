#!/usr/bin/env python3
"""TreeLoc reproduction on tree-inventory scenes."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def skew(v: np.ndarray) -> np.ndarray:
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]], dtype=float)


def rotation_align_to_z(axes: np.ndarray) -> np.ndarray:
    if len(axes) == 0:
        return np.eye(3)
    oriented = axes.copy()
    oriented[oriented[:, 2] < 0] *= -1.0
    # Robust analogue of Eq. (3): choose the dominant stem direction by
    # RANSAC-style inlier support, then solve the least-squares mean direction
    # over that consensus set before aligning it to z.
    best_inliers = np.arange(len(oriented))
    best_count = -1
    cos_tol = math.cos(math.radians(6.0))
    for candidate in oriented:
        candidate = candidate / (np.linalg.norm(candidate) + 1e-12)
        support = np.flatnonzero(np.abs(oriented @ candidate) >= cos_tol)
        if len(support) > best_count:
            best_count = len(support)
            best_inliers = support
    a = np.mean(oriented[best_inliers], axis=0)
    a = a / (np.linalg.norm(a) + 1e-12)
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(a, z)
    s = np.linalg.norm(v)
    c = float(np.dot(a, z))
    if s < 1e-10:
        return np.eye(3)
    k = skew(v / s)
    return np.eye(3) + k * s + (k @ k) * (1.0 - c)


def se2_align(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(src) == 0:
        return np.eye(2), np.zeros(2)
    src_mean = src.mean(axis=0)
    dst_mean = dst.mean(axis=0)
    xs = src - src_mean
    xd = dst - dst_mean
    u, _, vt = np.linalg.svd(xs.T @ xd)
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    t = dst_mean - r @ src_mean
    return r, t


def yaw_from_r2(r: np.ndarray) -> float:
    return math.atan2(r[1, 0], r[0, 0])


def pose_inv(t: np.ndarray) -> np.ndarray:
    out = np.eye(4)
    out[:3, :3] = t[:3, :3].T
    out[:3, 3] = -out[:3, :3] @ t[:3, 3]
    return out


@dataclass
class SceneDesc:
    name: str
    pose: np.ndarray
    align: np.ndarray
    centers: np.ndarray
    heights: np.ndarray
    dbh: np.ndarray
    tdh: np.ndarray
    triangles: dict[int, list[tuple[np.ndarray, tuple[int, int, int]]]]


def tdh_descriptor(centers: np.ndarray, dbh: np.ndarray, use_dbh: bool = True) -> np.ndarray:
    n_spatial, n_dbh = 5, 8
    hist = np.zeros((n_spatial, n_dbh), dtype=float)
    if len(centers) == 0:
        return hist.ravel()
    spatial_bins = [(0.0, 7.0), (5.0, 13.0), (11.0, 19.0), (17.0, 25.0), (23.0, 30.0)]
    if use_dbh:
        dbh_step = (0.80 - 0.0) / (n_dbh + 1)
        dbh_bins = [(i * dbh_step, i * dbh_step + 0.15) for i in range(n_dbh - 1)]
        dbh_bins.append((dbh_bins[-1][0] + dbh_step, math.inf))
    else:
        dbh_bins = [(0.0, math.inf)]
    distances = np.linalg.norm(centers[:, :2], axis=1)
    for dist, diameter in zip(distances, dbh):
        rbins = [i for i, (lo, hi) in enumerate(spatial_bins) if lo < dist <= hi or (i == 0 and dist == 0.0)]
        dbins = [i for i, (lo, hi) in enumerate(dbh_bins) if lo < diameter <= hi or (i == 0 and diameter == 0.0)]
        for rb in rbins:
            for db in dbins:
                hist[rb, db] += 1.0
    smooth = np.zeros_like(hist)
    for i in range(n_spatial):
        for j in range(n_dbh):
            smooth[i, j] = hist[i : min(i + 2, n_spatial), j : min(j + 2, n_dbh)].sum()
    return smooth.ravel()


def triangle_hash(sides: np.ndarray, area: float, delta_l: float = 0.1, rho: int = 100007, modulus: int = 50000000) -> int:
    ell_1, ell_2, ell_3 = (int(round(float(x) / delta_l)) for x in sorted(sides))
    value = (ell_3 * rho + ell_2) % modulus
    value = (value * rho + ell_1) % modulus
    value = (value * rho + int(round(area / delta_l))) % modulus
    return value


def triangle_descriptors(centers: np.ndarray, min_side: float = 2.0, max_side: float = 30.0) -> dict:
    table: dict[int, list[tuple[np.ndarray, tuple[int, int, int]]]] = defaultdict(list)
    if len(centers) < 3:
        return table
    for i, j, k in itertools.combinations(range(len(centers)), 3):
        pts = centers[[i, j, k], :2]
        sides = np.array(
            [np.linalg.norm(pts[0] - pts[1]), np.linalg.norm(pts[1] - pts[2]), np.linalg.norm(pts[0] - pts[2])]
        )
        if np.min(sides) < min_side or np.max(sides) > max_side:
            continue
        semi = float(np.sum(sides) / 2.0)
        area = math.sqrt(max(semi * (semi - sides[0]) * (semi - sides[1]) * (semi - sides[2]), 0.0))
        key = triangle_hash(sides, area)
        table[key].append((pts.mean(axis=0), (i, j, k)))
    return table


def make_scene(raw: dict, use_alignment: bool = True, use_dbh: bool = True) -> SceneDesc:
    positions = np.array([t["position"] for t in raw["trees"]], dtype=float)
    axes = np.array([t["axis"] for t in raw["trees"]], dtype=float)
    dbh = np.array([t["dbh"] for t in raw["trees"]], dtype=float)
    align = rotation_align_to_z(axes) if use_alignment else np.eye(3)
    aligned = (align @ positions.T).T if len(positions) else np.zeros((0, 3))
    centers = aligned[:, :2] if len(aligned) else np.zeros((0, 2))
    heights = aligned[:, 2] if len(aligned) else np.zeros(0)
    return SceneDesc(
        name=raw["name"],
        pose=np.array(raw["pose"], dtype=float),
        align=align,
        centers=centers,
        heights=heights,
        dbh=dbh,
        tdh=tdh_descriptor(centers, dbh, use_dbh=use_dbh),
        triangles=triangle_descriptors(centers),
    )


def chi_square(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sum((a - b) ** 2 / (a + b + 1e-10)))


def fine_score(a: SceneDesc, b: SceneDesc) -> float:
    cand_keys = set(b.triangles.keys())
    return float(sum(1 for key in a.triangles.keys() if key in cand_keys))


def count_support(query: SceneDesc, cand: SceneDesc, r: np.ndarray, t: np.ndarray) -> list[tuple[int, int]]:
    transformed = (r @ query.centers.T).T + t
    pairs = []
    for qi, p in enumerate(transformed):
        dists = np.linalg.norm(cand.centers - p, axis=1)
        if len(dists) == 0:
            continue
        ci = int(np.argmin(dists))
        if dists[ci] <= 0.40 and abs(query.dbh[qi] - cand.dbh[ci]) <= 0.20:
            pairs.append((qi, ci))
    return pairs


def ransac_vertical_offset(query: SceneDesc, cand: SceneDesc, pairs: list[tuple[int, int]]) -> float:
    if not pairs:
        return 0.0
    offsets = np.array([cand.heights[ci] - query.heights[qi] for qi, ci in pairs], dtype=float)
    best = float(np.median(offsets))
    best_count = -1
    for candidate in offsets:
        count = int(np.sum(np.abs(offsets - candidate) <= 0.20))
        if count > best_count:
            best_count = count
            best = float(candidate)
    inliers = offsets[np.abs(offsets - best) <= 0.20]
    return float(np.median(inliers)) if len(inliers) else best


def verify(query: SceneDesc, cand: SceneDesc) -> dict:
    centroid_src = []
    centroid_dst = []
    for key in sorted(query.triangles.keys() & cand.triangles.keys()):
        q_centroid, _ = query.triangles[key][0]
        c_centroid, _ = cand.triangles[key][0]
        centroid_src.append(q_centroid)
        centroid_dst.append(c_centroid)
    if len(centroid_src) < 2:
        return {"overlap": 0.0, "translation": [0.0, 0.0, 0.0], "yaw": 0.0, "num_matches": 0}

    rc, tc = se2_align(np.array(centroid_src), np.array(centroid_dst))
    pairs = count_support(query, cand, rc, tc)

    if len(pairs) >= 2:
        src = query.centers[[p[0] for p in pairs]]
        dst = cand.centers[[p[1] for p in pairs]]
        r, t2 = se2_align(src, dst)
        pairs = count_support(query, cand, r, t2)
    else:
        r, t2 = rc, tc

    dz = ransac_vertical_offset(query, cand, pairs)
    overlap = len(pairs) / max(1, len(query.centers) + len(cand.centers) - len(pairs))
    r4 = np.eye(3)
    r4[:2, :2] = r
    t4 = np.array([float(t2[0]), float(t2[1]), dz])
    # Paper Eq. final composition: undo candidate axis alignment, apply the
    # verified 4-DoF transform, then apply query axis alignment.
    final_r = cand.align.T @ r4 @ query.align
    final_t = cand.align.T @ t4
    return {
        "overlap": float(overlap),
        "translation": final_t.tolist(),
        "yaw": yaw_from_r2(final_r[:2, :2]),
        "rotation": final_r.tolist(),
        "num_matches": len(pairs),
    }


def run_treeloc(data: dict, top_tdh: int, top_fine: int, use_alignment: bool, use_dbh: bool) -> dict:
    db = [make_scene(s, use_alignment=use_alignment, use_dbh=use_dbh) for s in data["database"]]
    queries = [make_scene(s, use_alignment=use_alignment, use_dbh=use_dbh) for s in data["query"]]
    predictions = []
    pair_scores = []
    for q in queries:
        coarse = sorted(((chi_square(q.tdh, c.tdh), c) for c in db), key=lambda x: x[0])[:top_tdh]
        fine = sorted(((fine_score(q, c), c, dist) for dist, c in coarse), key=lambda x: (-x[0], x[2]))[:top_fine]
        verified = []
        for score, cand, dist in fine:
            v = verify(q, cand)
            verified.append((v["overlap"], score, -dist, cand, v))
        verified.sort(reverse=True, key=lambda x: (x[0], x[1], x[2]))
        best_overlap, best_fine, _, best, best_v = verified[0]
        predictions.append(
            {
                "query": q.name,
                "candidate": best.name,
                "similarity": float(best_overlap + 0.01 * best_fine),
                "estimated_query_to_candidate": best_v,
            }
        )
        scored_names = {best.name}
        for score, cand, dist in fine:
            pair_scores.append({"query": q.name, "candidate": cand.name, "score": float(score - 0.02 * dist)})
            scored_names.add(cand.name)
        # Include low scores for non-retrieved candidates so PR/AUC sees negatives.
        for cand in db:
            if cand.name not in scored_names:
                pair_scores.append({"query": q.name, "candidate": cand.name, "score": -chi_square(q.tdh, cand.tdh)})
    return {"method": "treeloc", "predictions": predictions, "pair_scores": pair_scores}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/forest_scenes.json")
    parser.add_argument("--output", default="artifacts/treeloc_results.json")
    parser.add_argument("--top-tdh", type=int, default=100)
    parser.add_argument("--top-fine", type=int, default=10)
    parser.add_argument("--no-alignment", action="store_true")
    parser.add_argument("--no-dbh", action="store_true")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text())
    result = run_treeloc(data, args.top_tdh, args.top_fine, not args.no_alignment, not args.no_dbh)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
