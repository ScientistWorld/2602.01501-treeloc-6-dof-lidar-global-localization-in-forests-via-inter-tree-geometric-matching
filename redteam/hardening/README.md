# Hardening audit (iteration 11)

`run_audit.sh` (run as a CPU job via `scripts/run.sh` at the time) reproduces the reference on train and the
hidden test, then runs every submission in `submissions_audit/` through the hidden-test evaluator
(variants, brute force, shortcuts), the score-forging (`submissions_forge/`) and truth-tampering
(`submissions_tamper/`) submissions, rescores the train-slice variants (`rescore_saved.py`), and computes rank
deltas with a paired bootstrap (`analyze.py`). Stages are resumable (`results/<stage>.done`).

- `treeloc_robust.py` — the stronger variant (robust verification; `--tilt` adds roll/pitch refinement).
- `shortcuts.py` — the shortcut submissions (each mode tries to score without solving the task).
- `results/` — final run (job `fa409d67-f9e`): `analysis_test.md`, `analysis_train.md`, score files, stage logs.
- `results_job1/` — first run (job `7aa87bbf-a81`), before the inter-session ground-truth registration and the
  Table V ablation fix.

Summary and interpretation: `HARDENING.md` at the workspace root.
