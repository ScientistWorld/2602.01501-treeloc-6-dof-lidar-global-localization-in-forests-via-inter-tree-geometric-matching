#!/bin/bash
# Reproduce the reference end to end: TreeLoc, its Table V no-alignment
# ablation and the TDH-only baseline on the train slice and on the hidden test
# (scoring/scores_train.json, scoring/scores.json, scoring/scores_test.json),
# then validate the workspace. The hardening audit is
# redteam/hardening/run_audit.sh (see HARDENING.md).
set -euo pipefail
cd /home/user
bash scripts/reproduce.sh
