#!/bin/bash
# Hardening audit for the TreeLoc gym (iteration 11). Not part of the gym.
#
# Stages run in priority order; each finished stage leaves a .done marker in
# redteam/hardening/results/ and is skipped when the job is resubmitted, so a
# killed job resumes where it stopped. Per-stage logs: results/<stage>.log.
#
#   smoke          tiny subset through every code path (fails fast on a bug)
#   official_train scripts/evaluate_train.sh  -> scoring/scores_train.json
#   official_test  scripts/evaluate_test.sh   -> scoring/scores_test.json
#   audit_test     every variant/shortcut in submissions_audit/ on the hidden test
#   forge          score-forging submissions (score files must be restored)
#   tamper         truth-tampering submission (truth must be restored / detected)
#   audit_train    selected variants on the train slice (train/test consistency)
#   analyze        rank deltas (two panels) + paired bootstrap on test queries
#   validate       python validate.py (default and --post-design)
set -uo pipefail
cd "$(dirname "$0")/../.."
H=redteam/hardening
OUT=$H/results
mkdir -p "$OUT"
export TREELOC_EVAL_JOBS="${TREELOC_EVAL_JOBS:-1}"
log() { echo "[$(date '+%F %T')] $*"; }

stage() {  # stage NAME CMD...
  local name=$1; shift
  if [ -f "$OUT/$name.done" ]; then log "skip $name (done earlier)"; return 0; fi
  log "start $name"
  local t0=$SECONDS
  "$@" > "$OUT/$name.log" 2>&1
  local rc=$?
  echo "{\"stage\": \"$name\", \"rc\": $rc, \"seconds\": $((SECONDS - t0))}" >> "$OUT/stages.jsonl"
  log "end $name rc=$rc after $((SECONDS - t0)) s"
  tail -n 40 "$OUT/$name.log"
  [ $rc -eq 0 ] && touch "$OUT/$name.done"
  return $rc
}

smoke() {
  python -c "import sys, numpy; print(sys.version); print('numpy', numpy.__version__)"
  nproc
  python - <<'EOF' || return 1
import gzip, json
for exp in ("intra_session_localization", "inter_session_localization"):
    p = json.loads(gzip.decompress(open(f"data/train/{exp}.input.json.gz", "rb").read()))
    s = p["sequences"][0]
    s["database"], s["queries"] = s["database"][:60], s["queries"][:6]
    open(f"redteam/hardening/results/smoke_{exp}.json", "w").write(json.dumps(p))
EOF
  local exp in_ out t0
  for exp in intra_session_localization inter_session_localization; do
    in_=$OUT/smoke_$exp.json; out=$OUT/smoke_out.json
    for args in "" "--no-alignment" "--no-dbh" "--first-step-only" "--top-tdh 0" "--top-tdh 0 --top-hash 0" "--seed 1"; do
      t0=$SECONDS
      # shellcheck disable=SC2086
      python method/treeloc.py --input "$in_" --output "$out" $args || return 1
      echo "treeloc [$args] on $exp: $((SECONDS - t0)) s"
    done
    for args in "" "--tilt"; do
      t0=$SECONDS
      # shellcheck disable=SC2086
      python $H/treeloc_robust.py --input "$in_" --output "$out" $args || return 1
      echo "treeloc_robust [$args] on $exp: $((SECONDS - t0)) s"
    done
    python baseline/tdh_baseline.py --input "$in_" --output "$out" || return 1
    python - "$out" <<'EOF' || return 1
import json, sys
o = json.load(open(sys.argv[1]))
assert len(o["predictions"]) == 6, o
print("smoke output ok:", o["predictions"][0]["candidate"], o["predictions"][0]["score"])
EOF
  done
}

official_train() {
  bash scripts/evaluate_train.sh || return 1
  cp scoring/scores_train.json scoring/scores.json
}

official_test() {
  TREELOC_DETAILS_DIR=$OUT/details_official bash scripts/evaluate_test.sh || return 1
  cp scoring/scores_test.json "$OUT/official_scores_test.json"
}

audit_test() {
  TREELOC_SUBMISSIONS_DIR=$H/submissions_audit TREELOC_SCORES_OUT=$OUT/audit_scores_test.json \
    TREELOC_DETAILS_DIR=$OUT/details_test TREELOC_METHOD_TIMEOUT_S=3600 python eval/test/evaluate.py
}

forge() {
  local before after
  before=$(sha256sum scoring/scores_test.json scoring/scores_train.json scoring/scores.json)
  TREELOC_SUBMISSIONS_DIR=$H/submissions_forge TREELOC_SCORES_OUT=$OUT/forge_scores_test.json python eval/test/evaluate.py
  after=$(sha256sum scoring/scores_test.json scoring/scores_train.json scoring/scores.json)
  if [ "$before" = "$after" ]; then echo "FORGE: official score files unchanged after the run"; else echo "FORGE: official score files CHANGED"; return 1; fi
}

tamper() {
  local bk=$OUT/truth_backup rc=0
  mkdir -p "$bk"
  cp data/train/truth.json.gz "$bk/train_truth.json.gz"
  cp eval/test/data/truth.json.gz "$bk/test_truth.json.gz"
  TREELOC_SUBMISSIONS_DIR=$H/submissions_tamper TREELOC_SCORES_OUT=$OUT/tamper_scores_test.json python eval/test/evaluate.py || rc=1
  if cmp -s eval/test/data/truth.json.gz "$bk/test_truth.json.gz"; then echo "TAMPER: test truth restored by the evaluator"; else echo "TAMPER: test truth still modified"; rc=1; fi
  if cmp -s data/train/truth.json.gz "$bk/train_truth.json.gz"; then echo "TAMPER: train truth unchanged"; else
    echo "TAMPER: train truth modified by the submission; a train evaluation now fails its integrity check:"
    python eval/train/evaluate.py --output "$OUT/tamper_train_integrity.json" treeloc > /dev/null 2>&1; echo "  train evaluator exit code $? (expected 1)"
    cp "$bk/train_truth.json.gz" data/train/truth.json.gz; echo "  train truth restored from backup"
  fi
  return $rc
}

audit_train() {
  TREELOC_SUBMISSIONS_DIR=$H/submissions_audit TREELOC_METHOD_TIMEOUT_S=5400 python eval/train/evaluate.py \
    --output "$OUT/audit_scores_train.json" stronger_robust_tilt stronger_robust weaker_treeloc_f bruteforce_exhaustive
}

analyze() {
  python $H/analyze.py --scores "$OUT/audit_scores_test.json" --details "$OUT/details_test" --out "$OUT/analysis_test.json" || return 1
  python $H/analyze.py --scores scoring/scores_train.json "$OUT/audit_scores_train.json" --out "$OUT/analysis_train.json" || return 1
  python - <<'EOF'
import json
a = json.load(open("scoring/scores_test.json"))["experiments"]
b = json.load(open("redteam/hardening/results/audit_scores_test.json"))["experiments"]
for e in a:
    for n in a[e]["results"]:
        print(e, n, "identical in official and audit runs:", a[e]["results"][n] == b[e]["results"].get(n))
EOF
}

validate() {
  python validate.py
  echo "---- --post-design"
  python validate.py --post-design || true
}

stage smoke smoke || { log "smoke test failed; aborting"; exit 1; }
stage official_train official_train
stage official_test official_test
stage audit_test audit_test
stage forge forge
stage tamper tamper
stage audit_train audit_train
stage analyze analyze
stage validate validate
log "audit finished"
cat "$OUT/stages.jsonl"
