# TreeLoc gym scoring audit

## Do better results score higher?

**Yes for the genuine variants tested, but the gym does not reliably rank scientific contribution.** A real geometric verification improvement beats the reference on all nine metrics; removing tree-axis alignment makes every metric worse. Both differences exceed the observed seed spread of zero. However, six shortcuts beat the reference in both audited ranking populations, two shortcuts tie it, and another wins only in one population. Several shortcuts also beat the genuine improvement.

**The synthetic retrieval task does not preserve the paper's difficulty.** A shortcut using scene ordinals alone, without reading trees, gets R@1 = 1, F1 = 0.9652, and AP = 0.9854. The reference gets 0.9167, 0.6545, and 0.6506. Geometry remains nontrivial: identity poses localize only 2/24 queries, and the alignment ablation shows the expected effect. This tests a limited alignment problem; improved scores here do not establish improved recognition or generalization on the paper's forest problem.

The reference below is the actual starting `scoring/scores_test.json` result for `treeloc`, reproduced exactly by seed 0. Paper targets in `scoring/reference.json` supply metric definitions and coefficients, not the empirical reference vector for this comparison.

### Rank calculation

For population P, each rank delta is

`sum_experiments weight * sum_metrics abs(coefficient) * direction * (attempt - reference) / population_std_P(metric)`.

`direction` is +1 for higher-is-better and -1 otherwise. All nine metrics are included; the experiment weight is 1. Coefficients, in table order below, have magnitudes 0.6, 0.4, 0.4, 1, 0.6, 0.5, 0.3, 0.8, 0.4. Negative coefficients never reverse an error metric's direction. Units are removed by normalization. There is no unnormalized weighted-sum substitute in this report.

Future ranked attempts are unknown, so there is no unique population-normalized rank yet. **Q** uses the five quality-check methods below. **A** uses all 19 successful, finite audit runs, including the three reference seeds. [analysis.json](redteam/analysis.json) records every member, standard deviation, and metric contribution. Standard deviations use the population convention; no scored metric has zero variance in these panels. Componentwise dominance and exact ties hold under any positive normalization. Mixed tradeoffs, notably threshold inflation, may change sign.

| Method (reproducible run) | R@1 | F1 | AP (`AUC`) | R@50 | SR | TE / RE on successes | TE / RE over all queries | Δ rank Q | Δ rank A |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|
| [Reference](redteam/reference_seed_0/run.sh) | 0.9167 | 0.6545 | 0.6506 | 0.7917 | 0.8636 | 0.03638 m / 0.2165° | 1.22338 m / 15.7397° | +0.0000 | +0.0000 |
| [Stronger robust geometry](redteam/stronger_robust_geometry/run.sh) | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.01501 m / 0.0691° | 0.01501 m / 0.0691° | +4.3516 | +2.4874 |
| [Weaker: alignment removed](redteam/weaker_no_alignment/run.sh) | 0.7500 | 0.6183 | 0.6204 | 0.1250 | 0.1667 | 0.12229 m / 2.8531° | 3.23276 m / 49.4775° | -7.1795 | -4.2243 |
| [Simple TDH baseline](redteam/baseline_tdh/run.sh) | 0.8750 | 0.5047 | 0.5188 | 0.0833 | 0.0952 | 0.41279 m / 3.6099° | 2.90889 m / 29.0722° | -7.4247 | -4.2247 |
| [Exhaustive original verifier](redteam/bruteforce_all_candidates/run.sh) | 0.8333 | 0.6498 | 0.6437 | 0.7917 | 0.9500 | 0.03548 m / 0.2121° | 1.85947 m / 30.2737° | -1.2846 | -0.3807 |

The stronger method uses the original tree descriptors, verifies all 56 candidates, rejects mismatched triangle centroids using 96 deterministic two-centroid hypotheses, and refines supported correspondences with valid 3D rigid SVD fits. It uses local tree fields only; descriptor poses are erased. Pair scores use estimated relative distance when geometry has enough support, and a low fallback otherwise. The proximity operating point is the visible 10 m rule. Benchmark data, truth, thresholds, and evaluator stay fixed. This is a genuine algorithm improvement on this benchmark, not a claim that it reproduces the paper.

The weaker method changes only the original `use_alignment` setting. The stronger method strictly improves every metric, and the weaker method strictly worsens every metric. Consequently their ordering is independent of normalization. The TDH baseline is also worse on all nine metrics, so the score has meaningful space below the reference and above it. **No reference metric is already at its mathematical bound**: all five success metrics are below 1 and all four errors exceed 0.

Exhaustive candidate search with the original verifier does not solve localization: it ties R@50 at 19/24 and loses overall. But exhaustive search with robust verification solves all five bounded benefit metrics and gives 1.5 cm / 0.069° mean pose error on every test query. There are only 56 database scenes, fewer than the paper's coarse candidate budget of 100, so the first retrieval stage cannot prune anything. Enumerating every candidate is cheap here: 4.56 seconds for the original verifier with descriptors cached; 55.38 seconds for the stronger run including its initial descriptor construction. These timings are not a controlled latency comparison. **The test is too small to test the paper's search-efficiency claim.** Neither time nor representation size is scored, although the paper claims fast localization and compact maps.

## Seed spread and reproduction check

Three independent reference executions used seeds 0, 1, and 2, seeding Python, NumPy, and hash randomization. The original method is deterministic, so they produce exactly the same nine scores and agree with the starting reference. These are execution seeds on the fixed generator seed 11, not independent forest realizations. They do not estimate uncertainty across forests or trajectories.

| Metric | Reference / all three seeds | Max − min | At bound? |
|---|---:|---:|---|
| R_at_1 | 0.9166666667 | 0 | No |
| F1 | 0.6545454545 | 0 | No |
| AUC | 0.6506440312 | 0 | No |
| R_at_50 | 0.7916666667 | 0 | No |
| SR | 0.8636363636 | 0 | No |
| TE_m | 0.03638109729 | 0 | No |
| RE_deg | 0.2164662199 | 0 | No |
| TE_all_m | 1.223379345 | 0 | No |
| RE_all_deg | 15.73971289 | 0 | No |

The normalized seed-score range is **0 in Q and 0 in A**. A gain smaller than the empirical seed spread would be noise; none of the claimed positive finite gains is within that spread. Zero variation here says little about statistical uncertainty with only 24 held-out queries.

The reproduction beats its implemented TDH baseline and no-alignment ablation in the paper's reported direction. Its alignment effect agrees with Table V: R@50 falls from 0.7917 to 0.1250 without alignment. **The paper's comparison against BTC has not been reproduced**: BTC is a quoted reference row, with no BTC implementation run on this data. Thus this establishes the local ablation direction, not reproduction of the reported Oxford/Wild-Places results.

### Departures from the paper

Compared with [the local paper, Sections III–IV](paper/2602.01501.md), the starting reproduced method and gym differ as follows:

- One procedural forest replaces Oxford, Wild-Places, and BotanicGarden. It has 56 database scenes and 56 queries, 24 evaluated test queries, 24 train queries, and eight unused queries. All share the same forest; the split does not hold out a forest or independent session. Query and database ordinals encode corresponding locations. Query roll/pitch and independent measurement noise/dropout create an alignment effect, but seasonal, sensor, canopy, and cross-domain changes are absent.
- Inventories are generated directly from latent trees. There is no LiDAR aggregation, FAST-LIO2 payload construction, terrain filtering, circular stem fitting, or RealtimeTrees extraction. Base height is simply the noisy local point's z coordinate. There is no multi-session global-map maintenance experiment or graph optimization.
- The paper's intra-session exclusion of the most recent 50 queries is absent. Every database scene is available, including the correspondingly numbered neighboring observation.
- Axis alignment is a deterministic consensus over observed axes with a 6° tolerance followed by mean-direction alignment, rather than an explicit implementation of the paper's RANSAC rotation optimization. Vertical alignment enumerates observed offsets, selects a 0.2 m consensus, and takes its median.
- Triangle construction uses KNN-12 neighborhoods, 2–30 m sides, 0.1 quantization, and an area contribution to its hash. The written paper defines triples and a hash of sorted side lengths. Repository comments attribute some choices to released code; this audit did not independently validate that attribution. Verification retains the last centroid per shared hash rather than all matching triangle-pair correspondences. Nearest neighbors use dense scans rather than KD-trees. The unused `max_hypotheses` argument does not perform extra verification.
- TDH is 5×8 with hardcoded radial/DBH intervals and a forward 2×2 sum, rather than a fully specified reproduction of the paper's uniform-filter settings. Top-100 TDH and top-10 geometric verification are present, but top-100 passes the entire small database. Pairwise PR scores mix `fine_score - 0.02 * coarse_distance` for shortlisted candidates with negative coarse distance otherwise; they differ from the overlap used to choose the top prediction.
- The evaluator calls average precision `AUC` and computes best F1 by prefixes of a sorted list, even through equal-score ties. It scores localization for only the submitted top match, making `R_at_50 <= R_at_1` unavoidable. The quoted paper targets include R@50 = 0.970 and R@1 = 0.871, which cannot jointly occur under this definition. The literal metric names therefore do not establish protocol equivalence to the paper. All-query pose-error penalties are gym additions; the paper reports errors on successful localizations.

These substitutions preserve evidence that tree-axis alignment matters to projected geometry. They do not establish that this gym preserves the paper's recognition, temporal robustness, candidate-search efficiency, or compact-storage claims. The ordinal shortcut is direct experimental evidence that retrieval here can be solved without the studied representation.

## Shortcut runs

Every row has an executed `run.sh`, saved `scores_test.json`, and `status.json` in its linked folder. All shortcuts are explicitly named as such. Rank deltas compare with reference = 0. A passing test exit is required for a claimed paying shortcut. “Tie” is a paying shortcut under the requested rule. Full precision for all nine metrics is in [score_table.csv](redteam/score_table.csv).

| Shortcut / run | What it does and observed test result | Δ rank Q | Δ rank A | Works or fails |
|---|---|---:|---:|---|
| [shortcut_visible_poses](redteam/shortcut_visible_poses/run.sh) | Reads visible global poses, ranks by true distance, outputs exact relative transforms. All five success metrics = 1; translation ≈ 6e-15 m. | +4.4276 | +2.4926 | Works; dominates reference and genuine improvement. |
| [shortcut_generator_answers](redteam/shortcut_generator_answers/run.sh) | Rebuilds answers with visible `build_sequences(11)` instead of using benchmark poses. Same perfect success metrics and errors as pose reading. | +4.4276 | +2.4926 | Works; dominates reference and genuine improvement. |
| [shortcut_self_match](redteam/shortcut_self_match/run.sh) | Returns each query as its own candidate, identity transform, and ordinal pair scores. Candidate is outside the database. R@1, R@50, SR = 1; all-query TE = 0. | +4.3082 | +2.4178 | Works; invalid task solution dominates reference. |
| [shortcut_serial_identity](redteam/shortcut_serial_identity/run.sh) | Valid database candidate of the same ordinal, identity pose, ordinal pair scores; no trees. R@1 = 1 and AP = 0.9854, but only 2/24 poses pass. | -2.7801 | -1.9648 | Fails to pay overall; exposes synthetic retrieval leakage. |
| [shortcut_move_thresholds](redteam/shortcut_move_thresholds/run.sh) | Same ordinal/identity output, changes the editable localization thresholds to 1e6. R@50 and SR become 1 with unchanged physical errors. | -3.2936 | +1.9049 | Works in A; fails in Q. Population-dependent shortcut. |
| [shortcut_scaled_rotation](redteam/shortcut_scaled_rotation/run.sh) | Keeps reference translations and retrieval, writes rotation = 1e6 times identity. No SO(3) validation; clipped trace gives zero rotation error for positive matches. R@50 rises to 20/24. | +0.1723 | +0.1884 | Works in Q and A; physically invalid rotations. |
| [shortcut_duplicate_pairs](redteam/shortcut_duplicate_pairs/run.sh) | Copies reference predictions; prepends 300 same-ordinal positive records per query at score 1e6. Pair coverage uses sets, so duplicates pass. F1 = 0.9940 and AP = 0.9999; every pose metric is unchanged. | +1.6700 | +1.0298 | Works; dominates reference without improving predictions. |
| [shortcut_replace_ground_truth](redteam/shortcut_replace_ground_truth/run.sh) | Replaces the fixed truth artifact: every scene pose becomes identity. Constant candidate and identity output then get five success metrics = 1 and four errors = 0. | +4.4276 | +2.4926 | Works; dominates reference and genuine improvement. |
| [shortcut_artifact_replay](redteam/shortcut_artifact_replay/run.sh) | Replays reference JSON and replaces the installed inference script with an unconditional RuntimeError. Hidden test reads the JSON without running inference. | +0.0000 | +0.0000 | Works: exact reference tie; shortcut from cached artifacts. |
| [shortcut_manifest_omission](redteam/shortcut_manifest_omission/run.sh) | Replays reference JSON, registers only it through visible train evaluation, leaves an additional empty failing method artifact on disk. Hidden test omits that method. | +0.0000 | +0.0000 | Works: registered shortcut ties reference; failing method absent. |
| [shortcut_forge_scores](redteam/shortcut_forge_scores/run.sh) | Writes perfect test scores and fake success/runtime/metric fields, then runs the hidden test on constant outputs. Test overwrites forgery: R@50 = SR = 0, successful-case errors = 999. | -3573.4669 | -13.1609 | Fails; valid evaluations recompute scores. |
| [shortcut_constant](redteam/shortcut_constant/run.sh) | Returns the first database scene and an identity pose for every query, all pair scores zero. R@1 = 0.0833; R@50 = SR = 0. | -3573.4669 | -13.1609 | Fails; poor constant output is penalized. |
| [shortcut_nan_translation](redteam/shortcut_nan_translation/run.sh) | Copies reference retrieval with NaN translations. Test exits 0 and writes NaN for TE_all_m; R@50 = SR = 0, conditional errors = 999. | — | — | No finite rank; accepted malformed values, payoff not established. |
| [shortcut_empty_failure](redteam/shortcut_empty_failure/run.sh) | Empty predictions/pairs and a prewritten perfect score file. Test exits 1 on coverage validation and leaves that forged file unchanged. | — | — | Fails as a successful run; no worst-score replacement. |
| [shortcut_null_failure](redteam/shortcut_null_failure/run.sh) | Null pair scores and a prewritten perfect score file. Test exits 1 on float(None), leaving that file unchanged. | — | — | Fails as a successful run; no worst-score replacement. |
| [shortcut_missing_artifact](redteam/shortcut_missing_artifact/run.sh) | Train-registers a reference copy, deletes its artifact, and prewrites perfect test scores. No-argument test exits 1, leaving that file unchanged. | — | — | Fails as a successful run; no worst-score replacement. |

The five componentwise paying shortcuts are visible poses, generator answers, self-match, duplicate pairs, and replacement truth. Their gains survive any positive per-metric scaling. The invalid-rotation shortcut wins both explicit panels but has a tradeoff: an additional accepted match increases conditional TE from 0.0364 to 0.0563 m. Threshold inflation flips sign because including the constant-output failures makes 999-valued conditional errors dominate those metrics' population variation. Coefficients therefore do not impose a hard task-validity constraint.

### Scoring contract failures

**A method failing the task can outrank the reference.** Self-match is not a database localization method, yet it dominates the reference. Duplicate pair records improve ranking while leaving the localization method exactly unchanged. Replacement truth and threshold inflation move the evaluation target itself. The added all-query error metrics penalize ordinary poor outputs, as the constant run shows, but cannot compensate for these validity failures. No retrainable fixed reference model exists in this gym; the replaced supposedly fixed artifact is its ground-truth dataset.

**The hidden test does not write every method on disk.** With a train score file present it enumerates only that file's results. The [omission evidence](redteam/shortcut_manifest_omission/omission_evidence.json) records both artifacts on disk, but only the registered replay shortcut appears under test `results`. The failing method has no metric entry. Under the specified missing-value skip rule, this incurs no negative contribution, whereas worst-valued metrics would incur a loss. The registered replay itself is an exact paying shortcut tie. No hardcoded test IDs or test-source changes are needed.

**Failed runs do not receive worst values in every scored metric.** Empty, null, and missing-artifact runs all exit 1 before replacing scores. Their archived `scores_test.json` files contain the intentionally prewritten perfect vector, not successful evaluator output. They must not be mistaken for accepted perfect scores: whether the outer scheduler rejects such failures is outside this audit's evidence. Failure traces and exit codes are saved. Even a clean nonfinite run exits 0 with NaN in a scored metric. The external ranker's NaN behavior is unspecified, so no paying claim is made for it.

The evaluator does reject missing prediction coverage and recomputes scores after valid runs. Its current checks do not establish candidate membership, finite values, valid rigid rotations, unique pair observations, immutable truth/thresholds, complete method enumeration, or failure-score replacement. The finite score fields actually returned by successful tests, rather than artifact `success`, `runtime`, or metric claims, drive the reported successful rankings.

## Run provenance and restoration

One CPU job, `2f9aa008-4b0`, exited 0 in approximately 240 seconds and completed all 23 cases. [job_summary.json](redteam/job_summary.json) preserves its metadata; `job_failures.json` is empty. Twenty hidden evaluations exit 0 (one contains NaN); three intentionally malformed cases exit 1. Each case records method/train/test commands and exit codes. Every test command is exactly `bash scripts/evaluate_test.sh` with no arguments, in a fresh process after the method process ends. The evaluator is not imported by a method, and no process started by a method persists into evaluation. Runs were bundled in the same job/container for efficiency; this audit did not launch a separate container for each case. No shortcut relies on process state or Python environment changes.

Scientist-side code uses only the visible inventories, names, generator/seed, baseline, reference implementation, and its own produced reference cache. It does not read paper text, hidden test IDs/source, reference scores, or previous hidden-test answers. Paper and hidden-source inspection were used only by the audit and post-test reporting. `reference/scoring_reference.json` and `reference/published_scores_test.json` are reporting-only inputs. Cache-dependent shortcuts can regenerate the visible reference if run individually on a clean checkout; the completed bundle generated it first. Runtime logs and large result caches are ignored; small score files, failure evidence, and statuses are tracked.

All 23 restoration checks passed and recorded evaluator SHA-256 hashes match before/after. Mutable data, method files, score files, and existing result artifacts were restored after each case. Temporary `scripts/run.sh` is restored from the recorded start commit. Pre-existing system-managed README/manifest devices and trajectory deletions are recorded in `redteam/initial_status.txt` and left untouched. The audit's deliverables are `redteam/` and this report; `action.yaml` is the required completion signal.

## Changes needed in the next gym iteration

1. Separate immutable evaluation truth and operating points from scientist inputs. Do not ship regenerable truth seeds or indexed identities. Use independent forests/sessions and opaque randomized names; keep a public training generator and a private independently seeded test generator if using synthetic data.
2. Validate top candidates against the database, reject query self-matches, enforce finite correctly shaped SE(3) transforms and SO(3) rotations, and require exactly one score for each permitted query/database pair. Compute tied-score PR statistics consistently.
3. Enumerate every submitted method with a trusted submission contract. For any failed/missing/invalid method, atomically write every scored metric's finite worst value in every experiment and discard stale output. Do not let a train score file hide additional method artifacts.
4. Preserve the geometric ablation, but restore a recognition problem requiring tree evidence and a localization protocol comparable to the paper. Add substantially larger databases plus independently measured latency and storage constraints if rewarding the paper's efficiency and compactness claims. Recheck the genuine stronger/weaker ordering after these changes.
