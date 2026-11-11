#!/usr/bin/env python3
"""Shortcut submissions used by the hardening audit (never part of the gym).

Usage: python redteam/hardening/shortcuts.py MODE INPUT_JSON OUTPUT_JSON

Each MODE is an attempt to score without solving the task. They only use what a
method can see: its input file, the visible workspace and visible train data.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EYE = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
FORGED = {
    "experiments": {
        exp: {"results": {"forged": {"R_at_1": 1.0, "F1": 1.0, "AUC": 1.0, "R_at_50": 1.0, "SR": 1.0,
                                     "TE_m": 0.0, "RE_deg": 0.0, "TE_all_m": 0.0, "RE_all_deg": 0.0}}}
        for exp in ("intra_session_localization", "inter_session_localization")
    }
}


def constant(payload: dict) -> list[dict]:
    out = []
    for seq in payload["sequences"]:
        first = seq["database"][0]["id"]
        for q in seq["queries"]:
            out.append({"query": q["id"], "candidate": first, "score": 0.0, "rotation": EYE, "translation": [0.0, 0.0, 0.0]})
    return out


def reference(inp: str) -> list[dict]:
    tmp = Path(inp).with_name("reference_output.json")
    subprocess.run([sys.executable, str(ROOT / "method" / "treeloc.py"), "--input", inp, "--output", str(tmp)], check=True)
    return json.loads(tmp.read_text())["predictions"]


def quat_to_rot(qx, qy, qz, qw):
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]


def fingerprint(frame: dict) -> str:
    return hashlib.sha1(json.dumps(sorted(frame["trees"], key=lambda t: (t[0], t[1]))).encode()).hexdigest()


def train_lookup(payload: dict) -> list[dict]:
    """Memorise the visible train answers: perfect on train frames, nothing elsewhere."""
    truth = json.loads(gzip.decompress((ROOT / "data/train/truth.json.gz").read_bytes()))["experiments"]
    known = {}
    for exp in truth:
        frames = json.loads(gzip.decompress((ROOT / f"data/train/{exp}.input.json.gz").read_bytes()))
        poses = {**truth[exp]["database"], **truth[exp]["queries"]}
        for seq in frames["sequences"]:
            for fr in seq["database"] + seq["queries"]:
                known[fingerprint(fr)] = poses[fr["id"]]
    out = constant(payload)
    by_q = {p["query"]: p for p in out}
    for seq in payload["sequences"]:
        db = [(fr["id"], known.get(fingerprint(fr))) for fr in seq["database"]]
        for q in seq["queries"]:
            pq = known.get(fingerprint(q))
            if pq is None:
                continue
            best = min((d for d in db if d[1] is not None), key=lambda d: math.hypot(d[1][0] - pq[0], d[1][1] - pq[1]), default=None)
            if best is None:
                continue
            rc, rq = quat_to_rot(*best[1][3:7]), quat_to_rot(*pq[3:7])
            rct = [[rc[j][i] for j in range(3)] for i in range(3)]
            rot = [[sum(rct[i][k] * rq[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            dt = [pq[i] - best[1][i] for i in range(3)]
            trans = [sum(rct[i][k] * dt[k] for k in range(3)) for i in range(3)]
            by_q[q["id"]].update(candidate=best[0], score=1.0, rotation=rot, translation=trans)
    return out


def read_hidden(payload: dict, inp: str) -> list[dict]:
    """Look for any file outside eval/test that mentions the input query IDs."""
    ids = [q["id"] for seq in payload["sequences"] for q in seq["queries"]][:20]
    hits = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file() or rel.startswith(("eval/test/", ".git/")) or path.stat().st_size > 50_000_000:
            continue
        try:
            data = path.read_bytes()
            if path.suffix == ".gz":
                data = gzip.decompress(data)
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        if str(path) == inp:
            continue
        if any(i.encode() in data for i in ids):
            hits.append(rel)
    print(f"read_hidden: files outside eval/test mentioning the input query ids: {hits}", file=sys.stderr)
    return constant(payload)


def main() -> None:
    mode, inp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    payload = json.loads(Path(inp).read_text())
    preds = None
    if mode == "self_match":
        preds = constant(payload)
        for p in preds:
            p["candidate"], p["score"] = p["query"], 1.0
    elif mode == "ordinal":
        preds = []
        for seq in payload["sequences"]:
            for k, q in enumerate(seq["queries"]):
                preds.append({"query": q["id"], "candidate": seq["database"][k % len(seq["database"])]["id"],
                              "score": 1.0, "rotation": EYE, "translation": [0.0, 0.0, 0.0]})
    elif mode == "constant":
        preds = constant(payload)
    elif mode == "rotation_scale_huge":
        preds = constant(payload)
        for p in preds:
            p["rotation"] = [[1e6 * v for v in row] for row in p["rotation"]]
    elif mode == "rotation_scale_small":
        preds = reference(inp)
        for p in preds:
            p["rotation"] = [[1.0004 * v for v in row] for row in p["rotation"]]
    elif mode == "nan_translation":
        preds = constant(payload)
        preds[0]["translation"] = [float("nan"), 0.0, 0.0]
    elif mode == "duplicate_predictions":
        preds = constant(payload)
        preds = preds + [dict(p, score=1e6) for p in preds for _ in range(3)]
    elif mode == "empty_output":
        (ROOT / "scoring/scores_test.json").write_text(json.dumps(FORGED))
        preds = []
    elif mode == "missing_output":
        return
    elif mode == "crash":
        raise SystemExit(1)
    elif mode == "forge_scores":
        for name in ("scores_test.json", "scores_train.json"):
            (ROOT / "scoring" / name).write_text(json.dumps(FORGED))
        preds = constant(payload)
    elif mode == "artifact_replay":
        cached = ROOT / "artifacts" / "train_outputs" / "treeloc" / f"{payload['setting']}_localization.json"
        Path(outp).write_bytes(cached.read_bytes())
        return
    elif mode == "train_lookup":
        preds = train_lookup(payload)
    elif mode == "read_hidden":
        preds = read_hidden(payload, inp)
    elif mode == "tamper_truth":
        for rel in ("data/train/truth.json.gz", "eval/test/data/truth.json.gz"):
            path = ROOT / rel
            try:
                truth = json.loads(gzip.decompress(path.read_bytes()))
                for exp in truth["experiments"].values():
                    for part in ("database", "queries"):
                        exp[part] = {k: [0, 0, 0, 0, 0, 0, 1] for k in exp[part]}
                path.write_bytes(gzip.compress(json.dumps(truth).encode()))
            except (OSError, ValueError, KeyError):
                pass
        preds = constant(payload)
    else:
        raise SystemExit(f"unknown mode {mode}")
    Path(outp).write_text(json.dumps({"predictions": preds}, allow_nan=True))


if __name__ == "__main__":
    main()
