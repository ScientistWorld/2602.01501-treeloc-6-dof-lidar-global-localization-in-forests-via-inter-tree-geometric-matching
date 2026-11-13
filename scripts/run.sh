#!/bin/bash
# TEMPORARY (hardening iteration 12): exploration job. The reference
# reproduction (bash scripts/reproduce.sh) is restored as run.sh afterwards.
set -euo pipefail
cd /home/user
bash redteam/hardening2/run_explore.sh
