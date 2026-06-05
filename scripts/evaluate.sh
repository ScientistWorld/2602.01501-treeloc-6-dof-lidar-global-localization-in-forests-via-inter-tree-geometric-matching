#!/bin/bash
# Evaluation script — the standard way to evaluate work in this environment.
#
# This script must be SELF-CONTAINED using only code in eval/.
# Do NOT import from method/ — evaluate.sh must work even when the
# paper's method code is hidden from a scientist agent.
#
# Design it so that anyone following the same output format can run
# this script to evaluate their results.
#
# OUTPUT CONTRACT: This script MUST write scoring/scores.json containing
# a JSON dict nested by experiment, e.g.:
#   {"imagenet_classification": {"top1_accuracy": 82.1, "top5_accuracy": 94.8}}
# Experiment and metric names must match the keys in scoring/reference.json.
# This file is read by the system for automated comparison.
#
# Example usage:
#   bash scripts/evaluate.sh
#   bash scripts/evaluate.sh artifacts/my_results.json
#
# Called from run.sh after training, or independently.

set -e

cd /home/user

mkdir -p scoring

if [ ! -f data/forest_scenes.json ]; then
  python data/generate_synthetic_forest.py --output data/forest_scenes.json --seed 11
fi

RESULT_ARGS=()
add_result_arg() {
  local item="$1"
  local name
  local path
  if [[ "$item" == *:* ]]; then
    name="${item%%:*}"
    path="${item#*:}"
  else
    path="$item"
    name="$(basename "$path")"
    name="${name%.json}"
    name="${name%_results}"
  fi
  RESULT_ARGS+=(--result "${name}:${path}")
}

if [ "$#" -gt 0 ]; then
  for item in "$@"; do
    add_result_arg "$item"
  done
else
  if [ -f artifacts/treeloc_results.json ]; then
    RESULT_ARGS+=(--result treeloc:artifacts/treeloc_results.json)
  fi
  if [ -f artifacts/treeloc_no_alignment_results.json ]; then
    RESULT_ARGS+=(--result treeloc_no_alignment:artifacts/treeloc_no_alignment_results.json)
  fi
  if [ -f artifacts/tdh_baseline_results.json ]; then
    RESULT_ARGS+=(--result tdh_baseline:artifacts/tdh_baseline_results.json)
  fi
fi

if [ "${#RESULT_ARGS[@]}" -eq 0 ]; then
  echo "No result artifacts found. Run scripts/method.sh or scripts/baseline.sh first." >&2
  exit 1
fi

python eval/evaluate_treeloc.py \
  --data data/forest_scenes.json \
  "${RESULT_ARGS[@]}" \
  --output scoring/scores.json \
  --aux-output artifacts/auxiliary_metrics.json
