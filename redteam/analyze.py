#!/usr/bin/env python3
"""Post-test reporting; this file is not part of any submitted method."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

ROOT = Path('/home/user/redteam')
EXP = 'synthetic_forest_localization'
reference_schema = json.loads((ROOT / 'reference/scoring_reference.json').read_text())
experiment = reference_schema['experiments'][EXP]
metrics = experiment['metrics']


def get_result(folder):
    score = json.loads((folder / 'scores_test.json').read_text())
    return score.get('experiments', {}).get(EXP, {}).get('results', {}).get(folder.name)


rows = {}
for folder in ROOT.iterdir():
    statuspath = folder / 'status.json'
    if not statuspath.exists():
        continue
    status = json.loads(statuspath.read_text())
    result = get_result(folder) if (folder / 'scores_test.json').exists() else None
    valid = status.get('test', {}).get('exit_code') == 0 and result is not None
    finite = valid and all(isinstance(result.get(key), (int, float))
                           and math.isfinite(result[key]) for key in metrics)
    rows[folder.name] = {'metrics': result, 'test_exit_code': status.get('test', {}).get('exit_code'),
                         'test_succeeded': valid, 'all_metrics_finite': finite,
                         'method_seconds': status.get('method', {}).get('seconds'),
                         'restored': status['restored']}

ref = rows['reference_seed_0']['metrics']
panels = {
    'quality_panel': ['reference_seed_0', 'weaker_no_alignment', 'baseline_tdh',
                      'stronger_robust_geometry', 'bruteforce_all_candidates'],
    'all_finite_attempts_panel': [name for name, row in rows.items() if row['all_metrics_finite']],
}
panel_scales = {}
for panel, names in panels.items():
    names = [name for name in names if rows.get(name, {}).get('all_metrics_finite')]
    scales = {key: statistics.pstdev([rows[name]['metrics'][key] for name in names]) for key in metrics}
    panel_scales[panel] = {'members': names, 'population_standard_deviations': scales}
    for name, row in rows.items():
        if not row['all_metrics_finite']:
            row[panel + '_rank_delta'] = None
            continue
        terms = {key: experiment['weight'] * abs(spec['coefficient'])
                 * (1 if spec['higher_is_better'] else -1)
                 * (row['metrics'][key] - ref[key]) / scales[key]
                 if scales[key] else 0. for key, spec in metrics.items()}
        row[panel + '_rank_delta'] = sum(terms.values())
        row[panel + '_metric_contributions'] = terms

for name, row in rows.items():
    if row['all_metrics_finite']:
        gains = {key: (1 if spec['higher_is_better'] else -1) * (row['metrics'][key] - ref[key])
                 for key, spec in metrics.items()}
        row['direction_adjusted_changes'] = gains
        row['componentwise_no_worse_than_reference'] = all(v >= -1e-10 for v in gains.values())
        row['exact_metric_tie'] = all(abs(v) < 1e-10 for v in gains.values())

seed_names = [f'reference_seed_{i}' for i in range(3)]
seed_spread = {key: {'min': min(rows[name]['metrics'][key] for name in seed_names),
                     'max': max(rows[name]['metrics'][key] for name in seed_names),
                     'range': max(rows[name]['metrics'][key] for name in seed_names)
                              - min(rows[name]['metrics'][key] for name in seed_names)}
               for key in metrics}
rank_spread = {panel: max(rows[name][panel + '_rank_delta'] for name in seed_names)
                     - min(rows[name][panel + '_rank_delta'] for name in seed_names)
               for panel in panels}
published = json.loads((ROOT / 'reference/published_scores_test.json').read_text())
published_ref = published['experiments'][EXP]['results']['treeloc']
output = {'reference': ref, 'published_reference': published_ref,
          'published_reference_difference': {key: ref[key] - published_ref[key] for key in metrics},
          'scored_metrics_at_bound': [key for key, spec in metrics.items()
                                      if (spec['higher_is_better'] and ref[key] == 1.)
                                      or (not spec['higher_is_better'] and ref[key] == 0.)],
          'seed_metric_spread': seed_spread, 'seed_rank_spread': rank_spread,
          'rank_panels': panel_scales, 'attempts': rows,
          'notes': ['Rank deltas are audit-panel normalized, not unknown future-population ranks.',
                    'Absolute coefficient values and declared directions are used.',
                    'Nonzero test exits are not counted as successful shortcuts, even when forged scores survive.',
                    'NaN rank treatment is unspecified externally; no success claimed for nonfinite values.']}
(ROOT / 'analysis.json').write_text(json.dumps(output, indent=2))
for name, row in rows.items():
    print(json.dumps({'name': name, 'test_exit_code': row['test_exit_code'],
                      'rank_delta': row['all_finite_attempts_panel_rank_delta'],
                      'R_at_50': (row['metrics'] or {}).get('R_at_50')}))
