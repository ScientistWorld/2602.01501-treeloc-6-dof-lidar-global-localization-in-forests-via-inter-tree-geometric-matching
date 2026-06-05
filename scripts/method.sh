#!/bin/bash
# Run the paper's proposed method.
#
# This script trains/runs the paper's method using code in method/.
#
# Usage:
#   bash scripts/method.sh

set -e

cd /home/user

mkdir -p artifacts data

if [ ! -f data/forest_scenes.json ]; then
  python data/generate_synthetic_forest.py --output data/forest_scenes.json --seed 11
fi

python method/treeloc.py \
  --data data/forest_scenes.json \
  --output artifacts/treeloc_results.json

python method/treeloc.py \
  --data data/forest_scenes.json \
  --output artifacts/treeloc_no_alignment_results.json \
  --no-alignment

bash scripts/evaluate.sh
