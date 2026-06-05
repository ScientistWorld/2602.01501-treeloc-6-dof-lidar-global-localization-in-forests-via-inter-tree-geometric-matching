#!/bin/bash
# Reproduce the paper's results end-to-end.
#
# This script runs inside the compute container and should call
# scripts/baseline.sh and scripts/method.sh to run baselines and
# the paper's method, each of which calls scripts/evaluate.sh.
#
# Assumes:
#   - Container is built (environment/container.sif)
#   - Data and models are downloaded (via scripts/download.sh)
#   - Working directory is /home/user
#
# This is the "gold standard" reproduction — 
# You do not need to run this, but keep this in good shape
# so other agents can easily run a full loop of reproduction and get the paper's numbers.

set -e

cd /home/user

mkdir -p artifacts data
python data/generate_synthetic_forest.py --output data/forest_scenes.json --seed 11
python baseline/tdh_baseline.py --data data/forest_scenes.json --output artifacts/tdh_baseline_results.json
python method/treeloc.py --data data/forest_scenes.json --output artifacts/treeloc_results.json
bash scripts/evaluate.sh
