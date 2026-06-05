#!/bin/bash
# Evaluate visible train slice of TreeLoc-format result artifacts.
#
# Usage:
#   bash scripts/evaluate_train.sh
#   bash scripts/evaluate_train.sh artifacts/my_results.json
#   bash scripts/evaluate_train.sh my_method:artifacts/my_results.json

set -euo pipefail

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
  shopt -s nullglob
  for path in artifacts/*_results.json; do
    add_result_arg "$path"
  done
  shopt -u nullglob
fi

if [ "${#RESULT_ARGS[@]}" -eq 0 ]; then
  echo "No result artifacts found. Run a method first or pass result paths explicitly." >&2
  exit 1
fi

python eval/train/evaluate.py \
  --data data/forest_scenes.json \
  "${RESULT_ARGS[@]}" \
  --output scoring/scores_train.json
