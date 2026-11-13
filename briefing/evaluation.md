# Evaluation

## Data

Two experiments, each with a visible train slice (`data/train/`) and a hidden test slice (held by the evaluator only):

| Experiment | Train slice (visible) | Hidden test slice |
|---|---|---|
| `intra_session_localization` | Oxford Evo: database = first 40% of the sequence (934 scenes), queries = later revisits (867) | Oxford Stein am Rhein, a different forest: database = first 50% (523), queries = later revisits (439) |
| `inter_session_localization` | Wild-Places Venman: queries from session V-03, database from session V-02 (~6 months earlier), frames >= 50 m outside the official test regions (493 database / 550 queries) | Same two sessions inside the official Wild-Places Venman test regions (543 / 548) |

A query is evaluated only if at least one database scene lies within 10 m of it, and intra-session queries come at least 50 frames after the end of the database. Scene IDs are random strings and scenes are shuffled. Each input file (`<experiment>.input.json.gz`) holds `tree_fields` and one sequence with `database` and `queries`; every scene is `{"id", "trees"}` with one row per stem: `x y z` (stem centre / base point, local frame, metres), `axis_x axis_y axis_z` (stem axis), `dbh`, `dbh_approximation` (fallback when `dbh` is null), `score`, `reconstructed` (1 = fully reconstructed stem, 0 = candidate stem), `number_clusters`. `data/train/truth.json.gz` holds the train poses (`x y z qx qy qz qw`, scene-to-world) for development only.

## Submission interface

A method is a script `submissions/<name>.sh` invoked from the workspace root as

    bash submissions/<name>.sh INPUT_JSON OUTPUT_JSON

once per experiment. It writes `{"predictions": [...]}` with exactly one entry per query: `{"query": id, "candidate": database id, "score": finite number (higher = more confident), "rotation": 3x3, "translation": [3]}`, where `(rotation, translation)` maps points from the query frame into the candidate's frame. Any malformed output (missing, duplicate or unknown query, a candidate that is not a database scene of that experiment, non-finite numbers, a rotation that is not a proper rotation within 1e-3, a translation beyond 1e6 m), a crash, a timeout (2 h per experiment) or no output gives that method the worst value of every metric of the experiment. Scores are always recomputed by the evaluator from the raw predictions. Runtime is not scored; instead, per-query search is bounded by rule: detailed matching (any transform or correspondence estimation) against at most 100 database scenes per query, independent of database size (`scoring/CONSTRAINTS.md`).

## Metrics (per experiment)

A returned scene is correct if it lies within 10 m (horizontal) of the query. A pose is a success if its 3D translation error is <= 0.5 m and its geodesic rotation error is <= 5 deg (full 6-DoF, measured against the returned scene).

| Metric | Direction | Definition |
|---|---|---|
| `R_at_1` | higher | fraction of queries whose returned scene is correct |
| `F1` | higher | maximum F1 over thresholds on `score`; precision = correct accepted / accepted, recall = correct accepted / all queries |
| `AUC` | higher | area under that precision–recall curve (equal scores share one threshold) |
| `R_at_50` | higher | fraction of queries whose pose is a success |
| `SR` | higher | among queries with a correct scene, fraction whose pose is a success |
| `TE_m`, `RE_deg` | lower | mean translation / rotation error over correct, successful queries (0.5 m / 5 deg if none) |
| `TE_all_m`, `RE_all_deg` | lower | mean error over all queries, each capped at 10 m / 180 deg |

## Scoring scripts

- `bash scripts/evaluate_train.sh [name ...]` runs submissions on the train slice and writes `scoring/scores_train.json` (raw outputs and per-query diagnostics go to `artifacts/train_outputs/<name>/`). `scripts/evaluate.sh` does the same into `scoring/scores.json`.
- `bash scripts/evaluate_test.sh` (no arguments) runs every `submissions/*.sh`, plus any method named in `scoring/scores_train.json` (scored as failed if its script is gone), on the hidden test inputs and writes `scoring/scores_test.json`.

## Baselines and targets

Two reference baselines are scored alongside the paper's method: a global-descriptor-only retrieval baseline that reports an identity pose (`tdh_baseline`), and an ablated variant of the paper's method from its ablation table (`treeloc_no_alignment`). The paper's own numbers (Oxford Stein, Wild-Places Venman) are recorded in `scoring/reference.json`; the gym's protocol differs in details listed there (fixed database split, 6-DoF rather than 3-DoF errors, recall over all queries), so those numbers are context, not targets to match.
