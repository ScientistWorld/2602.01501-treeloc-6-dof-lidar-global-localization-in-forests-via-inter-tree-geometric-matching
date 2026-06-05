#!/bin/bash
# Download all data and models needed for this environment.
#
# Run on a node with internet access BEFORE building the container
# or submitting compute jobs.
#
# This script should be idempotent — safe to run multiple times.
# It should skip files that already exist.
#
# Update the storage estimate below as you add downloads.
#
# Estimated total download size: 0 GB
# Estimated disk usage after extraction: <5 MB
#
# This scaled reproduction has no external assets. The script writes the
# deterministic benchmark to workspace-local data/ paths for portability.

set -e

cd "$(dirname "$0")/.."

# No external downloads are required for this scaled reproduction. The public
# robotics datasets are large and require raw LiDAR/tree-extraction pipelines,
# so this gym uses a deterministic tree-inventory generator in data/.
python data/generate_synthetic_forest.py --output data/forest_scenes.json --seed 11
