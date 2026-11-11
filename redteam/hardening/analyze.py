#!/usr/bin/env python3
"""Rank analysis for the hardening audit.

rank_delta(m) = sum_exp w_exp * sum_metric |coef| * dir * (m - ref) / std_P(metric, exp)

with dir = +1 for higher-is-better metrics, P a population of attempts
(Q: honest methods only; A: every audited entry, failed ones at their worst
values). Paired bootstrap over test queries (same resampled queries for every
method) gives a 95% interval for the rank delta of each method with per-query
details, holding the normalisation fixed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = "treeloc"
WORST = {"R_at_1": 0.0, "F1": 0.0, "AUC": 0.0, "R_at_50": 0.0, "SR": 0.0, "TE_m": 0.5, "RE_deg": 5.0, "TE_all_m": 10.0, "RE_all_deg": 180.0}


def pr(correct: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    n = len(correct)
    if n == 0 or correct.sum() == 0:
        return 0.0, 0.0
    order = np.argsort(-scores, kind="stable")
    s, c = scores[order], correct[order]
    last = np.r_[s[1:] != s[:-1], True]  # end of each tie group
    tp = np.cumsum(c)[last].astype(float)
    det = (np.arange(1, n + 1))[last].astype(float)
    precision = tp / det
    recall = tp / n
    with np.errstate(invalid="ignore", divide="ignore"):
        f1 = np.where(tp > 0, 2 * precision * recall / (precision + recall), 0.0)
    auc = float(np.sum(precision * np.diff(np.r_[0.0, recall])))
    return float(f1.max()), auc


def metrics_from_details(d: dict, idx: np.ndarray) -> dict:
    c, s, ok, te, re, sc = (d[k][idx] for k in ("correct", "success", "ok", "te", "re", "score"))
    n = len(idx)
    tp = c.sum()
    good = ok & (c == 1)
    f1, auc = pr(c, sc)
    return {
        "R_at_1": c.mean(), "F1": f1, "AUC": auc, "R_at_50": s.mean(),
        "SR": good.sum() / tp if tp else 0.0,
        "TE_m": te[good].mean() if good.any() else 0.5,
        "RE_deg": re[good].mean() if good.any() else 5.0,
        "TE_all_m": np.minimum(te, 10.0).mean(), "RE_all_deg": np.minimum(re, 180.0).mean(),
    }


def load_details(ddir: Path, name: str, exp: str):
    path = ddir / f"{name}__{exp}.json"
    if not path.is_file():
        return None
    rows = sorted(json.loads(path.read_text()), key=lambda r: r["query"])
    arr = lambda k, t=float: np.array([t(r[k]) for r in rows])
    return {"correct": arr("correct", int), "success": arr("success", int), "ok": arr("success", int).astype(bool),
            "te": arr("te"), "re": arr("re"), "score": arr("score")}


def rank_delta(vals: dict, ref: dict, ref_json: dict, stds: dict) -> float:
    total = 0.0
    for exp, e in ref_json["experiments"].items():
        for m, spec in e["metrics"].items():
            sd = stds[exp][m]
            if sd <= 0:
                continue
            sign = 1.0 if spec["higher_is_better"] else -1.0
            total += e["weight"] * abs(spec["coefficient"]) * sign * (vals[exp][m] - ref[exp][m]) / sd
    return total


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", nargs="+", required=True, help="score files; later files override earlier ones per method")
    ap.add_argument("--details", default=None, help="per-query details dir (TREELOC_DETAILS_DIR) for the paired bootstrap")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude", nargs="*", default=[], help="method names to leave out")
    a = ap.parse_args()
    out_path = Path(a.out)
    details_dir = Path(a.details) if a.details else None
    ref_json = json.loads((ROOT / "scoring" / "reference.json").read_text())
    exps = list(ref_json["experiments"])
    vals, status = {}, {}
    for path in a.scores:
        scores = json.loads(Path(path).read_text())["experiments"]
        for n in scores[exps[0]]["results"]:
            if n in a.exclude:
                continue
            vals[n] = {e: scores[e]["results"][n] for e in exps}
            status[n] = {e: scores[e].get("status", {}).get(n, "?") for e in exps}
    names = sorted(vals)
    honest = [n for n in names if not n.startswith("shortcut_") and all(s == "ok" for s in status[n].values())]
    panels = {"Q": honest, "A": names}
    stds = {p: {e: {m: float(np.std([vals[n][e][m] for n in members])) for m in ref_json["experiments"][e]["metrics"]} for e in exps}
            for p, members in panels.items()}
    report = {"panels": panels, "stds": stds, "methods": {}}
    for n in names:
        report["methods"][n] = {"status": status[n], "metrics": vals[n],
                                "rank_delta": {p: rank_delta(vals[n], vals[REF], ref_json, stds[p]) for p in panels}}

    # Paired bootstrap of the rank delta over test queries (normalisation from panel Q).
    det = {n: {e: (load_details(details_dir, n, e) if details_dir else None) for e in exps} for n in names}
    ref_det = det[REF]
    if all(ref_det[e] is not None for e in exps):
        rng = np.random.default_rng(12345)
        B = 1000
        boots = {e: [rng.integers(0, len(ref_det[e]["correct"]), len(ref_det[e]["correct"])) for _ in range(B)] for e in exps}
        ref_b = [{e: metrics_from_details(ref_det[e], boots[e][b]) for e in exps} for b in range(B)]
        for n in names:
            if n == REF or any(det[n][e] is None for e in exps):
                continue
            deltas = []
            for b in range(B):
                vb = {e: metrics_from_details(det[n][e], boots[e][b]) for e in exps}
                deltas.append(rank_delta(vb, ref_b[b], ref_json, stds["Q"]))
            deltas = np.array(deltas)
            per_metric = {}
            for e in exps:
                full = {m: v for m, v in metrics_from_details(det[n][e], np.arange(len(det[n][e]["correct"]))).items()}
                diffs = {m: [] for m in full}
                for b in range(0, B, 4):
                    vb = metrics_from_details(det[n][e], boots[e][b])
                    for m in full:
                        diffs[m].append(vb[m] - ref_b[b][e][m])
                per_metric[e] = {m: [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))] for m, d in diffs.items()}
            report["methods"][n]["bootstrap_rank_delta_Q"] = {
                "mean": float(deltas.mean()), "ci95": [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))],
                "p_le_0": float((deltas <= 0).mean()), "p_ge_0": float((deltas >= 0).mean()),
            }
            report["methods"][n]["bootstrap_metric_diff_ci95"] = per_metric
    out_path.write_text(json.dumps(report, indent=2))

    # Human-readable table.
    lines = []
    head = "| method | status | " + " | ".join(f"{e.split('_')[0]} {m}" for e in exps for m in ("R_at_1", "F1", "AUC", "R_at_50", "SR", "TE_m", "RE_deg", "TE_all_m", "RE_all_deg")) + " | Δrank Q | Δrank A | boot CI (Q) |"
    lines.append(head)
    lines.append("|" + "---|" * (head.count("|") - 1))
    order = sorted(names, key=lambda n: -report["methods"][n]["rank_delta"]["Q"])
    for n in order:
        r = report["methods"][n]
        st = "ok" if all(s == "ok" for s in r["status"].values()) else "; ".join(sorted(set(s for s in r["status"].values() if s != "ok")))[:60]
        cells = [f"{r['metrics'][e][m]:.3f}" for e in exps for m in ("R_at_1", "F1", "AUC", "R_at_50", "SR", "TE_m", "RE_deg", "TE_all_m", "RE_all_deg")]
        ci = r.get("bootstrap_rank_delta_Q", {}).get("ci95")
        lines.append(f"| {n} | {st} | " + " | ".join(cells) + f" | {r['rank_delta']['Q']:+.3f} | {r['rank_delta']['A']:+.3f} | {('[%+.3f, %+.3f]' % tuple(ci)) if ci else '—'} |")
    out_path.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
