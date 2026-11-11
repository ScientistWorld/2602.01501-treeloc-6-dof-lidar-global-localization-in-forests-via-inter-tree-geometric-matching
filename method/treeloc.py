#!/usr/bin/env python3
"""TreeLoc: 6-DoF LiDAR global localization in forests via inter-tree geometric matching.

Re-implementation of Jung et al. (ICRA 2026, arXiv:2602.01501), following the
paper (Sec. III) and the authors' released C++ implementation
(github.com/minwoo0611/TreeLoc, ``src/matching.cpp`` / ``src/app.cpp``):

1. Tree selection: reconstructed stems inside a 60 m x 60 m box, topped up to
   30 trees with candidate stems ranked by detection score.
2. Roll/pitch correction (Sec. III-B, Eq. 3): RANSAC over the stem axes of
   reconstructed trees, least-squares mean direction of the consensus set,
   rotated onto e_z; stem positions are rotated and projected to the plane.
3. Tree Distribution Histogram (Sec. III-C): 5 radial x 8 DBH bins with
   overlapping ranges, 2x2 uniform smoothing, chi-square distance; the 100
   closest database frames are kept.
4. 2D triangle descriptor (Sec. III-D): triangles from each tree's 10 nearest
   neighbours, hash of the quantized sorted side lengths (and area, as in the
   released code); the 10 candidates sharing the most keys are verified.
5. Two-step geometric verification (Sec. III-E): SE(2) from matched triangle
   centroids (Eq. 5), DBH-gated nearest-neighbour stem correspondences,
   second SVD refinement, overlap ratio (Eq. 6) ranks candidates; vertical
   offset from base heights by RANSAC; the 4-DoF transform is composed with
   both scenes' axis-alignment rotations into a 6-DoF pose.

Interface (gym): ``python method/treeloc.py --input in.json --output out.json``.
The output holds, per query, the best database frame, the overlap ratio as its
score, and the estimated transform mapping query-frame points into the
candidate frame.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

BOX_HALF_WIDTH_M = 30.0
TARGET_TREES = 30
SUPPLEMENT_SCORE_MIN = 0.1
SPATIAL_BINS = [(0.0, 7.0), (5.0, 13.0), (11.0, 19.0), (17.0, 25.0), (23.0, 30.0)]
DBH_MIN, DBH_MAX, DBH_SECTIONS, DBH_BIN_WIDTH = 0.0, 0.8, 8, 0.15
KNN_K = 10
MIN_EDGE_M, MAX_EDGE_M = 2.0, 30.0
DELTA_L = 0.1
HASH_RHO, HASH_MOD = 100007, 50000000
AXIS_RANSAC_TOL_DEG = 10.0
INIT_MATCH_DIST_M, INIT_MATCH_DBH_M = 0.5, 0.4
FINAL_MATCH_DIST_M = 0.4
Z_RANSAC_ITERS, Z_RANSAC_SAMPLE, Z_INLIER_M, Z_MIN_INLIER_RATIO = 200, 10, 0.1, 0.9


def dbh_bins() -> list[tuple[float, float]]:
    step = (DBH_MAX - DBH_MIN) / (DBH_SECTIONS + 1)
    bins = [(DBH_MIN + i * step, DBH_MIN + i * step + DBH_BIN_WIDTH) for i in range(DBH_SECTIONS - 1)]
    bins.append((bins[-1][0] + step, math.inf))
    return bins


DBH_BINS = dbh_bins()


@dataclass
class Scene:
    id: str
    align: np.ndarray  # 3x3 rotation taking raw local coordinates to the gravity-aligned frame
    centers: np.ndarray  # (n, 2) aligned stem centres of selected trees
    heights: np.ndarray  # (n,) aligned base heights
    dbh: np.ndarray  # (n,)
    tdh: np.ndarray  # (40,)
    hash_list: list[int] = field(default_factory=list)  # one hash per triangle (with repeats)
    hash_last: dict[int, tuple[int, int, int]] = field(default_factory=dict)  # hash -> last triangle
    hash_counter: Counter = field(default_factory=Counter)
    hash_set: frozenset = frozenset()


# ----------------------------------------------------------------------------- preprocessing


def rotation_onto_z(a: np.ndarray) -> np.ndarray:
    a = a / (np.linalg.norm(a) + 1e-12)
    z = np.array([0.0, 0.0, 1.0])
    c = float(np.clip(a @ z, -1.0, 1.0))
    if abs(c - 1.0) < 1e-12:
        return np.eye(3)
    if abs(c + 1.0) < 1e-12:
        return np.diag([-1.0, 1.0, -1.0])
    v = np.cross(a, z)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1.0 + c)


def axis_alignment(axes: np.ndarray) -> np.ndarray:
    """RANSAC + least-squares solution of Eq. (3): align the dominant stem direction with e_z."""
    if len(axes) == 0:
        return np.eye(3)
    a = axes / (np.linalg.norm(axes, axis=1, keepdims=True) + 1e-12)
    a = np.where(a[:, 2:3] < 0.0, -a, a)  # |e_z^T R a| is sign-invariant
    cos_tol = math.cos(math.radians(AXIS_RANSAC_TOL_DEG))
    support = np.abs(a @ a.T) >= cos_tol  # hypothesis = each observed axis
    counts = support.sum(axis=1)
    best = int(np.argmax(counts))
    inliers = a[support[best]]
    mean = inliers.mean(axis=0)
    return rotation_onto_z(mean)


def select_trees(trees: np.ndarray, f: dict) -> np.ndarray:
    """Upstream SelectTreesForDescriptors: reconstructed stems, then candidate stems by score."""
    rec = trees[:, f["reconstructed"]] == 1
    nclu = trees[:, f["number_clusters"]]
    score = trees[:, f["score"]]
    chosen = list(np.flatnonzero(rec))
    if len(chosen) < TARGET_TREES:
        cand = np.flatnonzero(~rec & (nclu > 2) & (score > SUPPLEMENT_SCORE_MIN))
        cand = cand[np.argsort(-score[cand], kind="stable")]
        chosen += list(cand[: TARGET_TREES - len(chosen)])
    if len(chosen) < TARGET_TREES:
        cand = np.flatnonzero(~rec & (nclu == 2) & (score > SUPPLEMENT_SCORE_MIN))
        cand = cand[np.argsort(-score[cand], kind="stable")]
        chosen += list(cand[: TARGET_TREES - len(chosen)])
    return np.array(chosen, dtype=int)


def tdh_descriptor(centers: np.ndarray, dbh: np.ndarray, use_dbh: bool = True) -> np.ndarray:
    bins_d = DBH_BINS if use_dbh else [(-math.inf, math.inf)]
    hist = np.zeros((len(SPATIAL_BINS), len(bins_d)))
    for (x, y), d in zip(centers, dbh):
        r = math.hypot(x, y)
        si = next((i for i, (lo, hi) in enumerate(SPATIAL_BINS) if lo < r <= hi), -1)
        if si < 0:
            continue
        for j, (lo, hi) in enumerate(bins_d):
            if (lo < d <= hi) or (j == len(bins_d) - 1 and d > lo):
                hist[si, j] += 1.0
                break
    smooth = np.zeros_like(hist)
    for i in range(hist.shape[0]):
        for j in range(hist.shape[1]):
            smooth[i, j] = hist[i : i + 2, j : j + 2].sum()
    return smooth.ravel()


def order_by_edge_length(pts: list, i: int, j: int, k: int) -> tuple[int, int, int]:
    """Canonical vertex order of the released code: start from the longest edge."""
    (xi, yi), (xj, yj), (xk, yk) = pts[i], pts[j], pts[k]
    d_ij = (xi - xj) ** 2 + (yi - yj) ** 2
    d_jk = (xj - xk) ** 2 + (yj - yk) ** 2
    d_ki = (xk - xi) ** 2 + (yk - yi) ** 2
    a, b, c = i, j, k
    dbc, dca = d_jk, d_ki
    if d_jk >= d_ij and d_jk >= d_ki:
        a, b, c = j, k, i
        dbc, dca = d_ki, d_ij
    elif d_ki >= d_ij and d_ki >= d_jk:
        a, b, c = k, i, j
        dbc, dca = d_ij, d_jk
    if dbc < dca:
        a, b = b, a
    return (a, b, c)


def knn_triangles(centers: np.ndarray) -> list[tuple[int, int, int]]:
    """Triangles over each tree's KNN neighbourhood (k = 10, edge range [2, 30] m)."""
    n = len(centers)
    if n < 3:
        return []
    d = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(-1))
    pts = [tuple(p) for p in centers.tolist()]
    triples = set()
    for i in range(n):
        order = np.argsort(d[i], kind="stable")[: KNN_K + 1].tolist()
        row = d[i]
        neigh = sorted(j for j in order if j != i and MIN_EDGE_M <= row[j] <= MAX_EDGE_M)
        for a, b, c in itertools.combinations(neigh, 3):
            triples.add(order_by_edge_length(pts, a, b, c))
    return sorted(triples)


def triangle_hash(p0, p1, p2) -> int:
    """Hash of the quantized sorted side lengths, extended by the area bucket (released code)."""
    a, b, c = sorted((math.dist(p0, p1), math.dist(p1, p2), math.dist(p2, p0)))
    e1, e2, e3 = (int(math.floor(x / DELTA_L + 0.5)) for x in (a, b, c))  # std::round
    h = (e3 * HASH_RHO + e2) % HASH_MOD
    h = (h * HASH_RHO + e1) % HASH_MOD
    s = (a + b + c) / 2.0
    area = math.sqrt(max(s * (s - a) * (s - b) * (s - c), 0.0))
    return (h * HASH_RHO + int(math.floor(area / DELTA_L + 0.5))) % HASH_MOD


def make_scene(frame: dict, f: dict, use_alignment: bool = True, use_dbh: bool = True) -> Scene:
    raw = np.array(
        [
            [
                t[f["x"]], t[f["y"]], t[f["z"]], t[f["axis_x"]], t[f["axis_y"]], t[f["axis_z"]],
                t[f["dbh"]] if t[f["dbh"]] is not None else t[f["dbh_approximation"]],
                t[f["score"]], t[f["reconstructed"]], t[f["number_clusters"]],
            ]
            for t in frame["trees"]
        ],
        dtype=float,
    ).reshape(-1, 10)
    g = {"reconstructed": 8, "number_clusters": 9, "score": 7}
    # Released-code order (ProcessFile): the alignment uses the reconstructed
    # stems inside the raw 60 m box; tree selection runs on all (aligned) trees
    # and the 60 m box crop is applied to the aligned positions afterwards.
    in_box = (np.abs(raw[:, 0]) <= BOX_HALF_WIDTH_M) & (np.abs(raw[:, 1]) <= BOX_HALF_WIDTH_M)
    rec = raw[:, 8] == 1
    align = axis_alignment(raw[rec & in_box, 3:6])
    pos = raw[:, 0:3] @ align.T
    sel = select_trees(raw, g)
    if len(sel):
        keep = (np.abs(pos[sel, 0]) <= BOX_HALF_WIDTH_M) & (np.abs(pos[sel, 1]) <= BOX_HALF_WIDTH_M)
        sel = sel[keep]
    centers = pos[sel, :2] if len(sel) else np.zeros((0, 2))
    heights = pos[sel, 2] if len(sel) else np.zeros(0)
    dbh = raw[sel, 6] if len(sel) else np.zeros(0)
    # Descriptors (TDH, triangle hashes) use the aligned centres. The paper's
    # Table V "no alignment" ablation feeds the raw, unaligned centres to TDH
    # and the triangle hash instead; verification and the 6-DoF pose still use
    # the aligned scene (its SR stays at the full method's level in Table V).
    desc = centers if use_alignment else (raw[sel, :2] if len(sel) else np.zeros((0, 2)))
    scene = Scene(frame["id"], align, centers, heights, dbh, tdh_descriptor(desc, dbh, use_dbh))
    pts = [tuple(p) for p in desc.tolist()]
    for tri in knn_triangles(desc):
        h = triangle_hash(pts[tri[0]], pts[tri[1]], pts[tri[2]])
        scene.hash_list.append(h)
        scene.hash_last[h] = tri
    scene.hash_counter = Counter(scene.hash_list)
    scene.hash_set = frozenset(scene.hash_counter)
    return scene


# ----------------------------------------------------------------------------- matching


def kabsch_2d(src: np.ndarray, dst: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    sm, dm = src.mean(axis=0), dst.mean(axis=0)
    h = (src - sm).T @ (dst - dm)
    u, _, vt = np.linalg.svd(h)
    v = vt.T
    r = v @ u.T
    if np.linalg.det(r) < 0.0:
        v[:, 1] *= -1.0
        r = v @ u.T
    return r, dm - r @ sm


def nearest_query_for_candidates(q_pts: np.ndarray, c_pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    d = np.sqrt(((c_pts[:, None, :] - q_pts[None, :, :]) ** 2).sum(-1))
    idx = d.argmin(axis=1)
    return idx, d[np.arange(len(c_pts)), idx]


def hash_count(q: Scene, c: Scene) -> int:
    common = q.hash_set & c.hash_set
    return sum(q.hash_counter[h] for h in common)


def verify(q: Scene, c: Scene, first_step_only: bool = False) -> dict:
    """Two-step geometric verification (upstream Compute2DTransformation)."""
    out = {"overlap": 0.0, "R": np.eye(2), "t": np.zeros(2), "matches": []}
    common = q.hash_last.keys() & c.hash_last.keys()
    if len(common) < 2 or len(q.centers) == 0 or len(c.centers) == 0:
        return out
    qc = np.array([q.centers[list(q.hash_last[h])].mean(axis=0) for h in common])
    cc = np.array([c.centers[list(c.hash_last[h])].mean(axis=0) for h in common])
    r, t = kabsch_2d(qc, cc)
    if not first_step_only:
        idx, dist = nearest_query_for_candidates(q.centers @ r.T + t, c.centers)
        ok = (np.abs(q.dbh[idx] - c.dbh) <= INIT_MATCH_DBH_M) & (dist < INIT_MATCH_DIST_M)
        if ok.sum() >= 2:
            r, t = kabsch_2d(q.centers[idx[ok]], c.centers[ok])
    idx, dist = nearest_query_for_candidates(q.centers @ r.T + t, c.centers)
    ok = dist < FINAL_MATCH_DIST_M
    matches = [(int(i), int(j)) for j, i in zip(np.flatnonzero(ok), idx[ok])]
    union = len(q.centers) + len(c.centers) - len(matches)
    out.update(overlap=len(matches) / union if union > 0 else 0.0, R=r, t=t, matches=matches)
    return out


def ransac_z_offset(q: Scene, c: Scene, matches: list[tuple[int, int]], rng: np.random.Generator) -> float:
    """Vertical offset (candidate minus query base height) by RANSAC, as in the released code."""
    if not matches:
        return 0.0
    diffs = np.array([c.heights[j] - q.heights[i] for i, j in matches])
    if len(diffs) == 1:
        return float(diffs[0])
    n = len(diffs)
    sample = min(Z_RANSAC_SAMPLE, n)
    best_count, best = 0, None
    for _ in range(Z_RANSAC_ITERS):
        guess = diffs[rng.integers(0, n, size=sample)].mean()
        inl = np.abs(diffs - guess) < Z_INLIER_M
        cnt = int(inl.sum())
        if cnt > best_count and cnt >= Z_MIN_INLIER_RATIO * n:
            best_count, best = cnt, float(diffs[inl].mean())
    return best if best is not None else float(diffs.mean())


def compose_pose(q: Scene, c: Scene, v: dict, dz: float) -> tuple[np.ndarray, np.ndarray]:
    r4 = np.eye(3)
    r4[:2, :2] = v["R"]
    t4 = np.array([v["t"][0], v["t"][1], dz])
    rot = c.align.T @ r4 @ q.align
    trans = c.align.T @ t4
    return rot, trans


def localize(payload: dict, top_tdh: int, top_hash: int, use_alignment: bool, use_dbh: bool, first_step_only: bool, seed: int = 0) -> dict:
    fields = {name: i for i, name in enumerate(payload["tree_fields"])}
    predictions = []
    for seq in payload["sequences"]:
        db = [make_scene(fr, fields, use_alignment, use_dbh) for fr in seq["database"]]
        queries = [make_scene(fr, fields, use_alignment, use_dbh) for fr in seq["queries"]]
        db_tdh = np.stack([s.tdh for s in db])
        for q in queries:
            chi = ((db_tdh - q.tdh) ** 2 / (db_tdh + q.tdh + 1e-10)).sum(axis=1)
            order = np.argsort(chi, kind="stable")
            coarse = order if top_tdh <= 0 else order[:top_tdh]
            ranked = sorted(((hash_count(q, db[i]), -chi[i], int(i)) for i in coarse), key=lambda x: (-x[0], -x[1]))
            fine = ranked if top_hash <= 0 else ranked[:top_hash]
            best_overlap, best_i, best_v = -1.0, None, None
            for _, _, i in fine:
                v = verify(q, db[i], first_step_only)
                if best_overlap <= v["overlap"]:  # ties: the later candidate wins, as in the released code
                    best_overlap, best_i, best_v = v["overlap"], i, v
            cand = db[best_i]
            rng = np.random.default_rng(seed)
            dz = ransac_z_offset(q, cand, best_v["matches"], rng)
            rot, trans = compose_pose(q, cand, best_v, dz)
            predictions.append(
                {
                    "query": q.id,
                    "candidate": cand.id,
                    "score": float(best_overlap),
                    "rotation": rot.tolist(),
                    "translation": trans.tolist(),
                }
            )
    return {"method": "treeloc", "predictions": predictions}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-tdh", type=int, default=100, help="TDH candidates kept (<=0: all)")
    parser.add_argument("--top-hash", type=int, default=10, help="candidates verified after hash ranking (<=0: all)")
    parser.add_argument("--no-alignment", action="store_true", help="ablation (Table V, Align = none): TDH and triangle hashes from raw, unaligned centres")
    parser.add_argument("--no-dbh", action="store_true", help="ablation: TDH without DBH bins")
    parser.add_argument("--first-step-only", action="store_true", help="ablation TreeLoc-f: centroid alignment only")
    parser.add_argument("--seed", type=int, default=0, help="seed of the vertical-offset RANSAC")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text())
    result = localize(payload, args.top_tdh, args.top_hash, not args.no_alignment, not args.no_dbh, args.first_step_only, args.seed)
    Path(args.output).write_text(json.dumps(result))


if __name__ == "__main__":
    main()
