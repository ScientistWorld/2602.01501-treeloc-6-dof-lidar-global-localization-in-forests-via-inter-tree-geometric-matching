#!/bin/bash
# Reproduce the gym end to end: score the reference (TreeLoc), its
# no-alignment ablation and the TDH-only baseline on the train slice and on the
# hidden test slice, then validate the workspace.
#
# The benchmark data are committed (data/train/, eval/test/data/); to rebuild
# them from the public source run scripts/download.sh on a node with internet.
set -euo pipefail
cd "$(dirname "$0")/.."
export TREELOC_EVAL_JOBS="${TREELOC_EVAL_JOBS:-3}"
bash scripts/evaluate_train.sh
cp scoring/scores_train.json scoring/scores.json
bash scripts/evaluate_test.sh
python validate.py --compare
