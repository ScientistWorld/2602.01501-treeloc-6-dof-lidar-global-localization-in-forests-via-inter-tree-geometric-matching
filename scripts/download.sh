#!/bin/bash
# Fetch the public benchmark source and (re)build the processed benchmark files.
#
# Source: the TreeLoc authors' RealtimeTrees tree inventories (Oxford Forest
# Evo / Stein am Rhein and Wild-Places Venman V-02 / V-03), published in
# https://github.com/minwoo0611/TreeLoc (branch TreeLoc++), pinned below.
#
# Estimated download: ~220 MB (temporary git checkout, deleted afterwards).
# Disk after processing: ~19 MB (data/train/ ~10 MB, eval/test/data/ ~9 MB).
#
# Idempotent: each processed file set is rebuilt only if a file is missing.
# The raw checkout is placed in a temporary directory outside the workspace and
# removed, because its trajectories include the hidden test answers; only
# eval/test/prepare_test_data.py writes the test side, into eval/test/data/.
set -euo pipefail
cd "$(dirname "$0")/.."

UPSTREAM_URL="https://github.com/minwoo0611/TreeLoc"
UPSTREAM_COMMIT="4b988c874f34d07b8258c79286078e15a5896b75"   # branch TreeLoc++

need_train=0
for f in intra_session_localization.input.json.gz inter_session_localization.input.json.gz truth.json.gz; do
  [ -f "data/train/$f" ] || need_train=1
done
need_test=0
if [ -f eval/test/prepare_test_data.py ]; then
  for f in intra_session_localization.input.json.gz inter_session_localization.input.json.gz truth.json.gz; do
    [ -f "eval/test/data/$f" ] || need_test=1
  done
fi

if [ "$need_train" = 0 ] && [ "$need_test" = 0 ]; then
  echo "Processed benchmark files exist in data/train/ and eval/test/data/; skipping fetch."
  exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
git init -q "$WORK/treeloc"
git -C "$WORK/treeloc" remote add origin "$UPSTREAM_URL"
git -C "$WORK/treeloc" fetch -q --depth 1 origin "$UPSTREAM_COMMIT"
git -C "$WORK/treeloc" checkout -q FETCH_HEAD

if [ "$need_train" = 1 ]; then
  python3 data/prepare_treeloc_data.py --source "$WORK/treeloc/data" --output data/train
fi
if [ "$need_test" = 1 ]; then
  python3 eval/test/prepare_test_data.py --source "$WORK/treeloc/data" --output eval/test/data
fi
