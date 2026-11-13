import json, math, sys, statistics
from pathlib import Path
R = Path(__file__).resolve().parent / 'results' / 'details'
M = ["treeloc","bruteforce_exhaustive","verify_tdh100","stronger_robust_tilt","ablation_no_tdh","weaker_no_dbh","weaker_treeloc_f","treeloc_no_alignment","tdh_baseline"]
KEYS = ["R_at_1","F1","AUC","R_at_50","SR","TE_m","RE_deg","TE_all_m","RE_all_deg"]
HIB = {k: k in ("R_at_1","F1","AUC","R_at_50","SR") for k in KEYS}
def load(v, m):
    return json.loads((R / v / f"{m}.json").read_text())
def pr(rows):
    n=len(rows)
    rs=sorted(rows,key=lambda r:-r['score']); tp=fp=0; best=0; auc=0; prev=0; i=0
    while i<n:
        j=i
        while j<n and rs[j]['score']==rs[i]['score']:
            if rs[j]['correct']: tp+=1
            else: fp+=1
            j+=1
        p=tp/(tp+fp); r=tp/n
        if tp: best=max(best,2*p*r/(p+r))
        auc+=p*(r-prev); prev=r; i=j
    return best,auc
def metrics(rows):
    n=len(rows); c=sum(r['correct'] for r in rows)
    good=[r for r in rows if r['correct'] and r['success']]
    f1,auc=pr(rows)
    return {"R_at_1":c/n,"F1":f1,"AUC":auc,"R_at_50":sum(r['success'] for r in rows)/n,"SR":len(good)/c if c else 0,
            "TE_m":statistics.mean(r['te'] for r in good) if good else .5,"RE_deg":statistics.mean(r['re'] for r in good) if good else 5,
            "TE_all_m":statistics.mean(min(r['te'],10) for r in rows),"RE_all_deg":statistics.mean(min(r['re'],180) for r in rows)}
def evaluate(intra, inters, coefs, weights, panel=None, show=("bruteforce_exhaustive","stronger_robust_tilt","verify_tdh100","ablation_no_tdh","weaker_treeloc_f","weaker_no_dbh")):
    vals={}
    for m in M:
        vals[m]={"intra":metrics(load(intra,m)),"inter":metrics(sum((load(v,m) for v in inters),[]))}
    panel = panel or M
    sd={e:{k:statistics.pstdev([vals[m][e][k] for m in panel]) for k in KEYS} for e in ("intra","inter")}
    out={}
    for m in show:
        parts={e:{k:weights[e]*coefs[e][k]*(1 if HIB[k] else -1)*(vals[m][e][k]-vals["treeloc"][e][k])/sd[e][k] for k in KEYS} for e in ("intra","inter")}
        out[m]=(sum(sum(p.values()) for p in parts.values()), parts)
    return out, vals
CUR={"R_at_1":.8,"F1":.4,"AUC":.4,"R_at_50":1.0,"SR":.5,"TE_m":.4,"RE_deg":.4,"TE_all_m":.5,"RE_all_deg":.3}
if __name__=="__main__":
    out,vals=evaluate("intra_S50",["inter_A15"],{"intra":CUR,"inter":CUR},{"intra":.6,"inter":.4})
    for m,(t,p) in out.items():
        print(m, round(t,3)); 
        for e in p: print('  ',e, ' '.join(f"{k}:{v:+.3f}" for k,v in p[e].items()))


def sweep():
    """Rank of each variant under alternative weightings and normalisation panels."""
    pri = {"R_at_1": 1.0, "F1": 0.6, "AUC": 0.6, "R_at_50": 0.5, "SR": 0.3, "TE_m": 0.2, "RE_deg": 0.2, "TE_all_m": 0.3, "RE_all_deg": 0.2}
    fam = [m for m in M if m not in ("tdh_baseline", "treeloc_no_alignment")]
    lines = ["| intra | inter | inter coefficients | weights intra/inter | panel | " + " | ".join(m for m in ("bruteforce_exhaustive", "stronger_robust_tilt", "verify_tdh100", "ablation_no_tdh", "weaker_treeloc_f", "weaker_no_dbh")) + " |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for intra in ("intra_S50", "intra_SP"):
        for inter in (["inter_A15"], ["inter_A15", "inter_B15"]):
            for cname, ic in (("current", CUR), ("place-recognition-heavy", pri)):
                for wt in ((.6, .4), (.5, .5)):
                    for pname, panel in (("Q (all 9)", None), ("F (TreeLoc family)", fam)):
                        out, _ = evaluate(intra, inter, {"intra": CUR, "inter": ic}, {"intra": wt[0], "inter": wt[1]}, panel)
                        lines.append(f"| {intra[6:]} | {'+'.join(x[6:] for x in inter)} | {cname} | {wt[0]}/{wt[1]} | {pname} | " + " | ".join(f"{t:+.2f}" for t, _ in out.values()) + " |")
    return "\n".join(lines) + "\n"
