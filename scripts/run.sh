#!/bin/bash
# Regenerate the deterministic benchmark and all standard TreeLoc-format
# artifacts, then score the formal and split evaluation suites.

set -euo pipefail

cd /home/user

mkdir -p artifacts data scoring

python data/generate_synthetic_forest.py --output data/forest_scenes.json --seed 11
python baseline/tdh_baseline.py \
  --data data/forest_scenes.json \
  --output artifacts/tdh_baseline_results.json
python method/treeloc.py \
  --data data/forest_scenes.json \
  --output artifacts/treeloc_results.json
python method/treeloc.py \
  --data data/forest_scenes.json \
  --output artifacts/treeloc_no_alignment_results.json \
  --no-alignment

bash scripts/evaluate.sh
bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh

python validate.py --compare
python validate.py --post-reproducer
