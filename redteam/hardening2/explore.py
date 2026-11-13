#!/usr/bin/env python3
"""Hardening iteration 12, exploration stage (audit code, not part of the gym).

Question: how large must the hidden inter-session test be before exhaustive
verification (the paper's verifier run on every database scene) stops
outranking the reference (TDH top-100 -> hash top-10 -> verification)?

Builds candidate inter-session test slices from the pinned upstream release
(data/downloads/treeloc_src, gitignored) with the hidden-test builder's own
functions, runs a set of methods on each, and stores per-query details
(correct / success / errors / score) so that any pooling of directions can be
scored exactly afterwards (analyze.py). The intra-session slice is unchanged
and taken from eval/test/data.

Variants (each one direction, one sequence):
  A<R>: V-03 queries inside the official test regions vs V-02 database within R m
  B<R>: V-02 queries inside the official test regions vs V-03 database within R m
  for R in {15 (current margin), 35, 50}.

Resumable: a finished (variant, method) pair is skipped.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import os
import random
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SRC = ROOT / "data" / "downloads" / "treeloc_src" / "data"
WORK = ROOT / "data" / "downloads" / "explore"  # gitignored: hidden-region variants stay out of git
RES = HERE / "results"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


P = load("prep_test", ROOT / "eval" / "test" / "prepare_test_data.py")
E = load("eval_test", ROOT / "eval" / "test" / "evaluate.py")

METHODS = {
    "treeloc": [sys.executable, "method/treeloc.py"],
    "bruteforce_exhaustive": [sys.executable, "method/treeloc.py", "--top-tdh", "0", "--top-hash", "0"],
    "verify_tdh100": [sys.executable, "method/treeloc.py", "--top-hash", "100"],
    "stronger_robust_tilt": [sys.executable, "redteam/hardening/treeloc_robust.py", "--tilt"],
    "ablation_no_tdh": [sys.executable, "method/treeloc.py", "--top-tdh", "0"],
    "weaker_no_dbh": [sys.executable, "method/treeloc.py", "--no-dbh"],
    "weaker_treeloc_f": [sys.executable, "method/treeloc.py", "--first-step-only"],
    "treeloc_no_alignment": [sys.executable, "method/treeloc.py", "--no-alignment"],
    "tdh_baseline": [sys.executable, "baseline/tdh_baseline.py"],
}


def build_variants() -> dict[str, tuple[Path, Path]]:
    out = {}
    v02, v03 = SRC / "Wild_V02", SRC / "Wild_V03"
    t02, t03 = P.read_trajectory(v02), P.read_trajectory(v03)
    d02 = [P.distance_to_test_regions(p[0], p[1]) for p in t02]
    d03 = [P.distance_to_test_regions(p[0], p[1]) for p in t03]
    offsets = None
    for radius in (15, 35, 50):
        for direction in ("A", "B"):
            name = f"inter_{direction}{radius}"
            vdir = WORK / name
            inp, tru = vdir / "input.json.gz", vdir / "truth.json.gz"
            out[name] = (inp, tru)
            if inp.is_file() and tru.is_file():
                continue
            if offsets is None:
                cache = WORK / "v03_offsets.json"
                if cache.is_file():
                    offsets = {int(k): tuple(v) for k, v in json.loads(cache.read_text()).items()}
                else:
                    t0 = time.time()
                    offsets = P.session_registration_offsets(v02, v03)
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_text(json.dumps({str(k): list(v) for k, v in offsets.items()}))
                    print(f"registration offsets in {time.time() - t0:.0f}s", flush=True)
            rng = random.Random(f"explore::{name}")
            if direction == "A":  # V-03 queries vs V-02 database (V-03 poses registered)
                db_idx = [i for i, d in enumerate(d02) if d <= radius]
                q_idx = [i for i, d in enumerate(d03) if d == 0.0]
                payload, truth = P.build_experiment("inter_session", v02, db_idx, v03, q_idx, rng, "seq_v", q_offsets=offsets)
            else:  # V-02 queries vs V-03 database: register the V-03 database poses
                db_idx = [i for i, d in enumerate(d03) if d <= radius]
                q_idx = [i for i, d in enumerate(d02) if d == 0.0]
                payload, truth = P.build_experiment("inter_session", v03, db_idx, v02, q_idx, rng, "seq_v")
                src = truth["source"]
                for fid, pose in truth["database"].items():
                    i = int(src[fid].split(":")[1])
                    truth["database"][fid] = [round(pose[k] + offsets[i][k], 6) if k < 3 else pose[k] for k in range(7)]
            P.write_json_gz(inp, payload)
            P.write_json_gz(tru, {"experiments": {"inter_session_localization": truth}})
            seq = payload["sequences"][0]
            print(f"{name}: {len(seq['database'])} database, {len(seq['queries'])} queries", flush=True)
    # current hidden intra slice, unchanged
    out["intra_S50"] = (ROOT / "eval/test/data/intra_session_localization.input.json.gz", ROOT / "eval/test/data/truth.json.gz")
    # paper's intra protocol approximated by chronological blocks: queries of block j
    # see every frame before s_j (s_j <= t - 50), so the database grows along the run
    vdir = WORK / "intra_SP"
    inp, tru = vdir / "input.json.gz", vdir / "truth.json.gz"
    out["intra_SP"] = (inp, tru)
    if not (inp.is_file() and tru.is_file()):
        stein = SRC / "Oxford_Stein"
        traj = P.read_trajectory(stein)
        n = len(traj)
        bounds = [150, 300, 450, 600, 750, 900, n]
        rng = random.Random("explore::intra_SP")
        seqs, truth = [], {"database": {}, "queries": {}, "source": {}}
        for j in range(len(bounds) - 1):
            s0, s1 = bounds[j], bounds[j + 1]
            q_idx = [t for t in range(s0 + P.EXCLUSION_FRAMES, min(n, s1 + P.EXCLUSION_FRAMES))]
            payload, tr = P.build_experiment("intra_session", stein, list(range(s0)), stein, q_idx, rng, f"seq_s{j}")
            if not payload["sequences"][0]["queries"]:
                continue
            seqs += payload["sequences"]
            for k in truth:
                truth[k].update(tr[k])
        payload["sequences"] = seqs
        P.write_json_gz(inp, payload)
        P.write_json_gz(tru, {"experiments": {"intra_session_localization": truth}})
        print("intra_SP: " + ", ".join(f"{s['name']} {len(s['database'])}/{len(s['queries'])}" for s in seqs), flush=True)
    return out


def run(task) -> dict:
    variant, method, (inp, tru) = task
    det_path = RES / "details" / variant / f"{method}.json"
    if det_path.is_file():
        return json.loads((RES / "metrics" / variant / f"{method}.json").read_text())
    exp = "intra_session_localization" if variant.startswith("intra") else "inter_session_localization"
    raw = gzip.decompress(inp.read_bytes())
    payload = json.loads(raw)
    truth = E.Truth(json.loads(gzip.decompress(tru.read_bytes()))["experiments"][exp])
    wdir = WORK / "runs" / variant
    wdir.mkdir(parents=True, exist_ok=True)
    in_json, out_json = wdir / f"{method}.input.json", wdir / f"{method}.output.json"
    in_json.write_bytes(raw)
    t0 = time.time()
    env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    proc = subprocess.run(METHODS[method] + ["--input", str(in_json), "--output", str(out_json)], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    secs = time.time() - t0
    in_json.unlink(missing_ok=True)
    if proc.returncode != 0:
        print(f"FAILED {variant}/{method}: {proc.stderr[-800:]}", flush=True)
        return {"variant": variant, "method": method, "status": "failed"}
    preds = E.validate_output(json.loads(out_json.read_text()), payload)
    metrics, details = E.score_experiment(preds, truth)
    for d in details:  # distance of the returned scene, for the analysis
        d["dist"] = truth.xy_distance(d["query"], d["candidate"])
    det_path.parent.mkdir(parents=True, exist_ok=True)
    (RES / "metrics" / variant).mkdir(parents=True, exist_ok=True)
    rec = {"variant": variant, "method": method, "status": "ok", "seconds": round(secs, 1), "metrics": metrics,
           "n_queries": len(truth.q), "n_database": len(truth.db)}
    (RES / "metrics" / variant / f"{method}.json").write_text(json.dumps(rec))
    det_path.write_text(json.dumps(details))
    print(f"{variant}/{method} ok in {secs:.0f}s: " + ", ".join(f"{k}={v:.3f}" for k, v in metrics.items()), flush=True)
    return rec


def main() -> int:
    variants = build_variants()
    order = ["bruteforce_exhaustive", "verify_tdh100", "stronger_robust_tilt", "ablation_no_tdh", "treeloc",
             "weaker_treeloc_f", "weaker_no_dbh", "treeloc_no_alignment", "tdh_baseline"]
    # longest tasks first (largest databases first)
    vorder = ["inter_B50", "inter_A50", "inter_B35", "inter_A35", "inter_B15", "inter_A15", "intra_SP", "intra_S50"]
    tasks = [(v, m, variants[v]) for m in order for v in vorder]
    tasks.sort(key=lambda t: (order.index(t[1]) > 1, vorder.index(t[0])))
    jobs = int(os.environ.get("EXPLORE_JOBS", "8"))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        recs = list(pool.map(run, tasks))
    (RES / "summary.json").write_text(json.dumps(recs, indent=1))
    return 0 if all(r.get("status") == "ok" for r in recs) else 1


if __name__ == "__main__":
    sys.exit(main())
