#!/usr/bin/env python3
"""Rescore saved train-slice outputs (artifacts/train_outputs/<name>/<exp>.json)
against the current train truth, using the train evaluator's own validation and
metric code. Used by the hardening audit when only the truth changed (the
predictions of an unchanged method on unchanged inputs are identical).

Usage: python redteam/hardening/rescore_saved.py OUT_JSON NAME [NAME ...]
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("train_eval", ROOT / "eval" / "train" / "evaluate.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def main() -> None:
    out_path, names = Path(sys.argv[1]), sys.argv[2:]
    truth = json.loads(gzip.decompress((ev.DATA_DIR / "truth.json.gz").read_bytes()))["experiments"]
    result = {"experiments": {}}
    for exp in ev.EXPERIMENTS:
        payload = json.loads(gzip.decompress((ev.DATA_DIR / f"{exp}.input.json.gz").read_bytes()))
        t = ev.Truth(truth[exp])
        res, status = {}, {}
        for name in names:
            path = ROOT / "artifacts" / "train_outputs" / name / f"{exp}.json"
            try:
                metrics, _ = ev.score_experiment(ev.validate_output(json.loads(path.read_text()), payload), t)
                res[name], status[name] = metrics, "ok (rescored saved output)"
            except (OSError, ValueError, ev.InvalidOutput) as exc:
                res[name], status[name] = dict(ev.WORST), f"failed: {exc}"
            print(exp, name, status[name], {k: round(v, 4) for k, v in res[name].items()})
        result["experiments"][exp] = {"slice": "train", "query_count": len(t.q), "results": res, "status": status}
    out_path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
