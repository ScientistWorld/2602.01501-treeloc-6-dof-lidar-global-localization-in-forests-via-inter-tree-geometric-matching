#!/bin/bash
# Run the simple baseline (TDH-only global retrieval) on the visible train
# slice and score it.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/evaluate_train.sh tdh_baseline
