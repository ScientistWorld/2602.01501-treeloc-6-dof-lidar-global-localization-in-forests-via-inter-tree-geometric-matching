#!/bin/bash
# Iteration-11 hardening job: reproduces the reference end to end (TreeLoc and
# the baselines on the train slice and on the hidden test, i.e. what
# scripts/reproduce.sh does) and then runs the hardening audit (variants and
# shortcuts through the hidden test). Resumable; see redteam/hardening/run_audit.sh.
set -euo pipefail
cd /home/user
bash redteam/hardening/run_audit.sh
