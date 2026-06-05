#!/bin/bash
# Score all available TreeLoc-format result artifacts on the visible train
# slice and held-out test slice.

set -euo pipefail

cd /home/user

bash scripts/evaluate_train.sh
bash scripts/evaluate_test.sh
