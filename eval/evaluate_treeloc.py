#!/usr/bin/env python3
"""Evaluate TreeLoc-format outputs without importing method code."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

Matrix4 = list[list[float]]
Matrix3 = list[list[float]]


def inv_pose(t: Matrix4) -> Matrix4:
    r_t = [[t[j][i] for j in range(3)] for i in range(3)]
    trans = [t[i][3] for i in range(3)]
    out = eye4()
    for i in range(3):
        for j in range(3):
            out[i][j] = r_t[i][j]
        out[i][3] = -sum(r_t[i][j] * trans[j] for j in range(3))
    return out


def eye4() -> Matrix4:
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def matmul4(a: Matrix4, b: Matrix4) -> Matrix4:
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def yaw_matrix(yaw: float) -> Matrix3:
    c, s = math.cos(yaw), math.sin(yaw)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


def rot_angle_deg(r: Matrix3) -> float:
    value = max(-1.0, min(1.0, (sum(r[i][i] for i in range(3)) - 1.0) / 2.0))
    return math.degrees(math.acos(value))


def average_precision(labels: list[int], scores: list[float]) -> float:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    labels_sorted = [labels[i] for i in order]
    positives = sum(labels_sorted)
    if positives == 0:
        return 0.0
    tp = 0
    precisions = []
    for i, label in enumerate(labels_sorted, start=1):
        if label:
            tp += 1
            precisions.append(tp / i)
    return sum(precisions) / len(precisions)


def max_f1(labels: list[int], scores: list[float]) -> float:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    labels_sorted = [labels[i] for i in order]
    positives = sum(labels_sorted)
    if positives == 0:
        return 0.0
    tp = fp = 0
    best = 0.0
    for label in labels_sorted:
        if label:
            tp += 1
        else:
            fp += 1
        fn = positives - tp
        denom = 2 * tp + fp + fn
        best = max(best, 0.0 if denom == 0 else 2 * tp / denom)
    return float(best)


def load_poses(data: dict) -> dict[str, Matrix4]:
    poses = {}
    for split in ("query", "database"):
        for scene in data[split]:
            poses[scene["name"]] = [[float(v) for v in row] for row in scene["pose"]]
    return poses


def pair_label(poses: dict[str, Matrix4], q: str, c: str, threshold: float) -> int:
    return int(math.dist([poses[q][i][3] for i in range(3)], [poses[c][i][3] for i in range(3)]) <= threshold)


def rotation_delta(a: Matrix4, b: Matrix4) -> Matrix3:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def evaluate_one(data: dict, result_path: Path) -> dict:
    result = json.loads(result_path.read_text())
    poses = load_poses(data)
    positive_dist = float(data.get("positive_distance_m", 10.0))
    te_thresh = float(data.get("localization_translation_threshold_m", 0.5))
    re_thresh = float(data.get("localization_rotation_threshold_deg", 5.0))
    te_miss_penalty = float(data.get("localization_translation_miss_penalty_m", positive_dist))
    re_miss_penalty = float(data.get("localization_rotation_miss_penalty_deg", 180.0))

    labels = [pair_label(poses, p["query"], p["candidate"], positive_dist) for p in result["pair_scores"]]
    scores = [float(p["score"]) for p in result["pair_scores"]]

    r_at_1_hits = 0
    loc_success = 0
    true_positive_top = 0
    te_values, re_values = [], []
    te_all_values, re_all_values = [], []
    for pred in result["predictions"]:
        q, c = pred["query"], pred["candidate"]
        is_positive = pair_label(poses, q, c, positive_dist)
        r_at_1_hits += is_positive
        if not is_positive:
            te_all_values.append(te_miss_penalty)
            re_all_values.append(re_miss_penalty)
            continue
        true_positive_top += 1
        gt = matmul4(inv_pose(poses[c]), poses[q])
        est = eye4()
        pose_est = pred["estimated_query_to_candidate"]
        if "rotation" in pose_est:
            rotation = pose_est["rotation"]
        else:
            rotation = yaw_matrix(float(pose_est["yaw"]))
        for i in range(3):
            for j in range(3):
                est[i][j] = float(rotation[i][j])
            est[i][3] = float(pose_est["translation"][i])
        delta = matmul4(inv_pose(gt), est)
        te = math.sqrt(sum(delta[i][3] ** 2 for i in range(3)))
        re = rot_angle_deg(rotation_delta(inv_pose(gt), est))
        te_all_values.append(te)
        re_all_values.append(re)
        if te <= te_thresh and re <= re_thresh:
            loc_success += 1
            te_values.append(te)
            re_values.append(re)

    n_queries = max(1, len(result["predictions"]))
    return {
        "R_at_1": r_at_1_hits / n_queries,
        "F1": max_f1(labels, scores),
        "AUC": average_precision(labels, scores),
        "R_at_50": loc_success / n_queries,
        "SR": loc_success / max(1, true_positive_top),
        "TE_m": sum(te_values) / len(te_values) if te_values else 999.0,
        "RE_deg": sum(re_values) / len(re_values) if re_values else 999.0,
        "TE_all_m": sum(te_all_values) / len(te_all_values) if te_all_values else te_miss_penalty,
        "RE_all_deg": sum(re_all_values) / len(re_all_values) if re_all_values else re_miss_penalty,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/forest_scenes.json")
    parser.add_argument("--result", action="append", required=True, help="method_name:path/to/results.json")
    parser.add_argument("--output", default="scoring/scores.json")
    parser.add_argument(
        "--aux-output",
        default=None,
        help="Optional path for metrics of result names that are not part of reference.json.",
    )
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text())
    main_experiment = {"results": {}}
    aux_results = {}
    for item in args.result:
        name, path = item.split(":", 1)
        metrics = evaluate_one(data, Path(path))
        if name == "treeloc":
            main_experiment["results"][name] = metrics
        else:
            aux_results[name] = metrics
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    experiments = {}
    if main_experiment["results"]:
        experiments["synthetic_forest_localization"] = main_experiment
    payload = {"experiments": experiments}
    out.write_text(json.dumps(payload, indent=2))
    if args.aux_output and aux_results:
        aux = Path(args.aux_output)
        aux.parent.mkdir(parents=True, exist_ok=True)
        aux.write_text(json.dumps({"results": aux_results}, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
