#!/usr/bin/env python3
"""Audit orchestration only; never imported by the restored evaluators."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/user')
EXPERIMENT = 'synthetic_forest_localization'
NAMES = [
    'reference_seed_0', 'reference_seed_1', 'reference_seed_2',
    'weaker_no_alignment', 'baseline_tdh', 'stronger_robust_geometry',
    'bruteforce_all_candidates', 'shortcut_visible_poses',
    'shortcut_generator_answers', 'shortcut_self_match',
    'shortcut_serial_identity', 'shortcut_move_thresholds',
    'shortcut_scaled_rotation', 'shortcut_duplicate_pairs',
    'shortcut_replace_ground_truth', 'shortcut_artifact_replay',
    'shortcut_manifest_omission', 'shortcut_forge_scores', 'shortcut_constant',
    'shortcut_nan_translation', 'shortcut_empty_failure',
    'shortcut_null_failure', 'shortcut_missing_artifact',
]


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2))


def execute(cmd, log, env=None):
    started = time.perf_counter()
    with open(log, 'w') as stream:
        p = subprocess.run(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=env)
    return {'exit_code': p.returncode, 'seconds': time.perf_counter() - started,
            'command': cmd}


def perfect_scores(name):
    return {'experiments': {EXPERIMENT: {'results': {name: {
        'R_at_1': 1., 'F1': 1., 'AUC': 1., 'R_at_50': 1., 'SR': 1.,
        'TE_m': 0., 'RE_deg': 0., 'TE_all_m': 0., 'RE_all_deg': 0.}}}}}


def run_one(name):
    out = ROOT / 'redteam' / name
    out.mkdir(exist_ok=True)
    state = ROOT / 'redteam/_state' / name
    state.mkdir(parents=True, exist_ok=True)
    # Backup only paths this run changes. No evaluator file is ever changed.
    paths = [ROOT / p for p in ('data/forest_scenes.json', 'scoring/scores_train.json',
                                'scoring/scores_test.json', 'method/redteam_attempt.py')]
    artifacts = list((ROOT / 'artifacts').glob('*_results.json'))
    existing = {}
    for i, path in enumerate(paths + artifacts):
        if path.exists():
            backup = state / str(i)
            shutil.copy2(path, backup)
            existing[str(path)] = str(backup)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in list((ROOT / 'eval').rglob('*.py')) + [ROOT / 'scripts/evaluate_test.sh']}
    status = {'name': name, 'seed': int(name[-1]) if name.startswith('reference_seed_') else 0,
              'hidden_test_arguments': [], 'evaluator_hashes_before': hashes}
    try:
        for path in artifacts:
            path.unlink()
        for path in paths[1:3]:
            path.unlink(missing_ok=True)
        shutil.copy2(ROOT / 'redteam/attempt.py', ROOT / 'method/redteam_attempt.py')
        env = dict(os.environ, PYTHONHASHSEED=str(status['seed']))
        status['method'] = execute([sys.executable, 'method/redteam_attempt.py', name,
                                    '--seed', str(status['seed'])], out / 'method.log', env)
        if status['method']['exit_code'] != 0:
            raise RuntimeError(f'{name}: method execution failed')
        artifact = ROOT / f'artifacts/{name}_results.json'
        if artifact.exists():
            shutil.copy2(artifact, out / 'results.json')

        # An explicit train selection is part of the visible documented API.
        # In the omission check another invalid method is present on disk.
        status['train'] = execute(['bash', 'scripts/evaluate_train.sh',
                                    f'{name}:artifacts/{name}_results.json'], out / 'train.log')
        if (ROOT / 'scoring/scores_train.json').exists():
            shutil.copy2(ROOT / 'scoring/scores_train.json', out / 'scores_train.json')
        if name in ('shortcut_forge_scores', 'shortcut_empty_failure', 'shortcut_null_failure',
                    'shortcut_missing_artifact'):
            write(ROOT / 'scoring/scores_test.json', perfect_scores(name))
            write(out / 'forged_scores.json', perfect_scores(name))
        if name == 'shortcut_missing_artifact':
            artifact.unlink()
        write(out / 'artifact_inventory.json', [str(p.relative_to(ROOT))
                                               for p in (ROOT / 'artifacts').glob('*_results.json')])
        # Fresh process, no arguments, stock script and eval/test source.
        status['test'] = execute(['bash', 'scripts/evaluate_test.sh'], out / 'test.log')
        scorepath = ROOT / 'scoring/scores_test.json'
        status['scorefile_exists'] = scorepath.exists()
        if scorepath.exists():
            shutil.copy2(scorepath, out / 'scores_test.json')
        status['evaluator_hashes_after'] = {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashes}
        assert hashes == status['evaluator_hashes_after'], 'Evaluator files changed'
    except Exception as e:
        status['error'] = repr(e)
        raise
    finally:
        for path in (ROOT / 'artifacts').glob('*_results.json'):
            path.unlink()
        for path in paths:
            path.unlink(missing_ok=True)
        for path, backup in existing.items():
            shutil.copy2(backup, path)
        status['restored'] = all(Path(p).read_bytes() == Path(b).read_bytes()
                                 for p, b in existing.items())
        write(out / 'status.json', status)
    print(json.dumps({'name': name, 'test_exit_code': status['test']['exit_code'],
                      'method_seconds': status['method']['seconds'],
                      'restored': status['restored']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name', choices=NAMES + ['all'])
    args = parser.parse_args()
    if args.name == 'all':
        failures = []
        for name in NAMES:
            try:
                run_one(name)
            except Exception as exc:
                failures.append([name, repr(exc)])
                print(json.dumps({'failed': name, 'error': repr(exc)}), flush=True)
        write(ROOT / 'redteam/job_failures.json', failures)
    else:
        run_one(args.name)
