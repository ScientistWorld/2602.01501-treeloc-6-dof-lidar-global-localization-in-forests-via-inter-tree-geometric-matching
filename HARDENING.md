# Hardening report — TreeLoc gym

Iteration 12 answers `REVIEW.md`. The iteration-11 report follows unchanged below. It records how the gym got
here: real data, the hidden test running methods itself, strict validation, file guards and the ground-truth
registration.

## Iteration 12: the review's brute-force finding

`REVIEW.md` reported one weakness. A brute-force matcher outranks the reference: the paper's verifier run on
every database scene, instead of TDH top-100 → hash top-10 → verify. It scored +0.47; the honest gain is +2.73.
The review asked to scale the hidden test (database size, query count or candidate pool) until brute force no
longer outranks the reference.

**Summary: I could not make brute force lose by scaling. On these data, scaling makes it win by more.**
- I tested every larger hidden test the released data allow, in one CPU job (`5b8d7c91-23d`).
- Every enlargement of the database widened brute force's margin.
- No faithful protocol or weighting change makes brute force lose either.
- The hidden test, evaluator, data, reference and score files are therefore **unchanged**.
- Brute force is now closed by an explicit, checkable rule for the post-hoc grader: a per-query budget on detailed
  matching (below).

Evidence: `redteam/hardening2/`, with these parts:
- `explore.py` builds the variants with the hidden-test builder's own functions and runs every method on them.
- `analyze_explore.py` computes ranks and a paired bootstrap; output in `results/explore_analysis.md` and `.json`.
- `whatif.py` gives weight and normalisation what-ifs; output in `results/whatif_weights.md`.
- `check_protocol_leak.py` tests the paper-protocol time leak; output in `results/protocol_leak.txt`.
- `results/metrics/` holds per-variant metrics.

The job reproduces the official hidden-test scores of the reference and both baselines exactly: max difference
0.0 on all 9 metrics.

### What I tried, and what happened (hidden test, Δrank vs the reference)

Ranks use the gym's coefficients and weights (intra 0.6 / inter 0.4). They are normalised over **panel Q**, the 9
methods run here: the reference, brute force, verify-all-100-TDH-candidates, the stronger variant, the three paper
ablations and the two baselines. 95% intervals come from a paired bootstrap over queries.

Variant names:
- **A** = V-03 queries vs a V-02 database (current direction).
- **B** = the reverse pair, V-02 queries vs a V-03 database. It is also one of the paper's 12 Venman pairs.
- **R** = how far past the official test regions the database extends. It adds same-forest scenes never used
  anywhere else; they are never true matches.

| Hidden-test variant | inter database / queries | Brute force | Stronger (honest) | Paper's "no TDH" ablation |
|---|---|---:|---:|---:|
| **Current: Stein + A, R = 15 m** | 543 / 548 | **+0.426** [+0.180, +0.697] | +2.690 | −0.425 |
| A, R = 35 m | 717 / 548 | +0.508 [+0.263, +0.777] | +2.761 | −0.363 |
| A, R = 50 m | 882 / 548 | +0.572 [+0.334, +0.850] | +2.838 | −0.290 |
| A + B, R = 15 m | 543 + 660 / 1013 | +0.565 [+0.337, +0.778] | +2.728 | −0.267 |
| A + B, R = 35 m | 717 + 966 / 1013 | +0.630 [+0.421, +0.871] | +2.777 | −0.214 |
| A + B, R = 50 m | 882 + 1198 / 1013 | +0.725 [+0.480, +0.964] | +2.873 | −0.118 |
| B, R = 50 m | 1198 / 465 | +0.897 [+0.647, +1.185] | +2.905 | **+0.079** |
| Paper's growing-database intra protocol + A, R = 15 m | 515 intra queries | +0.330 [+0.116, +0.599] | +2.651 | −0.531 |

Why scaling backfires, from the raw metrics (`results/explore.log`):
- **Brute force is insensitive to the added scenes.** In direction A, brute force's inter R@50 is 0.715 at R = 15,
  35 and 50 m, and its R@1 moves only from 0.659 to 0.655. The extra scenes never beat its choice. Its false
  matches (median 54 m away) are structural confusions inside the test regions, not chance hits that a larger pool
  would multiply.
- **The reference degrades as the pool grows.** Its R@1 falls 0.799 → 0.786 → 0.774 and its R@50 0.551 → 0.536 →
  0.524, because the TDH top-100 shortlist gets diluted. Direction B behaves the same way.
- **The ablation ordering breaks.** At the largest database the paper's own "no TDH" ablation overtakes the
  reference (+0.079). A test of that size would contradict the paper's Table V.
- **Brute force's gain is outside the shortlist.** It comes from true matches outside TDH's top 100.
  Verifying all 100 TDH candidates with the same verifier gains nothing (−0.056 [−0.242, +0.125]).
- **Its margin sits entirely in intra-session (Stein): +0.42.** There, TDH sometimes misses the right place, and
  brute force gets the pose right for 22 of the 439 queries where the reference gets neither place nor pose
  (for 9 of them it also gets the place). No unseen Stein data exist to add, and a larger
  same-session database helps brute force even more. The release has only Evo, Stein, V-02 and V-03; Evo is the
  visible train slice.

Other changes I tested and rejected:
- **The paper's own intra protocol** (database = every frame up to 50 before the query) cuts brute force to
  +0.33. It also brings the reference to the paper's Stein numbers: R@1 0.876 vs 0.871, R@50 0.922 vs 0.908.
  But a batch file can only express it as nested chronological databases, and matching scene contents across them
  reveals time order that pays directly. For 105 of 145 queries of one block, no positive lies in the most recent
  database block; for 101 of 140 of another, all of them do. Not adopted.
- **Re-weighting.** Inter-session coefficients that follow the paper's Table II (place recognition), with weights
  0.5/0.5, bring brute force to −0.03 in panel Q. Normalised over TreeLoc-family attempts only (panel F), it is
  still +1.82 under the same weights. Brute force has a mixed profile: it is better on Stein and worse on inter
  R@1/F1/AUC. So its sign depends on the population that future attempts form, not on coefficients. Weights and
  coefficients are unchanged.
- **A runtime or CPU budget.** Exhaustive verification over about 1,000 scenes costs about 0.6 ms per pair in the
  reference's own Python and less when vectorised. That is comparable to the reference's per-query cost, so no
  budget separates them without failing honest, slower variants. Runtime also varied 1.9× within one earlier job.

### The fix: a per-query search budget, checked by the grader

`scoring/CONSTRAINTS.md`, `scoring/DIRECTION.md` and `briefing/evaluation.md` now bound search per query:
- **Capped:** detailed matching, meaning any step that estimates a transform or correspondences against a database
  scene, is allowed against at most 100 scenes per query, independent of database size.
- **Unrestricted:** cheap whole-database scoring that estimates no transform (global descriptors, hash-key counting,
  inverted-index voting).
- **Out of bounds:** exhaustive verification.

This is the paper's real-time design constraint. The paper verifies 10 of its 100 coarse candidates and claims
< 50 ms per query. Within it, every better method stays expressible: descriptors, voting, verification, confidence
and pose refinement are all free, and so is verifying all 100 coarse candidates. Verifying all 100 is the most
search the cap allows; it scores −0.056 [−0.242, +0.125] in panel Q and +0.50 in panel F, so the extra search pays
only under the narrow family normalisation. The reference, its ablations and the iteration-11 stronger variant
all comply: the stronger variant verifies 10 candidates and keeps its +2.69.

| Shortcut | Before (iteration 11) | After (iteration 12) |
|---|---|---|
| Exhaustive verification (brute force) | +0.470 (11-method panel), +0.426 (this panel); not ruled out | Same hidden-test score, +0.426 [+0.180, +0.697]. Now out of bounds by rule, so the grader rejects it. The test itself cannot stop it (above). |

### Status of the other requirements

- **Do better results score higher? Yes, unchanged.** The stronger variant scores +2.690 [+2.399, +2.949]. Every
  paper ablation is below the reference:
  - TDH without DBH: −0.376
  - no TDH: −0.425
  - TreeLoc-f: −0.916
  - no alignment: −4.976
  - TDH-only baseline: −13.03

  The 9-method panel differs from iteration 11's 11-method panel, so magnitudes differ slightly; the order is
  identical.
- **Reference, before and after: unchanged.** Stein: R@1 0.759, R@50 0.879, SR 0.934, TE 0.121 m. Venman: R@1
  0.799, R@50 0.551. `scoring/scores_test.json` and `scores_train.json` are the iteration-11 files. They were
  reproduced independently by the review and, for the hidden test, bit-for-bit by this job. No gym code or data
  changed, so the reference and baselines were not rerun.
- **Headroom: unchanged.** The reference is at the bound of no scored metric, and the stronger variant is far above
  it on both experiments. No experiment was added.
- **Shortcuts left:** iteration 11's list stands (below), now with brute force closed by rule rather than left
  open: the public answer key, reading `eval/test/` at run time, train-truth tampering, and trading conditional
  metrics.

### Not fixed, stated plainly

- **The hidden test does not stop exhaustive verification; only the grader rule does.** A submission that verifies
  every scene still scores about +0.43 if the grader misses it.
- **The rule cannot be measured by the evaluator.** It relies on the grader reading the method's code.
- **Scaling with the paper's real data cannot stop it.** Doing so would need distractor databases orders of
  magnitude larger than the released sessions (about 1,000 scenes each). Brute force's wins are not chance hits
  among distractors, so adding scenes never hurts it.

---

# Iteration 11 report (unchanged record)

Evidence: `redteam/hardening/` (audit code, submissions, `run_audit.sh`), final results in
`redteam/hardening/results/` (job `fa409d67-f9e`), the pre-ground-truth-fix run in
`redteam/hardening/results_job1/` (job `7aa87bbf-a81`), the previous red-team audit in `REDTEAM.md` / `redteam/`.

Rank delta = Σ_exp weight · Σ_metric |coef| · direction · (method − reference) / std_P(metric), with
the coefficients and weights of `scoring/reference.json`. Panel **Q** = the 11 honest audited methods,
panel **A** = all 23 audited entries (failed ones at worst values). 95% intervals are a paired bootstrap
over hidden-test queries (every method resampled on the same queries, normalisation from Q).
Before/after shortcut numbers come from different gyms and panels, so compare signs and orderings,
not magnitudes.

## What changed

1. **Real data instead of the synthetic forest** (started by the first hardening session of this iteration, finished here).
   The gym now uses the authors' released RealtimeTrees tree inventories (github.com/minwoo0611/TreeLoc, branch
   `TreeLoc++`, pinned commit). `intra_session_localization`: train Oxford Evo (934 database / 867 queries), hidden test
   Oxford Stein am Rhein, the paper's localization benchmark (523 / 439). `inter_session_localization`: Wild-Places
   Venman V-03 queries vs V-02 database (~6 months apart); train ≥ 50 m outside the official Wild-Places test regions
   (493 / 550), hidden test inside them (543 / 548). Inputs carry tree inventories in local frames only, under random
   IDs, shuffled; no poses, no time order. `scripts/download.sh` rebuilds both slices byte-identically from the public
   commit (verified on the login node); the hidden-test builder lives only in `eval/test/`.
2. **Hidden test runs the methods itself** on inputs only `eval/test/` holds (`submissions/<name>.sh IN OUT`); TreeLoc
   needs no training. Every `submissions/*.sh` is scored, plus every name in `scores_train.json` (worst values if its
   script is gone). Outputs are validated strictly (known, unique queries; candidate in that experiment's database;
   finite numbers; proper rotation within 1e-3; |t| ≤ 1e6). Any failure, crash, timeout or missing output gets the
   worst value of every metric of that experiment, and the run still exits 0. Truth and inputs are SHA-256 pinned in
   the evaluator and loaded before any method runs; thresholds are constants in the evaluator.
3. **New this session: file guards.** Both evaluators snapshot the other score files and their benchmark files before
   submissions run and restore them afterwards (a forged `scores_train.json` previously survived a test run).
4. **New this session: inter-session ground truth registered.** Job 1 showed every method's inter-session poses off by
   ~0.5 m even when retrieval was right (train: R@1 0.99 but R@50 0.12; world-frame error (+0.51, −0.17) m, sd 0.05 m).
   The released V-03 trajectory is offset from V-02. The data builders now register each V-03 position to the V-02
   frame by matching its world-projected stems (±5 frames) to the V-02 stem map (DBH-gated nearest stem, median
   displacement, 1.0 m then 0.35 m). Inputs are unchanged; residual bias after the fix is (3.8, −1.2) cm, sd 4.5 cm.
   The paper reports no inter-session localization, so these pose metrics are a gym addition (noted in `reference.json`).
5. **New this session: method fidelity.** (a) Tree selection now follows the released `ProcessFile` order (align with
   reconstructed stems in the raw 60 m box, select from all trees, crop after alignment). (b) The `treeloc_no_alignment`
   baseline is restored to the paper's Table V ablation, which "feeds raw centers directly to TDH and the triangle
   hash"; verification and the 6-DoF pose still use the aligned scene. The earlier version removed alignment from the
   pose too, which caps 6-DoF accuracy here (median relative roll/pitch between revisits is 15°). Stein R@50 is now
   0.663 vs the paper's 0.701.
6. Removed the synthetic generator/evaluator; docs in `briefing/` and `scoring/` rewritten for the real-data gym.

Weights and coefficients are unchanged (intra 0.6 / inter 0.4; R@50 1.0, R@1 0.8, SR 0.5, TE_all 0.5, F1/AUC/TE/RE
0.4, RE_all 0.3). They already follow the paper: localization accuracy (Table III) and place recognition (Tables I/II)
are the headline results, and within-session localization is where the paper's 6-DoF claims live.

## Do better results score higher?

**Yes.** Hidden test, final gym (job 2):

| Variant | Δrank Q [95% CI] | Δrank A | Before: REDTEAM Q / A (synthetic) | Job 1 Q (before GT fix) |
|---|---:|---:|---:|---:|
| Stronger: robust verification + tilt refinement | **+2.734** [+2.436, +3.021] | +1.660 | +4.352 / +2.487 | +2.265 |
| Stronger: robust verification | **+2.478** [+2.185, +2.773] | +1.510 | — | +1.937 |
| Reference, seeds 1 and 2 | 0.000 [−0.0001, +0.0001] | 0.000 | 0 / 0 | 0.000 |
| Weaker: TDH without DBH (Table V) | −0.382 [−0.618, −0.117] | −0.208 | — | −0.399 |
| Weaker: no TDH, hash ranking over all (Table V) | −0.415 [−0.692, −0.103] | −0.257 | — | −0.392 |
| Weaker: TreeLoc-f, first verification step only (Table III) | −0.932 [−1.087, −0.765] | −0.603 | — | −0.681 |
| Baseline: no alignment for descriptors (Table V) | −5.057 [−5.499, −4.657] | −2.933 | −7.180 / −4.224 (old ablation) | −7.714 (old ablation) |
| Baseline: TDH-only retrieval, identity pose | −13.752 [−14.189, −13.337] | −7.390 | −7.425 / −4.225 | −13.135 |

The stronger variant (all hash-matched triangle pairs as SE(2) hypotheses, DBH-gated support, iterative refinement,
translation-aware overlap, optional roll/pitch refinement) beats the reference far beyond the paired noise. Every
paper ablation scores below the reference, with intervals excluding zero. Seed spread is zero: the only stochastic step
is the vertical-offset RANSAC, and seeds change TE_m by < 1e-4. On the train slice the order is the same: stronger +0.66,
brute force +0.16, reference 0, TreeLoc-f −0.45, no alignment −2.59, TDH −10.43 (`results/analysis_train.md`). Train and test rank the methods in the same order.

## Reference before and after

| | R@1 | F1 | AUC | R@50 | SR | TE_m | RE_deg | TE_all_m | RE_all_deg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Before (synthetic, 24 test queries) | 0.917 | 0.655 | 0.651 | 0.792 | 0.864 | 0.036 | 0.216 | 1.223 | 15.740 |
| After, intra (Oxford Stein, 439) | 0.759 | 0.791 | 0.737 | 0.879 | 0.934 | 0.121 | 0.752 | 0.670 | 5.925 |
| After, inter (Venman test regions, 548) | 0.799 | 0.800 | 0.745 | 0.551 | 0.637 | 0.133 | 1.300 | 2.289 | 16.369 |
| Paper, Stein 6-DoF (Table III) / Table I | 0.871 | 0.945 | 0.988 | 0.908 | 0.940 | 0.126 | 1.013 | — | — |

The localization numbers on Stein reproduce the paper's 6-DoF results closely (R@50 0.879 vs 0.908, SR 0.934 vs 0.940,
TE 0.121 vs 0.126 m). R@1/F1/AUC are lower because of protocol differences recorded in `reference.json`:
- the database is a fixed first half of the sequence, not every earlier frame;
- recall counts every evaluated query. The released code's recall only counts queries whose top-1 is correct, so a
  method could game it by abstaining.

## Shortcuts: fix and score before → after

| REDTEAM shortcut | Fix | Before Q / A | After |
|---|---|---:|---|
| Read visible global poses | Inputs hold local tree inventories only; poses only in truth | +4.428 / +2.493 | not possible; nearest analogue `train_lookup` −17.891 / −9.066 |
| Regenerate answers from the visible generator | No generator: real data; test from another forest / hidden region, private ID seed | +4.428 / +2.493 | `train_lookup` (memorise visible train answers) finds no test frame: −17.891 |
| Self-match (query as its own candidate) | Candidate must be a database frame of that experiment | +4.308 / +2.418 | invalid → worst: −18.889 / −9.419 |
| Ordinal / serial identity | Random IDs, shuffled frames | −2.780 / −1.965 | −17.372 / −8.894 |
| Move editable thresholds | Thresholds are evaluator constants in `eval/test/` | −3.294 / +1.905 | not possible (structural) |
| Scaled rotation (1e6·I) | Proper-rotation check | +0.172 / +0.188 | huge and 1.0004× scaling both invalid → −18.889 |
| Duplicate pair records | One prediction per query; duplicates invalid | +1.670 / +1.030 | −18.889 |
| Replace ground truth | Truth SHA-pinned, loaded before methods run, restored after | +4.428 / +2.493 | tamper run scores constant-level (R@1 0 / 0.016); test truth restored; a later train run fails its integrity check, so tampering cannot help the tamperer |
| Replay cached artifacts | Test runs the method on hidden inputs | 0.000 tie | train outputs replayed are invalid → −18.889 |
| Register only some methods (omission) | Every `submissions/*.sh` plus every `scores_train.json` name is scored; missing → worst | 0.000 tie | names without a script appear with worst values (shown in the forge/tamper runs) |
| Forge score files | Evaluator recomputes; other score files restored | fails | still fails; official score files byte-identical after the forge run |
| NaN translation | Non-finite → invalid | no finite rank (NaN accepted) | −18.889 |
| Empty / null / missing output, crash | Worst value of every metric, evaluator exits 0 | exit 1, no scores | −18.889 / −9.419 |
| Constant output | — | −3573 / −13.2 | −17.891 / −9.066 |

`shortcut_read_hidden` scanned every file outside `eval/test/` (excluding `.git`, `shared`, `tmp`) for hidden query
IDs and found none.

## Shortcuts and problems left

- **Exhaustive verification (brute force) outranks the reference: +0.470 [+0.200, +0.734] (panel A +0.316); train +0.16.**
  It runs the paper's verifier on every database scene instead of the TDH top-100 → hash top-10 shortlist. All of its
  gain is on Stein: +0.45, from R@1 0.797 vs 0.759 and R@50 0.934 vs 0.879. Inter-session it nets about zero: more
  false positives (R@1 0.659 vs 0.799) offset better poses (R@50 0.715 vs 0.551).

  I could not scale the test until it stops paying:
  - Stein (1047 frames) is the only released Oxford session, and Evo is the visible train slice.
  - The inter-session database already follows Wild-Places' test-region protocol.
  - Distractors from the other forest only add cost; a forest-level descriptor rejects them, so accuracy is unchanged.
  - A wall-clock budget cannot separate it. Brute force took 131 s on Stein, while the honest stronger variant took
    61 s, and the same method's runtime varied 1.9× within one job.

  The paper's case for its shortlist is speed (< 50 ms per query), which the gym cannot score. Its own "no TDH"
  ablation, which also shortlists, does score below the reference here (−0.415). The stronger honest variant outranks
  brute force by a wide margin (+2.73 vs +0.47). `scoring/DIRECTION.md` states that more computation per query is not a
  contribution.
- **Public answer key.** The hidden test frames come from a public repository whose trajectories are the answers. A
  method that bundles them could look up poses. This cannot be closed while using the paper's public data.
  `CONSTRAINTS.md` and `DIRECTION.md` forbid it, and `download.sh` deletes the raw checkout. The post-hoc grader should
  flag any method shipping TreeLoc/TreeLoc++ trajectories or inventories.
- **Reading `eval/test/` at run time.** Submissions run in the workspace without a sandbox and could open
  `eval/test/data/truth.json.gz`. Left to the grader, since there is no OS-level isolation to rely on.
- **A test-time submission can corrupt `data/train/truth.json.gz`.** The test evaluator guards only its own files.
  The train evaluator then fails its integrity check, so only the tamperer is hurt.
- **Conditional metrics** (SR, TE_m, RE_deg) can in principle be traded by deliberately returning wrong candidates for
  hard queries. This costs R@1, R@50 and TE_all/RE_all, which together carry about twice the coefficient mass (2.6 vs 1.3). Not
  exercised.

## Headroom

The reference sits at the bound of **no** scored metric (table above): R@1 0.76 / 0.80, R@50 0.88 / 0.55, F1 and AUC
below 0.80, errors well above 0. The stronger variant raises 7 of 9 metrics on intra and all 9 on inter. Its exceptions
on intra are TE_all and RE_all (0.748 vs 0.670 m, 6.5 vs 5.9°), from a few confidently wrong retrievals.

On inter it nearly saturates the pose metrics (R@50 0.987, SR 0.998). Intra still leaves room above it: R@1 0.852,
R@50 0.904, AUC 0.851, TE_all 0.75 m. Simple baselines are far below the reference: TDH-only R@50 = 0 on both, and
no-alignment −5.06. No experiment was added. Headroom exists on the paper's own benchmark, and both directions where the
paper falls short are already scored: inter-session localization, and the precision of its pose/candidate selection.

## Other limitations, stated plainly

- Train is easier than test for every method: Evo R@1 0.917 vs Stein 0.759. The paper also reports Evo > Stein. The
  ranking is identical on both slices.
- Inter-session truth depends on the stem-map registration above. It is a smooth correction from thousands of stems
  per window, not a per-query fit, but it uses the same modality the methods see.
- Not reproduced:
  - BTC and the other comparison methods (paper numbers only);
  - Karawatha / BotanicGarden (not in the release);
  - the storage and multi-session applications (Tables VI–VII);
  - runtime.
- The reference is a faithful Python re-implementation of the released C++ code. One documented difference: the
  roll/pitch alignment is RANSAC over stem axes as in the paper's Eq. 3; the released code uses a plain mean.
