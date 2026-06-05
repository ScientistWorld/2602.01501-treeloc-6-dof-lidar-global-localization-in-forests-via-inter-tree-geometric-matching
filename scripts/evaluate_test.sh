#!/bin/bash
# Evaluate held-out test slice of TreeLoc-format result artifacts.
#
# By default, this scores the exact method names present in
# scoring/scores_train.json. If train scores are absent, it falls back to
# enumerating artifacts/*_results.json for standalone use.
#
# Usage:
#   bash scripts/evaluate_test.sh
#   bash scripts/evaluate_test.sh artifacts/my_results.json
#   bash scripts/evaluate_test.sh my_method:artifacts/my_results.json

set -euo pipefail

cd /home/user

mkdir -p scoring

if [ ! -f data/forest_scenes.json ]; then
  python data/generate_synthetic_forest.py --output data/forest_scenes.json --seed 11
fi

RESULT_ARGS=()
RESULT_NAMES=()

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
  RESULT_NAMES+=("$name")
  RESULT_ARGS+=(--result "${name}:${path}")
}

read_train_results() {
  python - <<'PY'
import json
from pathlib import Path

path = Path("scoring/scores_train.json")
data = json.loads(path.read_text())
exp = data.get("experiments", {}).get("synthetic_forest_localization", {})
artifact_paths = exp.get("artifact_paths", {})
for name in sorted(exp.get("results", {})):
    print(f"{name}\t{artifact_paths.get(name, '')}")
PY
}

if [ "$#" -gt 0 ]; then
  for item in "$@"; do
    add_result_arg "$item"
  done
  if [ -f scoring/scores_train.json ]; then
    mapfile -t TRAIN_METHODS < <(read_train_results | cut -f 1)
    for method in "${TRAIN_METHODS[@]}"; do
      found=false
      for name in "${RESULT_NAMES[@]}"; do
        if [ "$name" = "$method" ]; then
          found=true
          break
        fi
      done
      if [ "$found" = false ]; then
        echo "Explicit test arguments omit train-scored method '${method}'." >&2
        exit 1
      fi
    done
  fi
elif [ -f scoring/scores_train.json ]; then
  while IFS=$'\t' read -r method recorded_path; do
    path="$recorded_path"
    if [ -z "$path" ]; then
      path="artifacts/${method}_results.json"
    fi
    if [ ! -f "$path" ]; then
      echo "Missing result artifact for train-scored method '${method}': ${path}" >&2
      exit 1
    fi
    add_result_arg "${method}:${path}"
  done < <(read_train_results)
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

python eval/test/evaluate.py \
  --data data/forest_scenes.json \
  "${RESULT_ARGS[@]}" \
  --output scoring/scores_test.json
