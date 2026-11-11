#!/bin/bash
# Hidden-test evaluation. Runs with no arguments and scores EVERY method on
# disk: each submissions/<name>.sh is run on the hidden test inputs held in
# eval/test/data/ (invoked as `bash submissions/<name>.sh INPUT_JSON OUTPUT_JSON`),
# its output is validated and scored, and all numbers are written to
# scoring/scores_test.json. Methods that fail, time out or write an invalid
# output receive the worst value of every metric.
#
# Optional environment: TREELOC_EVAL_JOBS (parallel method runs, default 1),
# TREELOC_METHOD_TIMEOUT_S (per method and experiment, default 7200).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p scoring
python eval/test/evaluate.py
