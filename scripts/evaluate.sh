#!/bin/bash
# Standard evaluation entry point: scores every submissions/<name>.sh on the
# visible train slice (see scripts/evaluate_train.sh) and mirrors the result to
# scoring/scores.json. Evaluation code lives only in eval/ and never imports
# method code; any method that follows the submission interface can be scored.
#
# Usage: bash scripts/evaluate.sh [name ...]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p scoring
python eval/train/evaluate.py --output scoring/scores.json "$@"
