# Scientist Constraints

## Data
Use only the provided benchmark files. The train slice in `data/train/` is visible (inputs and poses); the hidden test inputs and answers live in `eval/test/` and must not be read, copied, or reconstructed by a method. Do not fetch or bundle the upstream source of these inventories (or their trajectories / poses) into a method: that is an answer key for the hidden test, not a localization method.

## Evaluation
Score through `scripts/evaluate_train.sh` and `scripts/evaluate_test.sh` only. Do not modify `eval/`, the files in `data/train/` or `eval/test/data/`, the 10 m correctness radius, the 0.5 m / 5 deg pose thresholds, or the database/query splits. The evaluator recomputes every number from your raw predictions; score files written by a method are discarded or restored.

## Inputs
At test time a method sees one experiment's input file: the tree inventories of the database and query scenes, in local frames, under random IDs. It must not use scene poses, time order, or any knowledge of which hidden scenes correspond. No training happens on the hidden test; any parameter fitting must use the train slice.

## Outputs
Exactly one prediction per query: a database scene of the same experiment, a finite confidence score, a proper 3x3 rotation and a finite translation (query frame into candidate frame). Anything else scores the worst value of every metric of that experiment.

## Compliance Checklist
- [ ] The method is registered as `submissions/<name>.sh INPUT_JSON OUTPUT_JSON` and reads only its input file plus code/parameters in the workspace.
- [ ] Nothing under `eval/test/` (or any copy of the upstream poses) is read by the method.
- [ ] `eval/`, `data/train/`, thresholds and splits are unchanged.
- [ ] Reported numbers come from `scripts/evaluate_test.sh` / `scripts/evaluate_train.sh`.
