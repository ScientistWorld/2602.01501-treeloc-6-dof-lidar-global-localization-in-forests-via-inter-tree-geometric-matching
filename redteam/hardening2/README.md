# Hardening audit, iteration 12 (REVIEW.md follow-up)

Question: can the hidden test be scaled until exhaustive verification (the paper's verifier run on every database scene)
stops outranking the reference? Answer: no, not with the released data; see `HARDENING.md` (iteration 12).

- `run_explore.sh` — the CPU job (`5b8d7c91-23d`): `explore.py` then `analyze_explore.py`.
- `explore.py` — builds candidate hidden-test variants from the pinned upstream release (into the gitignored
  `data/downloads/explore/`; needs `data/downloads/treeloc_src`, a checkout as in `scripts/download.sh`) with the
  hidden-test builder's own functions, runs 9 methods per variant, stores per-query details (gitignored) and metrics.
- `analyze_explore.py` — ranks of every configuration (intra slice x inter directions/margins), panels Q and F, paired
  bootstrap: `results/explore_analysis.md` / `.json`.
- `whatif.py` — stdlib re-scoring of the saved details under other weights / panels: `results/whatif_weights.md`.
- `check_protocol_leak.py` — time-order leak of the paper's growing-database intra protocol: `results/protocol_leak.txt`.
