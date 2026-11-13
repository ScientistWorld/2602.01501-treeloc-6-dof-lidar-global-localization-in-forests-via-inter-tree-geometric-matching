#!/usr/bin/env python3
"""Score candidate hidden-test configurations from the exploration details.

A configuration = the unchanged intra-session slice + one inter-session slice
made of one or both directions (A: V-03 -> V-02, B: V-02 -> V-03) at one
database margin R. Per-query details of separately run directions are pooled
exactly (each query only depends on its own database).

rank_delta(m) = sum_exp w_exp * sum_metric |coef| * dir * (m - ref) / std_P(metric)
with two normalisation panels: Q = every explored method, F = TreeLoc-family
variants only (no TDH-only baseline, no no-alignment ablation), which gives
the brute force the smallest denominators. 95% intervals: paired bootstrap
over queries (all methods resampled on the same queries, panel std fixed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
REF = "treeloc"
WORST = {"R_at_1": 0.0, "F1": 0.0, "AUC": 0.0, "R_at_50": 0.0, "SR": 0.0, "TE_m": 0.5, "RE_deg": 5.0, "TE_all_m": 10.0, "RE_all_deg": 180.0}


def pr(c: np.ndarray, s: np.ndarray):
    n = len(c)
    if n == 0 or c.sum() == 0:
        return 0.0, 0.0
    order = np.argsort(-s, kind="stable")
    s, c = s[order], c[order]
    last = np.r_[s[1:] != s[:-1], True]
    tp = np.cumsum(c)[last].astype(float)
    det = np.arange(1, n + 1)[last].astype(float)
    p, r = tp / det, tp / n
    with np.errstate(invalid="ignore", divide="ignore"):
        f1 = np.where(tp > 0, 2 * p * r / (p + r), 0.0)
    return float(f1.max()), float(np.sum(p * np.diff(np.r_[0.0, r])))


def metrics(d: dict, idx=None) -> dict:
    if idx is None:
        idx = np.arange(len(d["correct"]))
    c, ok, te, re, sc = (d[k][idx] for k in ("correct", "success", "te", "re", "score"))
    good = ok.astype(bool) & (c == 1)
    f1, auc = pr(c, sc)
    return {
        "R_at_1": c.mean(), "F1": f1, "AUC": auc, "R_at_50": ok.mean(),
        "SR": good.sum() / c.sum() if c.sum() else 0.0,
        "TE_m": te[good].mean() if good.any() else 0.5, "RE_deg": re[good].mean() if good.any() else 5.0,
        "TE_all_m": np.minimum(te, 10.0).mean(), "RE_all_deg": np.minimum(re, 180.0).mean(),
    }


def load(variant: str, method: str):
    p = RES / "details" / variant / f"{method}.json"
    if not p.is_file():
        return None
    rows = sorted(json.loads(p.read_text()), key=lambda r: r["query"])
    return {k: np.array([r[k] for r in rows], dtype=float) for k in ("correct", "success", "te", "re", "score", "dist")} | {
        "query": [r["query"] for r in rows]}


def pool(parts):
    parts = [p for p in parts]
    if any(p is None for p in parts):
        return None
    out = {k: np.concatenate([p[k] for p in parts]) for k in ("correct", "success", "te", "re", "score", "dist")}
    out["query"] = sum((p["query"] for p in parts), [])
    return out


def rank(vals, ref, spec, stds):
    tot = 0.0
    for exp, e in spec["experiments"].items():
        for m, ms in e["metrics"].items():
            sd = stds[exp][m]
            if sd <= 0:
                continue
            sign = 1.0 if ms["higher_is_better"] else -1.0
            tot += e["weight"] * abs(ms["coefficient"]) * sign * (vals[exp][m] - ref[exp][m]) / sd
    return tot


def analyze(config: str, inter_parts: list[str], spec: dict, methods: list[str], weights=None, intra: str = "intra_S50") -> dict:
    spec = json.loads(json.dumps(spec))
    if weights:
        for exp, w in weights.items():
            spec["experiments"][exp]["weight"] = w
    det = {}
    intra_name = intra
    for m in methods:
        intra = load(intra_name, m)
        inter = pool([load(v, m) for v in inter_parts])
        if intra is None or inter is None:
            continue
        det[m] = {"intra_session_localization": intra, "inter_session_localization": inter}
    names = sorted(det)
    vals = {m: {e: metrics(det[m][e]) for e in det[m]} for m in names}
    family = [m for m in names if m not in ("tdh_baseline", "treeloc_no_alignment")]
    panels = {"Q": names, "F": family}
    stds = {p: {e: {k: float(np.std([vals[m][e][k] for m in mem])) for k in WORST} for e in spec["experiments"]} for p, mem in panels.items()}
    out = {"config": config, "intra": intra_name, "inter_parts": inter_parts, "weights": {e: spec["experiments"][e]["weight"] for e in spec["experiments"]},
           "n_inter_queries": int(len(det[REF]["inter_session_localization"]["correct"])), "methods": {}}
    rng = np.random.default_rng(7)
    B = 400
    boots = {e: [rng.integers(0, len(det[REF][e]["correct"]), len(det[REF][e]["correct"])) for _ in range(B)] for e in spec["experiments"]}
    ref_b = [{e: metrics(det[REF][e], boots[e][b]) for e in spec["experiments"]} for b in range(B)]
    for m in names:
        rec = {"metrics": vals[m], "rank": {p: rank(vals[m], vals[REF], spec, stds[p]) for p in panels}}
        per_exp = {}
        for e in spec["experiments"]:
            sub = {"experiments": {e: spec["experiments"][e]}}
            per_exp[e] = {p: rank({e: vals[m][e]}, {e: vals[REF][e]}, sub, stds[p]) for p in panels}
        rec["rank_by_experiment"] = per_exp
        if m != REF:
            draws = [rank({e: metrics(det[m][e], boots[e][b]) for e in spec["experiments"]}, ref_b[b], spec, stds["Q"]) for b in range(B)]
            rec["ci_Q"] = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]
        out["methods"][m] = rec
    return out


def main() -> int:
    spec = json.loads((ROOT / "scoring" / "reference.json").read_text())
    methods = ["treeloc", "bruteforce_exhaustive", "verify_tdh100", "stronger_robust_tilt", "ablation_no_tdh",
               "weaker_no_dbh", "weaker_treeloc_f", "treeloc_no_alignment", "tdh_baseline"]
    configs = {f"A{r}": [f"inter_A{r}"] for r in (15, 35, 50)}
    configs |= {f"B{r}": [f"inter_B{r}"] for r in (15, 35, 50)}
    configs |= {f"AB{r}": [f"inter_A{r}", f"inter_B{r}"] for r in (15, 35, 50)}
    results = []
    lines = ["| config | weights | inter q | method | Δrank Q [95% CI] | Δrank F | intra Q | inter Q | inter R@1 | inter R@50 | inter SR | inter TE_all |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    runs = [(i, w) for i in ("intra_S50", "intra_SP") for w in (("0.6/0.4", None), ("0.5/0.5", {"intra_session_localization": 0.5, "inter_session_localization": 0.5}))]
    for intra, (wname, w) in runs:
        for c0, parts in configs.items():
            c = f"{intra[6:]}+{c0}"
            r = analyze(c, parts, spec, methods, w, intra)
            if not r["methods"]:
                continue
            results.append(r)
            for m in ("bruteforce_exhaustive", "verify_tdh100", "stronger_robust_tilt", "ablation_no_tdh", "weaker_treeloc_f", "treeloc"):
                if m not in r["methods"]:
                    continue
                x = r["methods"][m]
                ci = x.get("ci_Q")
                ie = x["metrics"]["inter_session_localization"]
                lines.append(
                    f"| {c} | {wname} | {r['n_inter_queries']} | {m} | {x['rank']['Q']:+.3f}"
                    + (f" [{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else "")
                    + f" | {x['rank']['F']:+.3f} | {x['rank_by_experiment']['intra_session_localization']['Q']:+.3f} | {x['rank_by_experiment']['inter_session_localization']['Q']:+.3f}"
                    + f" | {ie['R_at_1']:.3f} | {ie['R_at_50']:.3f} | {ie['SR']:.3f} | {ie['TE_all_m']:.3f} |"
                )
    (RES / "explore_analysis.json").write_text(json.dumps(results, indent=1, default=float))
    (RES / "explore_analysis.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
