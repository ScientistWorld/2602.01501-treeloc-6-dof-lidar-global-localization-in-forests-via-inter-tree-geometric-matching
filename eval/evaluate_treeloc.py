#!/usr/bin/env python3
"""Evaluate TreeLoc-format outputs without importing method code."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def inv_pose(t: np.ndarray) -> np.ndarray:
    out = np.eye(4)
    out[:3, :3] = t[:3, :3].T
    out[:3, 3] = -out[:3, :3] @ t[:3, 3]
    return out


def yaw_matrix(yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    r = np.eye(3)
    r[:2, :2] = [[c, -s], [s, c]]
    return r


def rot_angle_deg(r: np.ndarray) -> float:
    value = max(-1.0, min(1.0, (np.trace(r) - 1.0) / 2.0))
    return math.degrees(math.acos(value))


def average_precision(labels: list[int], scores: list[float]) -> float:
    order = np.argsort(-np.array(scores))
    labels_sorted = np.array(labels)[order]
    positives = int(labels_sorted.sum())
    if positives == 0:
        return 0.0
    tp = 0
    precisions = []
    for i, label in enumerate(labels_sorted, start=1):
        if label:
            tp += 1
            precisions.append(tp / i)
    return float(np.mean(precisions))


def max_f1(labels: list[int], scores: list[float]) -> float:
    order = np.argsort(-np.array(scores))
    labels_sorted = np.array(labels)[order]
    positives = int(labels_sorted.sum())
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


def load_poses(data: dict) -> dict[str, np.ndarray]:
    poses = {}
    for split in ("query", "database"):
        for scene in data[split]:
            poses[scene["name"]] = np.array(scene["pose"], dtype=float)
    return poses


def pair_label(poses: dict[str, np.ndarray], q: str, c: str, threshold: float) -> int:
    return int(np.linalg.norm(poses[q][:3, 3] - poses[c][:3, 3]) <= threshold)


def evaluate_one(data: dict, result_path: Path) -> dict:
    result = json.loads(result_path.read_text())
    poses = load_poses(data)
    positive_dist = float(data.get("positive_distance_m", 10.0))
    te_thresh = float(data.get("localization_translation_threshold_m", 0.5))
    re_thresh = float(data.get("localization_rotation_threshold_deg", 5.0))

    labels = [pair_label(poses, p["query"], p["candidate"], positive_dist) for p in result["pair_scores"]]
    scores = [float(p["score"]) for p in result["pair_scores"]]

    r_at_1_hits = 0
    loc_success = 0
    true_positive_top = 0
    te_values, re_values = [], []
    for pred in result["predictions"]:
        q, c = pred["query"], pred["candidate"]
        is_positive = pair_label(poses, q, c, positive_dist)
        r_at_1_hits += is_positive
        if not is_positive:
            continue
        true_positive_top += 1
        gt = inv_pose(poses[c]) @ poses[q]
        est = np.eye(4)
        pose_est = pred["estimated_query_to_candidate"]
        if "rotation" in pose_est:
            est[:3, :3] = np.array(pose_est["rotation"], dtype=float)
        else:
            est[:3, :3] = yaw_matrix(float(pose_est["yaw"]))
        est[:3, 3] = np.array(pose_est["translation"], dtype=float)
        delta = inv_pose(gt) @ est
        te = float(np.linalg.norm(delta[:3, 3]))
        re = rot_angle_deg(delta[:3, :3])
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
        "TE_m": float(np.mean(te_values)) if te_values else 999.0,
        "RE_deg": float(np.mean(re_values)) if re_values else 999.0,
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
    ablation_experiment = {"results": {}}
    aux_results = {}
    for item in args.result:
        name, path = item.split(":", 1)
        metrics = evaluate_one(data, Path(path))
        if name == "treeloc":
            main_experiment["results"][name] = metrics
        elif name not in {"treeloc_no_alignment"}:
            aux_results[name] = metrics
        if name in {"treeloc", "treeloc_no_alignment"}:
            ablation_experiment["results"][name] = {
                "R_at_1": metrics["R_at_1"],
                "F1": metrics["F1"],
                "R_at_50": metrics["R_at_50"],
            }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    experiments = {}
    if main_experiment["results"]:
        experiments["synthetic_forest_localization"] = main_experiment
    if len(ablation_experiment["results"]) == 2:
        experiments["synthetic_alignment_ablation"] = ablation_experiment
    payload = {"experiments": experiments}
    out.write_text(json.dumps(payload, indent=2))
    if args.aux_output and aux_results:
        aux = Path(args.aux_output)
        aux.parent.mkdir(parents=True, exist_ok=True)
        aux.write_text(json.dumps({"results": aux_results}, indent=2))
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
