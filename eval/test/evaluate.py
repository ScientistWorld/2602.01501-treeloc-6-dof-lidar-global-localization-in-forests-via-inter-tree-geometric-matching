#!/usr/bin/env python3
"""Hidden-test evaluator for the TreeLoc forest-localization gym.

Self-contained (standard library only; shares no code with eval/train/ and
never imports method code). For every method on disk -- every
``submissions/<name>.sh`` -- it

1. writes a fresh copy of each hidden test input (held only in
   ``eval/test/data/``) to a new temporary directory,
2. runs ``bash submissions/<name>.sh <input.json> <output.json>`` from the
   workspace root (no training happens here; methods only localize),
3. validates the output strictly and recomputes every metric from the raw
   predictions against ground truth that is loaded (and integrity-checked)
   before any method runs.

A method that crashes, times out, writes nothing, or writes an invalid output
(unknown or duplicate query, candidate outside the query's database, non-finite
number, rotation that is not a rotation, ...) gets the worst value of every
metric of that experiment. Methods listed in ``scoring/scores_train.json`` but
missing from ``submissions/`` are scored as failed too. The score file is
written atomically after all methods have finished.
Other score files in ``scoring/`` and the benchmark files are snapshotted
before any submission runs and restored afterwards if a submission changed
them.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA_DIR = HERE / "data"
SLICE = "test"
EXPERIMENTS = ("intra_session_localization", "inter_session_localization")
EXPECTED_SHA256 = {
    "intra_session_localization.input.json.gz": "9864d2079b03a223c4a453163ff0bacb4c5541b30148982f3591a0da911da0db",
    "inter_session_localization.input.json.gz": "bbcbdd4cd3d5a62fee55f939286c5eed80d34f1def37f2b8b4aaf5aefc9b07e1",
    "truth.json.gz": "e5d92cd24947e0653992f9da9f5818ff71bb91999a62b3b7b4f5096cfabb1012",
}

# Operating points (fixed here, never read from data or method output).
POSITIVE_RADIUS_M = 10.0  # retrieved frame is correct if within 10 m (xy) of the query
TE_THRESHOLD_M = 0.5  # localization success: translation error <= 0.5 m
RE_THRESHOLD_DEG = 5.0  # ... and rotation error <= 5 deg
TE_CAP_M = 10.0  # per-query cap for the all-query error metrics
RE_CAP_DEG = 180.0
ROTATION_TOLERANCE = 1e-3
TRANSLATION_LIMIT_M = 1e6

METRICS = ("R_at_1", "F1", "AUC", "R_at_50", "SR", "TE_m", "RE_deg", "TE_all_m", "RE_all_deg")
WORST = {
    "R_at_1": 0.0, "F1": 0.0, "AUC": 0.0, "R_at_50": 0.0, "SR": 0.0,
    "TE_m": TE_THRESHOLD_M, "RE_deg": RE_THRESHOLD_DEG, "TE_all_m": TE_CAP_M, "RE_all_deg": RE_CAP_DEG,
}


class InvalidOutput(Exception):
    pass


# ----------------------------------------------------------------------------- data


def read_json_gz(path: Path) -> tuple[bytes, str]:
    raw = gzip.decompress(path.read_bytes())
    return raw, hashlib.sha256(raw).hexdigest()


def quat_to_rot(qx: float, qy: float, qz: float, qw: float) -> list[list[float]]:
    n = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    qx, qy, qz, qw = qx / n, qy / n, qz / n, qw / n
    return [
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ]


def matmul3(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transpose3(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def matvec3(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def det3(a) -> float:
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


def inv3(a):
    d = det3(a)
    c = [
        [a[1][1] * a[2][2] - a[1][2] * a[2][1], a[0][2] * a[2][1] - a[0][1] * a[2][2], a[0][1] * a[1][2] - a[0][2] * a[1][1]],
        [a[1][2] * a[2][0] - a[1][0] * a[2][2], a[0][0] * a[2][2] - a[0][2] * a[2][0], a[0][2] * a[1][0] - a[0][0] * a[1][2]],
        [a[1][0] * a[2][1] - a[1][1] * a[2][0], a[0][1] * a[2][0] - a[0][0] * a[2][1], a[0][0] * a[1][1] - a[0][1] * a[1][0]],
    ]
    return [[c[i][j] / d for j in range(3)] for i in range(3)]


def nearest_rotation(a):
    """Polar factor of a near-orthonormal matrix (Newton iteration)."""
    r = [row[:] for row in a]
    for _ in range(20):
        it = transpose3(inv3(r))
        r = [[0.5 * (r[i][j] + it[i][j]) for j in range(3)] for i in range(3)]
    return r


def rotation_angle_deg(r) -> float:
    """Geodesic angle of a rotation, robust near 0 and 180 degrees."""
    s = 0.5 * math.sqrt((r[2][1] - r[1][2]) ** 2 + (r[0][2] - r[2][0]) ** 2 + (r[1][0] - r[0][1]) ** 2)
    c = 0.5 * (r[0][0] + r[1][1] + r[2][2] - 1.0)
    return math.degrees(math.atan2(s, c))


class Truth:
    def __init__(self, entry: dict):
        self.db = {k: self._pose(v) for k, v in entry["database"].items()}
        self.q = {k: self._pose(v) for k, v in entry["queries"].items()}

    @staticmethod
    def _pose(p):
        return quat_to_rot(p[3], p[4], p[5], p[6]), [p[0], p[1], p[2]]

    def relative(self, query: str, cand: str):
        """Ground-truth transform mapping query-frame points into the candidate frame."""
        rq, tq = self.q[query]
        rc, tc = self.db[cand]
        rct = transpose3(rc)
        return matmul3(rct, rq), matvec3(rct, [tq[i] - tc[i] for i in range(3)])

    def xy_distance(self, query: str, cand: str) -> float:
        tq, tc = self.q[query][1], self.db[cand][1]
        return math.hypot(tq[0] - tc[0], tq[1] - tc[1])


# ----------------------------------------------------------------------------- validation


def _finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_output(output, payload: dict) -> dict:
    if not isinstance(output, dict) or not isinstance(output.get("predictions"), list):
        raise InvalidOutput("output must be an object with a 'predictions' list")
    query_seq, db_ids = {}, {}
    for seq in payload["sequences"]:
        db_ids[seq["name"]] = {frame["id"] for frame in seq["database"]}
        for frame in seq["queries"]:
            query_seq[frame["id"]] = seq["name"]
    preds = {}
    for item in output["predictions"]:
        if not isinstance(item, dict):
            raise InvalidOutput("each prediction must be an object")
        query, cand = item.get("query"), item.get("candidate")
        if not isinstance(query, str) or query not in query_seq:
            raise InvalidOutput(f"unknown query id {query!r}")
        if query in preds:
            raise InvalidOutput(f"duplicate prediction for query {query}")
        if not isinstance(cand, str) or cand not in db_ids[query_seq[query]]:
            raise InvalidOutput(f"candidate {cand!r} for query {query} is not a database frame of its sequence")
        score = item.get("score")
        if not _finite_number(score):
            raise InvalidOutput(f"score for query {query} must be a finite number")
        rot, trans = item.get("rotation"), item.get("translation")
        if not (isinstance(rot, list) and len(rot) == 3 and all(isinstance(r, list) and len(r) == 3 for r in rot)):
            raise InvalidOutput(f"rotation for query {query} must be a 3x3 list")
        if not all(_finite_number(v) for r in rot for v in r):
            raise InvalidOutput(f"rotation for query {query} has non-finite entries")
        if not (isinstance(trans, list) and len(trans) == 3 and all(_finite_number(v) for v in trans)):
            raise InvalidOutput(f"translation for query {query} must be 3 finite numbers")
        if max(abs(v) for v in trans) > TRANSLATION_LIMIT_M:
            raise InvalidOutput(f"translation for query {query} is out of range")
        rtr = matmul3(transpose3(rot), rot)
        ortho = max(abs(rtr[i][j] - (1.0 if i == j else 0.0)) for i in range(3) for j in range(3))
        if ortho > ROTATION_TOLERANCE or abs(det3(rot) - 1.0) > ROTATION_TOLERANCE:
            raise InvalidOutput(f"rotation for query {query} is not a proper rotation matrix")
        preds[query] = (cand, float(score), nearest_rotation([[float(v) for v in r] for r in rot]), [float(v) for v in trans])
    missing = set(query_seq) - set(preds)
    if missing:
        raise InvalidOutput(f"missing predictions for {len(missing)} queries")
    return preds


# ----------------------------------------------------------------------------- metrics


def pr_metrics(correct: list[int], scores: list[float], n_queries: int) -> tuple[float, float]:
    """Max F1 and area under the precision-recall curve of the top-1 matches.

    A query counts as detected at threshold tau if its score >= tau. Precision
    is the fraction of detected queries whose top match is correct; recall is
    the number of correct detections over all evaluated queries (every
    evaluated query has a true match). Equal scores share one threshold.
    """
    if n_queries == 0 or sum(correct) == 0:
        return 0.0, 0.0
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    tp = fp = 0
    best_f1 = 0.0
    auc = 0.0
    prev_recall = 0.0
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            if correct[order[j]]:
                tp += 1
            else:
                fp += 1
            j += 1
        precision = tp / (tp + fp)
        recall = tp / n_queries
        if tp:
            best_f1 = max(best_f1, 2 * precision * recall / (precision + recall))
        auc += precision * (recall - prev_recall)
        prev_recall = recall
        i = j
    return best_f1, auc


def score_experiment(preds: dict, truth: Truth) -> tuple[dict, list]:
    queries = sorted(truth.q)
    correct, scores, details = [], [], []
    success = 0
    tp_success_te, tp_success_re = [], []
    te_all, re_all = [], []
    n_correct = 0
    for q in queries:
        cand, score, rot, trans = preds[q]
        is_correct = int(truth.xy_distance(q, cand) <= POSITIVE_RADIUS_M)
        r_gt, t_gt = truth.relative(q, cand)
        r_err = matmul3(transpose3(r_gt), rot)
        re = rotation_angle_deg(r_err)
        te = math.dist(trans, t_gt)
        ok = te <= TE_THRESHOLD_M and re <= RE_THRESHOLD_DEG
        success += ok
        n_correct += is_correct
        if ok and is_correct:
            tp_success_te.append(te)
            tp_success_re.append(re)
        te_all.append(min(te, TE_CAP_M))
        re_all.append(min(re, RE_CAP_DEG))
        correct.append(is_correct)
        scores.append(score)
        details.append({"query": q, "candidate": cand, "score": score, "correct": is_correct, "success": int(ok), "te": te, "re": re})
    n = len(queries)
    f1, auc = pr_metrics(correct, scores, n)
    metrics = {
        "R_at_1": n_correct / n,
        "F1": f1,
        "AUC": auc,
        "R_at_50": success / n,
        "SR": (len(tp_success_te) / n_correct) if n_correct else 0.0,
        "TE_m": sum(tp_success_te) / len(tp_success_te) if tp_success_te else WORST["TE_m"],
        "RE_deg": sum(tp_success_re) / len(tp_success_re) if tp_success_re else WORST["RE_deg"],
        "TE_all_m": sum(te_all) / n,
        "RE_all_deg": sum(re_all) / n,
    }
    for key, value in metrics.items():
        if not math.isfinite(value):
            raise InvalidOutput(f"metric {key} is not finite")
    return metrics, details


# ----------------------------------------------------------------------------- runner


def discover_methods(submissions_dir: Path) -> dict[str, Path | None]:
    methods: dict[str, Path | None] = {}
    if submissions_dir.is_dir():
        for path in sorted(submissions_dir.glob("*.sh")):
            methods[path.stem] = path
    train_scores = ROOT / "scoring" / "scores_train.json"
    if train_scores.is_file():
        try:
            data = json.loads(train_scores.read_text())
            for exp in data.get("experiments", {}).values():
                for name in (exp.get("results") or {}):
                    methods.setdefault(str(name), None)
        except (OSError, ValueError, AttributeError):
            pass
    return methods


def run_one(name: str, script: Path | None, exp: str, payload_bytes: bytes, payload: dict, truth: Truth, timeout: float, details_dir: Path | None):
    if script is None:
        return dict(WORST), "failed: no submissions/<name>.sh for a method scored on train"
    work = Path(tempfile.mkdtemp(prefix=f"treeloc_{SLICE}_{name}_"))
    try:
        in_path, out_path, log_path = work / "input.json", work / "output.json", work / "method.log"
        in_path.write_bytes(payload_bytes)
        start = time.time()
        with log_path.open("wb") as log:
            proc = subprocess.Popen(
                ["bash", str(script), str(in_path), str(out_path)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                env={**os.environ, "TREELOC_INPUT": str(in_path), "TREELOC_OUTPUT": str(out_path)},
            )
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, 9)
                except OSError:
                    pass
                proc.wait()
                return dict(WORST), f"failed: timeout after {timeout:.0f}s"
        elapsed = time.time() - start
        tail = log_path.read_text(errors="replace")[-1500:] if log_path.exists() else ""
        if code != 0:
            print(f"[{SLICE}] {name}/{exp} exited {code}; log tail:\n{tail}", file=sys.stderr)
            return dict(WORST), f"failed: exit code {code}"
        if not out_path.is_file():
            return dict(WORST), "failed: no output file"
        try:
            output = json.loads(out_path.read_text())
            preds = validate_output(output, payload)
            metrics, details = score_experiment(preds, truth)
        except (ValueError, InvalidOutput) as exc:
            print(f"[{SLICE}] {name}/{exp} invalid output: {exc}", file=sys.stderr)
            return dict(WORST), f"failed: invalid output ({str(exc)[:200]})"
        if details_dir is not None:
            details_dir.mkdir(parents=True, exist_ok=True)
            (details_dir / f"{name}__{exp}.json").write_text(json.dumps(details))
        print(f"[{SLICE}] {name}/{exp} ok in {elapsed:.1f}s: " + ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()), file=sys.stderr)
        return metrics, "ok"
    finally:
        shutil.rmtree(work, ignore_errors=True)



def snapshot_files(paths: list[Path]) -> dict[Path, bytes | None]:
    """Bytes of files a submission must not change (other score files, benchmark data)."""
    snap = {}
    for p in paths:
        try:
            snap[p] = p.read_bytes() if p.is_file() else None
        except OSError:
            snap[p] = None
    return snap


def restore_files(snap: dict[Path, bytes | None]) -> None:
    """Undo any change a submission made to the snapshotted files while it ran."""
    for p, content in snap.items():
        try:
            current = p.read_bytes() if p.is_file() else None
        except OSError:
            current = None
        if current == content:
            continue
        print(f"[{SLICE}] {p} was modified while submissions ran; restoring it", file=sys.stderr)
        try:
            if content is None:
                p.unlink()
            else:
                tmp = p.with_name(p.name + ".restore")
                tmp.write_bytes(content)
                os.replace(tmp, p)
        except OSError as exc:
            print(f"[{SLICE}] could not restore {p}: {exc}", file=sys.stderr)


def write_scores(path: Path, results: dict, status: dict, counts: dict) -> None:
    payload = {"experiments": {}}
    for exp in EXPERIMENTS:
        payload["experiments"][exp] = {
            "slice": SLICE,
            "query_count": counts.get(exp, 0),
            "results": {name: results[name][exp] for name in sorted(results)},
            "status": {name: status[name][exp] for name in sorted(status)},
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(tmp, path)


def main() -> int:
    submissions_dir = Path(os.environ.get("TREELOC_SUBMISSIONS_DIR", ROOT / "submissions"))
    out_path = Path(os.environ.get("TREELOC_SCORES_OUT", ROOT / "scoring" / "scores_test.json"))
    details_env = os.environ.get("TREELOC_DETAILS_DIR")
    details_dir = Path(details_env) if details_env else None
    timeout = float(os.environ.get("TREELOC_METHOD_TIMEOUT_S", "7200"))
    jobs = max(1, int(os.environ.get("TREELOC_EVAL_JOBS", "1")))

    methods = discover_methods(submissions_dir)
    if not methods:
        print("No methods found: add submissions/<name>.sh", file=sys.stderr)
    results = {name: {} for name in methods}
    status = {name: {} for name in methods}

    # Load and integrity-check inputs and truth before any method runs.
    payload_bytes, payloads, truths, counts = {}, {}, {}, {}
    integrity_error = None
    try:
        for fname, expected in EXPECTED_SHA256.items():
            raw, digest = read_json_gz(DATA_DIR / fname)
            if digest != expected:
                raise ValueError(f"{fname} sha256 {digest} != expected")
            if fname == "truth.json.gz":
                truth_all = json.loads(raw)["experiments"]
            else:
                exp = fname.split(".")[0]
                payload_bytes[exp] = raw
                payloads[exp] = json.loads(raw)
        for exp in EXPERIMENTS:
            truths[exp] = Truth(truth_all[exp])
            counts[exp] = len(truths[exp].q)
            listed = {f["id"] for s in payloads[exp]["sequences"] for f in s["queries"]}
            if listed != set(truths[exp].q):
                raise ValueError(f"{exp}: input queries do not match truth")
    except (OSError, ValueError, KeyError) as exc:
        integrity_error = str(exc)

    if integrity_error:
        print(f"[{SLICE}] test data integrity failure: {integrity_error}", file=sys.stderr)
        for name in methods:
            for exp in EXPERIMENTS:
                results[name][exp] = dict(WORST)
                status[name][exp] = "failed: test data integrity"
        write_scores(out_path, results, status, counts)
        return 1

    tasks = [(name, script, exp) for name, script in methods.items() for exp in EXPERIMENTS]

    def work(task):
        name, script, exp = task
        try:
            return task, run_one(name, script, exp, payload_bytes[exp], payloads[exp], truths[exp], timeout, details_dir)
        except Exception as exc:  # never let one method break the others
            return task, (dict(WORST), f"failed: evaluator error {type(exc).__name__}: {exc}")

    # Submissions run with the workspace as their working directory. Score
    # files other than this run's output and the benchmark files are restored
    # afterwards if a submission changed them (truth is already in memory).
    guarded = [ROOT / "scoring" / n for n in ("scores.json", "scores_train.json", "scores_test.json")]
    guarded = [p for p in guarded if p.resolve() != out_path.resolve()]
    guarded += [DATA_DIR / n for n in EXPECTED_SHA256] + [DATA_DIR / "SHA256SUMS.json"]
    snapshot = snapshot_files(guarded)
    try:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            for (name, _script, exp), (metrics, state) in pool.map(work, tasks):
                results[name][exp] = metrics
                status[name][exp] = state
    finally:
        restore_files(snapshot)

    write_scores(out_path, results, status, counts)
    print(json.dumps({exp: {n: results[n][exp] for n in sorted(results)} for exp in EXPERIMENTS}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
