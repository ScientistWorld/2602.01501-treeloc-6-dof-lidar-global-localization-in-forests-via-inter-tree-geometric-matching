#!/usr/bin/env python3
"""Hardening audit variant: TreeLoc with a more robust geometric verification.

Not part of the gym's reference. Reuses the reference preprocessing (tree
selection, axis alignment, TDH, triangle hashes) from method/treeloc.py and
changes only verification / pose estimation:

* every hash-matched triangle pair (not just the last one per key) yields an
  SE(2) hypothesis from its three ordered vertices; the hypothesis with the
  most DBH-consistent stem correspondences wins (RANSAC-style), followed by
  iterative SVD refinement on the correspondences;
* candidates are ranked by overlap ratio weighted by exp(-(|t|/tau)^2), with
  |t| the estimated planar offset (translation-aware overlap, cf. TreeLoc++);
* ``--tilt``: residual roll/pitch and height are fitted robustly to the matched
  base heights after planar alignment (6-DoF refinement);
* ``--exhaustive``: skip TDH / hash pruning and verify every database frame.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("treeloc_ref", ROOT / "method" / "treeloc.py")
T = importlib.util.module_from_spec(_spec)
sys.modules["treeloc_ref"] = T
_spec.loader.exec_module(T)

MAX_HYP = 400
MATCH_DIST, MATCH_DBH = 0.4, 0.2
REFINE_DIST = 0.5


def triangle_table(scene) -> dict:
    pts = [tuple(p) for p in scene.centers.tolist()]
    table = defaultdict(list)
    for tri in T.knn_triangles(scene.centers):
        table[T.triangle_hash(pts[tri[0]], pts[tri[1]], pts[tri[2]])].append(tri)
    return table


def support(q, c, rs: np.ndarray, ts: np.ndarray) -> np.ndarray:
    """Number of DBH-consistent candidate stems explained by each hypothesis."""
    tq = np.einsum("hij,nj->hni", rs, q.centers) + ts[:, None, :]  # (H, Nq, 2)
    d = np.sqrt(((c.centers[None, :, None, :] - tq[:, None, :, :]) ** 2).sum(-1))  # (H, Nc, Nq)
    idx = d.argmin(axis=2)
    dmin = np.take_along_axis(d, idx[..., None], axis=2)[..., 0]
    ok = (dmin < MATCH_DIST) & (np.abs(q.dbh[idx] - c.dbh[None, :]) <= MATCH_DBH)
    return ok.sum(axis=1)


def correspondences(q, c, r, t, dist_thr, use_dbh=True):
    idx, dist = T.nearest_query_for_candidates(q.centers @ r.T + t, c.centers)
    ok = dist < dist_thr
    if use_dbh:
        ok &= np.abs(q.dbh[idx] - c.dbh) <= MATCH_DBH
    return idx, ok


def robust_verify(q, c, qtab, ctab) -> dict:
    out = {"overlap": 0.0, "R": np.eye(2), "t": np.zeros(2), "matches": [], "support": 0}
    common = sorted(qtab.keys() & ctab.keys())
    if len(common) < 1 or len(q.centers) < 3 or len(c.centers) < 3:
        return out
    hyps = []
    for h in common:
        for tq in qtab[h][:2]:
            for tc in ctab[h][:2]:
                src, dst = q.centers[list(tq)], c.centers[list(tc)]
                r, t = T.kabsch_2d(src, dst)
                if np.abs(src @ r.T + t - dst).max() < 0.3:
                    hyps.append((r, t))
        if len(hyps) >= MAX_HYP:
            break
    if len(common) >= 2:  # the paper's centroid hypothesis is always considered too
        qc = np.array([q.centers[list(q.hash_last[h])].mean(axis=0) for h in common if h in q.hash_last and h in c.hash_last])
        cc = np.array([c.centers[list(c.hash_last[h])].mean(axis=0) for h in common if h in q.hash_last and h in c.hash_last])
        if len(qc) >= 2:
            hyps.append(T.kabsch_2d(qc, cc))
    if not hyps:
        return out
    rs = np.stack([h[0] for h in hyps])
    ts = np.stack([h[1] for h in hyps])
    counts = support(q, c, rs, ts)
    best = int(np.argmax(counts))
    r, t = rs[best], ts[best]
    for _ in range(3):
        idx, ok = correspondences(q, c, r, t, REFINE_DIST)
        if ok.sum() < 3:
            break
        r, t = T.kabsch_2d(q.centers[idx[ok]], c.centers[ok])
    idx, dist = T.nearest_query_for_candidates(q.centers @ r.T + t, c.centers)
    ok = dist < T.FINAL_MATCH_DIST_M
    matches = [(int(i), int(j)) for j, i in zip(np.flatnonzero(ok), idx[ok])]
    union = len(q.centers) + len(c.centers) - len(matches)
    out.update(overlap=len(matches) / union if union else 0.0, R=r, t=t, matches=matches, support=int(counts[best]))
    return out


def tilt_refine(q, c, v: dict, rng: np.random.Generator):
    """Fit z_c - z_q' = dz + wx*y' - wy*x' robustly; returns (R_tilt, dz) or None."""
    m = v["matches"]
    if len(m) < 8:
        return None
    qi = np.array([i for i, _ in m])
    ci = np.array([j for _, j in m])
    p = q.centers[qi] @ v["R"].T + v["t"]
    a = np.column_stack([np.ones(len(m)), p[:, 1], -p[:, 0]])
    b = c.heights[ci] - q.heights[qi]
    best_inl = None
    for _ in range(200):
        s = rng.choice(len(m), size=3, replace=False)
        try:
            x = np.linalg.solve(a[s], b[s])
        except np.linalg.LinAlgError:
            continue
        inl = np.abs(a @ x - b) < 0.15
        if best_inl is None or inl.sum() > best_inl.sum():
            best_inl = inl
    if best_inl is None or best_inl.sum() < 8:
        return None
    x, *_ = np.linalg.lstsq(a[best_inl], b[best_inl], rcond=None)
    dz, wx, wy = (float(v_) for v_ in x)
    w = np.array([wx, wy, 0.0])
    ang = float(np.linalg.norm(w))
    if ang > math.radians(5.0):
        return None
    if ang < 1e-12:
        return np.eye(3), dz
    k = w / ang
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * kx + (1 - math.cos(ang)) * kx @ kx, dz


def localize(payload: dict, exhaustive: bool, tilt: bool, tau: float) -> dict:
    fields = {name: i for i, name in enumerate(payload["tree_fields"])}
    preds = []
    for seq in payload["sequences"]:
        db = [T.make_scene(fr, fields) for fr in seq["database"]]
        queries = [T.make_scene(fr, fields) for fr in seq["queries"]]
        db_tab = [triangle_table(s) for s in db]
        db_tdh = np.stack([s.tdh for s in db])
        for q in queries:
            qtab = triangle_table(q)
            if exhaustive:
                pool = range(len(db))
            else:
                chi = ((db_tdh - q.tdh) ** 2 / (db_tdh + q.tdh + 1e-10)).sum(axis=1)
                coarse = np.argsort(chi, kind="stable")[:100]
                ranked = sorted(((T.hash_count(q, db[i]), -chi[i], int(i)) for i in coarse), key=lambda x: (-x[0], -x[1]))
                pool = [i for _, _, i in ranked[:10]]
            best = (-1.0, None, None)
            for i in pool:
                if exhaustive and len(q.hash_set & db[i].hash_set) < 2:
                    continue
                v = robust_verify(q, db[i], qtab, db_tab[i])
                key = v["overlap"] * math.exp(-((float(np.linalg.norm(v["t"])) / tau) ** 2))
                if key > best[0]:
                    best = (key, i, v)
            if best[1] is None:
                best = (0.0, 0, robust_verify(q, db[0], qtab, db_tab[0]))
            key, i, v = best
            cand = db[i]
            rng = np.random.default_rng(0)
            rot = trans = None
            if tilt:
                fit = tilt_refine(q, cand, v, rng)
                if fit is not None:
                    r_tilt, dz = fit
                    r4 = np.eye(3)
                    r4[:2, :2] = v["R"]
                    rot_a = r_tilt @ r4
                    trans_a = r_tilt @ np.array([v["t"][0], v["t"][1], 0.0]) + np.array([0.0, 0.0, dz])
                    rot = cand.align.T @ rot_a @ q.align
                    trans = cand.align.T @ trans_a
            if rot is None:
                dz = T.ransac_z_offset(q, cand, v["matches"], rng)
                rot, trans = T.compose_pose(q, cand, v, dz)
            preds.append({"query": q.id, "candidate": cand.id, "score": float(key),
                          "rotation": rot.tolist(), "translation": trans.tolist()})
    return {"method": "treeloc_robust", "predictions": preds}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--tilt", action="store_true")
    ap.add_argument("--tau", type=float, default=10.0)
    a = ap.parse_args()
    payload = json.loads(Path(a.input).read_text())
    Path(a.output).write_text(json.dumps(localize(payload, a.exhaustive, a.tilt, a.tau)))


if __name__ == "__main__":
    main()
