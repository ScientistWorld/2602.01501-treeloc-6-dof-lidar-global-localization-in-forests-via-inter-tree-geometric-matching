#!/usr/bin/env python3
"""Does the paper's growing-database intra protocol (variant intra_SP) leak time order?

In intra_SP every block's database is "all frames before s_j", so the same scene
appears in several blocks' databases; matching contents across blocks reveals
which time block each database scene belongs to. This counts, per block, how
many queries have all / some / none of their true positives (<= 10 m) in the
most recent database block, i.e. how much a method that used block membership
could gain. Reads the gitignored exploration inputs (data/downloads/explore).
"""
import gzip, json, math, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
V = ROOT / "data/downloads/explore/intra_SP"
inp = json.loads(gzip.decompress((V / "input.json.gz").read_bytes()))
tr = json.loads(gzip.decompress((V / "truth.json.gz").read_bytes()))["experiments"]["intra_session_localization"]
src = tr["source"]
prev = {"seq_s0": 0, "seq_s2": 300, "seq_s3": 450, "seq_s4": 600, "seq_s5": 750}
out = collections.Counter()
for s in inp["sequences"]:
    db = [(f["id"], tr["database"][f["id"]]) for f in s["database"]]
    for q in s["queries"]:
        qp = tr["queries"][q["id"]]
        near = [int(src[i].split(":")[1]) for i, p in db if math.hypot(p[0] - qp[0], p[1] - qp[1]) <= 10]
        rec = [n >= prev[s["name"]] for n in near]
        out[(s["name"], "all" if all(rec) else ("some" if any(rec) else "none"))] += 1
for k in sorted(out):
    print(f"{k[0]}: positives in most recent block = {k[1]}: {out[k]} queries")
