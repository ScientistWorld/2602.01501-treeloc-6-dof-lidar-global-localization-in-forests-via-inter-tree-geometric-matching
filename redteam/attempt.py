#!/usr/bin/env python3
"""Scientist-side methods and explicitly named shortcuts. No test imports."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import pickle
import random
import sys
import time
from pathlib import Path

ROOT = Path('/home/user')
CACHE = ROOT / 'redteam/cache'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def identity():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def cached_reference(data):
    """Reuse the visible reference, or build it for a standalone shortcut run."""
    path = CACHE / 'reference_results.json'
    if not path.exists():
        model = load_module(ROOT / 'redteam/reference/treeloc.py', 'audit_treeloc')
        write(path, model.run_treeloc(data, 100, 10, True, True))
    return read(path)


def serial(name):
    return int(name.rsplit('_', 1)[1])


def constant(data, name, self_match=False):
    return {
        'method': name,
        'predictions': [
            {'query': q['name'],
             'candidate': q['name'] if self_match else data['database'][0]['name'],
             'estimated_query_to_candidate': {'translation': [0., 0., 0.], 'yaw': 0.}}
            for q in data['query']],
        'pair_scores': [
            {'query': q['name'], 'candidate': c['name'],
             'score': -abs(serial(q['name']) - serial(c['name'])) if self_match else 0.}
            for q in data['query'] for c in data['database']]}


def oracle(data, name):
    # Shortcut: labels and rigid transforms come directly from visible poses.
    import numpy as np
    predictions, pair_scores = [], []
    for q in data['query']:
        qp = np.asarray(q['pose'])
        ordered = sorted(data['database'], key=lambda c: math.dist(
            [row[3] for row in q['pose'][:3]], [row[3] for row in c['pose'][:3]]))
        candidate = ordered[0]
        cp = np.asarray(candidate['pose'])
        rotation = cp[:3, :3].T @ qp[:3, :3]
        translation = cp[:3, :3].T @ (qp[:3, 3] - cp[:3, 3])
        predictions.append({'query': q['name'], 'candidate': candidate['name'],
                            'estimated_query_to_candidate': {
                                'rotation': rotation.tolist(), 'translation': translation.tolist()}})
        for c in data['database']:
            distance = math.dist([row[3] for row in q['pose'][:3]],
                                 [row[3] for row in c['pose'][:3]])
            pair_scores.append({'query': q['name'], 'candidate': c['name'], 'score': -distance})
    return {'method': name, 'predictions': predictions, 'pair_scores': pair_scores}


def descriptors(data, model):
    cached = CACHE / 'descriptors.pkl'
    if cached.exists():
        return pickle.loads(cached.read_bytes())
    # Pose is deliberately erased: honest variants use only local tree fields.
    scenes = {s['name']: model.make_scene(dict(s, pose=identity()))
              for split in ('query', 'database') for s in data[split]}
    cached.write_bytes(pickle.dumps(scenes))
    return scenes


def rigid_align(src, dst):
    import numpy as np
    sm, dm = src.mean(0), dst.mean(0)
    u, _, vt = np.linalg.svd((src - sm).T @ (dst - dm))
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    return r, dm - r @ sm


def robust_geometry(query, cand, qraw, craw, model):
    """Real fix: reject centroid outliers, then refine valid SE(3) geometry."""
    import numpy as np
    common = sorted(query.triangles.keys() & cand.triangles.keys())
    fallback = model.verify(query, cand)
    if len(common) < 2:
        return fallback
    a = np.asarray([query.triangles[k][-1][0] for k in common])
    b = np.asarray([cand.triangles[k][-1][0] for k in common])
    rng = random.Random(100000 * serial(query.name) + serial(cand.name))

    def support(r, t):
        transformed = query.centers @ r.T + t
        distance = ((transformed[:, None, :] - cand.centers[None, :, :]) ** 2).sum(2)
        ci = distance.argmin(1)
        qi = np.flatnonzero((distance[np.arange(len(ci)), ci] <= .4**2)
                           & (np.abs(query.dbh - cand.dbh[ci]) <= .2))
        return qi, ci[qi]

    best = (0, None, None)
    # Include the original least-squares estimate and 96 deterministic
    # two-centroid hypotheses. The data and all thresholds stay fixed.
    transforms = [model.se2_align(a, b)]
    for _ in range(96):
        i, j = rng.sample(range(len(common)), 2)
        av, bv = a[j] - a[i], b[j] - b[i]
        if min(np.linalg.norm(av), np.linalg.norm(bv)) < 1.:
            continue
        angle = math.atan2(bv[1], bv[0]) - math.atan2(av[1], av[0])
        r = np.array([[math.cos(angle), -math.sin(angle)],
                      [math.sin(angle), math.cos(angle)]])
        transforms.append((r, b[i] - r @ a[i]))
    for r, t in transforms:
        qi, ci = support(r, t)
        if len(qi) > best[0]:
            best = len(qi), qi, ci
    count, qi, ci = best
    if count < 3:
        return fallback
    qp = np.asarray([tree['position'] for tree in qraw['trees']])
    cp = np.asarray([tree['position'] for tree in craw['trees']])
    r, t = rigid_align(qp[qi], cp[ci])
    for _ in range(3):
        transformed = qp @ r.T + t
        distance = ((transformed[:, None, :] - cp[None, :, :]) ** 2).sum(2)
        ci = distance.argmin(1)
        qi = np.flatnonzero((distance[np.arange(len(ci)), ci] <= .4**2)
                           & (np.abs(query.dbh - cand.dbh[ci]) <= .2))
        if len(qi) < 3:
            break
        r, t = rigid_align(qp[qi], cp[ci[qi]])
    count = len(qi)
    overlap = count / max(1, len(qp) + len(cp) - count)
    if overlap < fallback.get('overlap', 0):
        return fallback
    return {'overlap': overlap, 'num_matches': count,
            'rotation': r.tolist(), 'translation': t.tolist()}


def improved_or_bruteforce(data, model, name, stronger):
    import numpy as np
    scenes = descriptors(data, model)
    predictions, pair_scores = [], []
    diagnostics = []
    for qraw in data['query']:
        query = scenes[qraw['name']]
        verified = []
        # Exhaust every database candidate: there are only 56, fewer than
        # the paper's normal coarse candidate budget of 100.
        for craw in data['database']:
            cand = scenes[craw['name']]
            v = (robust_geometry(query, cand, qraw, craw, model) if stronger
                 else model.verify(query, cand))
            distance = float(np.linalg.norm(v['translation']))
            overlap = v['overlap']
            fine = model.fine_score(query, cand)
            coarse = model.chi_square(query.tdh, cand.tdh)
            if stronger:
                supported = v.get('num_matches', 0) >= 6 and overlap >= .10
                score = -distance if supported else -1000. + overlap
                key = (supported and distance <= 10., overlap, fine, -coarse)
            else:
                score = fine - .02 * coarse
                key = (overlap, fine, -coarse)
            pair_scores.append({'query': query.name, 'candidate': cand.name, 'score': score})
            verified.append((key, cand.name, v))
        _, best, v = max(verified, key=lambda item: item[0])
        predictions.append({'query': query.name, 'candidate': best,
                            'estimated_query_to_candidate': v})
        diagnostics.append({'query': query.name, 'candidates_verified': len(verified)})
    write(ROOT / 'redteam' / name / 'geometry_diagnostics.json', diagnostics)
    return {'method': name, 'predictions': predictions, 'pair_scores': pair_scores}


def run(name, seed):
    data = read(ROOT / 'data/forest_scenes.json')
    random.seed(seed)
    if name.startswith('reference_seed_'):
        import numpy as np
        np.random.seed(seed)
        model = load_module(ROOT / 'redteam/reference/treeloc.py', 'audit_treeloc')
        result = model.run_treeloc(data, 100, 10, True, True)
        if seed == 0:
            write(CACHE / 'reference_results.json', result)
    elif name == 'weaker_no_alignment':
        model = load_module(ROOT / 'redteam/reference/treeloc.py', 'audit_treeloc')
        result = model.run_treeloc(data, 100, 10, False, True)
    elif name in ('stronger_robust_geometry', 'bruteforce_all_candidates'):
        model = load_module(ROOT / 'redteam/reference/treeloc.py', 'audit_treeloc')
        result = improved_or_bruteforce(data, model, name, name == 'stronger_robust_geometry')
    elif name == 'baseline_tdh':
        import subprocess
        subprocess.run([sys.executable, str(ROOT / 'redteam/reference/tdh_baseline.py'),
                        '--output', f'artifacts/{name}_results.json'], check=True)
        return
    elif name == 'shortcut_visible_poses':
        result = oracle(data, name)
    elif name == 'shortcut_generator_answers':
        generator = load_module(ROOT / 'data/generate_synthetic_forest.py', 'visible_generator')
        # Shortcut: reconstruct all answers from the visible public seed;
        # do not read poses from the input benchmark in this branch.
        result = oracle(generator.build_sequences(11), name)
    elif name == 'shortcut_self_match':
        result = constant(data, name, self_match=True)
    elif name in ('shortcut_serial_identity', 'shortcut_move_thresholds'):
        # Shortcut: adjacent sequence names encode locations. No tree
        # attributes are read and no relative pose is estimated.
        result = constant(data, name, self_match=True)
        for pred in result['predictions']:
            pred['candidate'] = f"db_{serial(pred['query']):03d}"
        if name == 'shortcut_move_thresholds':
            data['localization_translation_threshold_m'] = 1e6
            data['localization_rotation_threshold_deg'] = 1e6
            write(ROOT / 'data/forest_scenes.json', data)
    elif name == 'shortcut_replace_ground_truth':
        for split in ('query', 'database'):
            for scene in data[split]:
                scene['pose'] = identity()
        write(ROOT / 'data/forest_scenes.json', data)
        result = constant(data, name)
    elif name in ('shortcut_scaled_rotation', 'shortcut_duplicate_pairs',
                  'shortcut_artifact_replay', 'shortcut_manifest_omission',
                  'shortcut_missing_artifact'):
        result = cached_reference(data)
        if name == 'shortcut_scaled_rotation':
            for pred in result['predictions']:
                pred['estimated_query_to_candidate']['rotation'] = [
                    [1000000. * (i == j) for j in range(3)] for i in range(3)]
        elif name == 'shortcut_duplicate_pairs':
            # Shortcut: duplicate likely positives by scene ordinal, using
            # no poses. Completeness validation checks sets, not multiplicity.
            duplicates = [{'query': q['name'], 'candidate': f"db_{serial(q['name']):03d}",
                           'score': 1000000.}
                          for q in data['query'] for _ in range(300)]
            result['pair_scores'] = duplicates + result['pair_scores']
        elif name == 'shortcut_artifact_replay':
            # Leave a method that fails if asked to infer. Only cached JSON
            # is presented, to show the test does not execute method code.
            (ROOT / 'method/redteam_attempt.py').write_text(
                "raise RuntimeError('shortcut replay: no inference method remains')\n")
        elif name == 'shortcut_manifest_omission':
            write(ROOT / 'artifacts/unscored_failing_method_results.json',
                  {'method': 'shortcut_unscored_failing_method', 'predictions': [], 'pair_scores': []})
    elif name in ('shortcut_constant', 'shortcut_forge_scores'):
        result = constant(data, name)
        if name == 'shortcut_forge_scores':
            result.update({'success': True, 'runtime_seconds': 0.,
                           'results': {'R_at_1': 1., 'R_at_50': 1., 'TE_m': 0.}})
    elif name in ('shortcut_empty_failure', 'shortcut_null_failure'):
        result = {'method': name, 'predictions': [], 'pair_scores': []}
        if name == 'shortcut_null_failure':
            result = constant(data, name)
            for pair in result['pair_scores']:
                pair['score'] = None
    elif name == 'shortcut_nan_translation':
        result = cached_reference(data)
        # Make only translations non-finite. JSON accepts NaN by default.
        for pred in result['predictions']:
            pred['estimated_query_to_candidate']['translation'] = [float('nan')] * 3
    else:
        raise ValueError(name)
    result['method'] = name
    write(ROOT / f'artifacts/{name}_results.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    run(args.name, args.seed)
    print(json.dumps({'name': args.name, 'seed': args.seed,
                      'method_seconds': time.perf_counter() - started}))
