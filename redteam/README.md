# TreeLoc gym scoring audit

Run the bundled audit as a CPU job with `bash redteam/run_all.sh`. Each
variant and shortcut has its own `run.sh`. Those scripts generate method
artifacts, invoke the unmodified visible training evaluator, and invoke
`bash scripts/evaluate_test.sh` with **no arguments** in a new process.
Preparation uses only scientist-visible data, generators, baseline code,
and (for improve-mode comparisons) the reference method code. It does not
read test query IDs, test source, reference scores, paper text, or existing
test answers. Test outputs are read only after evaluation for reporting.

`harness.py` restores all changed data, artifacts, method source, and scoring
files in a `finally` block. Runtime backup/cache directories and prediction
artifacts are ignored. Small score files, exit codes, and audit statistics
are retained beside each run. `reference/` snapshots only the scientist-visible
method and baseline, to keep the variants reproducible after restoration.

Population-normalized rank cannot be known for unknown future attempts.
`analyze.py` reports the stated ranking formula using explicit audit panels,
absolute coefficient magnitudes, declared directions, experiment weights,
and per-metric population standard deviations. Componentwise dominance and
exact ties do not depend on the choice of panel.
