#!/bin/bash
# Run the paper's method (TreeLoc, submissions/treeloc.sh) on the visible train
# slice and score it. The hidden test runs the same submission script itself.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/evaluate_train.sh treeloc treeloc_no_alignment
