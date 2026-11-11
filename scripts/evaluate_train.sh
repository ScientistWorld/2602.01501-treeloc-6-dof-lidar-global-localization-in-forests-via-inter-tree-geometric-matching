#!/bin/bash
# Train-slice evaluation on the visible data in data/train/. Scores every
# submissions/<name>.sh (or only the names given as arguments) through the same
# interface as the hidden test and writes scoring/scores_train.json. Raw outputs
# and per-query diagnostics are kept under artifacts/train_outputs/<name>/.
#
# Usage: bash scripts/evaluate_train.sh [name ...]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p scoring
python eval/train/evaluate.py --output scoring/scores_train.json "$@"
