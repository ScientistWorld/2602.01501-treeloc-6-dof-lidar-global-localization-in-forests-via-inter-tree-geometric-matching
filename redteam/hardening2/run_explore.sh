#!/bin/bash
# Hardening iteration 12, exploration job: candidate inter-session test scales
# (and the paper's growing-database intra protocol) x methods; see explore.py.
set -uo pipefail
cd "$(dirname "$0")/../.."
OUT=redteam/hardening2/results
mkdir -p "$OUT"
nproc
python -c "import numpy; print('numpy', numpy.__version__)"
t0=$SECONDS
EXPLORE_JOBS=${EXPLORE_JOBS:-8} python redteam/hardening2/explore.py 2>&1 | tee "$OUT/explore.log"
rc=${PIPESTATUS[0]}
echo "explore rc=$rc after $((SECONDS - t0)) s"
python redteam/hardening2/analyze_explore.py > "$OUT/analyze_explore.log" 2>&1
echo "analyze rc=$?"
tail -n 80 "$OUT/explore_analysis.md"
exit $rc
