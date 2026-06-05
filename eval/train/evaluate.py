#!/usr/bin/env python3
"""Train-slice evaluation for TreeLoc-format outputs.

This evaluator is method-agnostic: it only reads result artifacts with
predictions and pair scores. It intentionally does not import from method/.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

Matrix4 = list[list[float]]
Matrix3 = list[list[float]]

SLICE_NAME = "train"
EXPERIMENT_NAME = "synthetic_forest_localization"
QUERY_IDS = {
    "query_002",
    "query_005",
    "query_008",
    "query_010",
    "query_011",
    "query_012",
    "query_014",
    "query_015",
    "query_018",
    "query_019",
    "query_020",
    "query_022",
    "query_027",
    "query_028",
    "query_029",
    "query_030",
    "query_031",
    "query_032",
    "query_034",
    "query_035",
    "query_039",
    "query_043",
    "query_047",
    "query_053",
}


def eye4() -> Matrix4:
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def inv_pose(t: Matrix4) -> Matrix4:
    r_t = [[t[j][i] for j in range(3)] for i in range(3)]
    trans = [t[i][3] for i in range(3)]
    out = eye4()
    for i in range(3):
        for j in range(3):
            out[i][j] = r_t[i][j]
        out[i][3] = -sum(r_t[i][j] * trans[j] for j in range(3))
    return out


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
    q_xyz = [poses[q][i][3] for i in range(3)]
    c_xyz = [poses[c][i][3] for i in range(3)]
    return int(math.dist(q_xyz, c_xyz) <= threshold)


def rotation_delta(a: Matrix4, b: Matrix4) -> Matrix3:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def selected_query_ids(data: dict) -> list[str]:
    available = {scene["name"] for scene in data["query"]}
    missing = sorted(QUERY_IDS - available)
    if missing:
        raise ValueError(f"{SLICE_NAME} slice query IDs missing from data: {missing}")
    return sorted(QUERY_IDS)


def validate_complete_artifact(data: dict, result: dict, result_path: Path) -> None:
    expected_queries = {scene["name"] for scene in data["query"]}
    expected_candidates = {scene["name"] for scene in data["database"]}
    predictions = result.get("predictions", [])
    pair_scores = result.get("pair_scores", [])
    if not isinstance(predictions, list) or not isinstance(pair_scores, list):
        raise ValueError(f"{result_path}: expected list-valued predictions and pair_scores")

    prediction_queries = [str(pred.get("query")) for pred in predictions]
    prediction_set = set(prediction_queries)
    missing_predictions = sorted(expected_queries - prediction_set)
    duplicate_predictions = sorted({q for q in prediction_queries if prediction_queries.count(q) > 1})
    if missing_predictions or duplicate_predictions:
        raise ValueError(
            f"{result_path}: predictions must contain exactly one top prediction per query; "
            f"missing={missing_predictions}, duplicates={duplicate_predictions}"
        )

    pair_candidates_by_query = {query: set() for query in expected_queries}
    for pair in pair_scores:
        query = str(pair.get("query"))
        candidate = str(pair.get("candidate"))
        if query in pair_candidates_by_query:
            pair_candidates_by_query[query].add(candidate)
    incomplete = {
        query: sorted(expected_candidates - candidates)
        for query, candidates in pair_candidates_by_query.items()
        if candidates != expected_candidates
    }
    if incomplete:
        examples = {query: missing[:5] for query, missing in list(incomplete.items())[:3]}
        raise ValueError(f"{result_path}: pair_scores must cover every database candidate for every query; {examples}")


def evaluate_one(data: dict, result_path: Path) -> dict[str, float]:
    result = json.loads(result_path.read_text())
    validate_complete_artifact(data, result, result_path)
    slice_queries = set(selected_query_ids(data))
    poses = load_poses(data)
    positive_dist = float(data.get("positive_distance_m", 10.0))
    te_thresh = float(data.get("localization_translation_threshold_m", 0.5))
    re_thresh = float(data.get("localization_rotation_threshold_deg", 5.0))
    te_miss_penalty = float(data.get("localization_translation_miss_penalty_m", positive_dist))
    re_miss_penalty = float(data.get("localization_rotation_miss_penalty_deg", 180.0))

    pair_scores = [p for p in result["pair_scores"] if p["query"] in slice_queries]
    labels = [pair_label(poses, p["query"], p["candidate"], positive_dist) for p in pair_scores]
    scores = [float(p["score"]) for p in pair_scores]

    predictions_by_query = {p["query"]: p for p in result["predictions"] if p["query"] in slice_queries}
    r_at_1_hits = 0
    loc_success = 0
    true_positive_top = 0
    te_values, re_values = [], []
    te_all_values, re_all_values = [], []
    for query in selected_query_ids(data):
        pred = predictions_by_query[query]
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

    n_queries = len(slice_queries)
    return {
        "R_at_1": r_at_1_hits / n_queries,
        "F1": max_f1(labels, scores),
        "AUC": average_precision(labels, scores),
        "R_at_50": loc_success / n_queries,
        "SR": loc_success / max(1, true_positive_top),
        "TE_m": sum(te_values) / len(te_values) if te_values else 999.0,
        "RE_deg": sum(re_values) / len(re_values) if re_values else 999.0,
        "TE_all_m": sum(te_all_values) / len(te_all_values),
        "RE_all_deg": sum(re_all_values) / len(re_all_values),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/forest_scenes.json")
    parser.add_argument("--result", action="append", required=True, help="method_name:path/to/results.json")
    parser.add_argument("--output", default="scoring/scores_train.json")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text())
    results = {}
    artifact_paths = {}
    for item in args.result:
        name, path = item.split(":", 1)
        results[name] = evaluate_one(data, Path(path))
        artifact_paths[name] = path

    payload = {
        "experiments": {
            EXPERIMENT_NAME: {
                "slice": SLICE_NAME,
                "query_count": len(selected_query_ids(data)),
                "artifact_paths": artifact_paths,
                "results": results,
            }
        }
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
