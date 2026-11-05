#!/usr/bin/env python3
"""Run isolated release checks and publish a reproducible report; never reset user state."""
import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from statistics import median
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pulse import __version__
from pulse.config import Settings
from pulse.evaluation.fixtures import evaluate
from pulse.evaluation.rehearsal import rehearse
from pulse.repository import SourceRepository
from scripts.generate_data import generate


def atomic_json(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n')
    os.replace(temp, path)


def write_summary(path, report):
    counts = report['fixture_evaluation']['status_counts']
    lines = ['# Recorded release verification', '', f"Application: {report['application_version']}. Generated: {report['generated_at']}.", '',
             'Status: **review ready with verification gaps**.' if report['status'] != 'verification_failed' else 'Status: **verification failed**.', '',
             '## Automated checks', '', '| Check | Status | Tests | Elapsed seconds |', '|---|---|---:|---:|']
    for row in report['checks']:
        lines.append(f"| {row['name']} | {row['status']} | {row.get('test_count') or '—'} | {row.get('elapsed_seconds', '—')} |")
    lines += ['', '## Synthetic fixtures', '', f"{counts['passed']} fully matched, {counts['partial']} partial, {counts['failed']} mismatched, {counts['error']} adapter errors. No pooled accuracy claim.", '',
              '| Family | Split | TP / FP / FN / TN | Precision | Recall |', '|---|---|---|---:|---:|']
    def percent(value):
        return '—' if value is None else f'{value:.1%}'
    for row in report['fixture_evaluation']['families']:
        matrix = ' / '.join(str(row[key]) for key in ('true_positive', 'false_positive', 'false_negative', 'true_negative'))
        lines.append(f"| {row['family']} | {row['split']} | {matrix} | {percent(row['precision'])} | {percent(row['recall'])} |")
    lines += ['', '## API timings', '', 'Three in-process HTTP samples; excludes browser layout, network transit and human review.', '',
              '| Operation | Median seconds | Min–max seconds |', '|---|---:|---:|']
    for key in ('analysis_cold', 'analysis_cached', 'simulation_context', 'simulate_hybrid', 'brief_fallback', 'brief_cached', 'approve', 'close'):
        row = report['timings_seconds'][key]
        lines.append(f"| {key} | {row['median']:.3f} | {row['min']:.3f}–{row['max']:.3f} |")
    lines += ['', '## Rehearsal and outstanding gates', '',
              f"Three API rehearsals: {sum(r['status'] == 'passed' for r in report['rehearsals'])}/3 passed. Identical core arithmetic: {report['three_runs_identical_core_facts']}.", '']
    lines += [f"- {key}: {'passed' if value else 'outstanding'}" for key, value in report['release_gates'].items()]
    lines += ['', '## Claim limits', ''] + ['- ' + text for text in report['claim_limits']]
    lines += ['', 'The Access late-arrival fixture remains mismatched pending label/data-contract review. See the JSON report for every expected/observed value and unsupported field.', '']
    path.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/validation/release_report.json')
    parser.add_argument('--reports-only', action='store_true', help='Run evaluation/rehearsals without rerunning regression/build checks; report those checks as not run')
    args = parser.parse_args()
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('Node.js/npm are required; follow the application setup guide')
    started = perf_counter()
    checks = []
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    commands = [('python_regressions', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']),
                ('frontend_components', [npm, '--prefix', 'apps/web', 'test']),
                ('production_build', [npm, '--prefix', 'apps/web', 'run', 'build']),
                ('live_http_react', [sys.executable, 'scripts/smoke_workspace.py'])]
    if not args.reports_only:
        logs = ROOT / 'data/verification/logs'
        logs.mkdir(parents=True, exist_ok=True)
        for name, command in commands:
            t = perf_counter()
            with (logs / (name + '.log')).open('w') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            log_text = (logs / (name + '.log')).read_text()
            match = re.search(r'Ran (\d+) tests', log_text) if name == 'python_regressions' else re.search(r'Tests\s+(\d+) passed', log_text)
            checks.append({'name': name, 'status': 'passed' if result.returncode == 0 else 'failed',
                           'test_count': int(match.group(1)) if match else None,
                           'elapsed_seconds': round(perf_counter() - t, 3)})
            print(json.dumps(checks[-1]), flush=True)
            if result.returncode:
                atomic_json(output, {'schema_version': 1, 'status': 'verification_failed', 'checks': checks})
                raise RuntimeError(f'{name} failed; inspect data/verification/logs/{name}.log')
    else:
        checks = [{'name': name, 'status': 'not_run'} for name, _ in commands]
    with tempfile.TemporaryDirectory(prefix='pulse-release-') as folder:
        root = Path(folder)
        settings = Settings.load({'PULSE_AS_OF': '2026-11-05T14:00:00Z', 'PULSE_TIMEZONE': 'America/Chicago'}, root)
        with contextlib.redirect_stdout(io.StringIO()):
            generate(42, settings.data_dir)
        tables = SourceRepository(settings.database_path).snapshot(settings.as_of)
        fixtures = json.loads((settings.data_dir / 'evaluation_cases.json').read_text())
        evaluation = evaluate(fixtures['cases'], tables)
        print(json.dumps({'fixture_status_counts': evaluation['status_counts']}), flush=True)
        known = json.loads((ROOT / 'docs/validation/known_gaps.json').read_text())['discrepancies']
        unexpected = [r['case_id'] for r in evaluation['cases'] if r['status'] == 'error' or
                      (r['status'] == 'failed' and r['mismatches'] != known.get(r['case_id'], {}).get('mismatches'))]
        runs = []
        for i in range(1, 4):
            runs.append(rehearse(settings, root / ('rehearsal-' + str(i)), i))
            print(json.dumps({'rehearsal': i, 'status': runs[-1]['status']}), flush=True)
        consistent = len({r['core_facts_hash'] for r in runs}) == 1
        timings = {key: {'samples': [r['timings_seconds'][key] for r in runs],
                         'min': min(r['timings_seconds'][key] for r in runs),
                         'max': max(r['timings_seconds'][key] for r in runs),
                         'median': median(r['timings_seconds'][key] for r in runs)} for key in runs[0]['timings_seconds']}
        report = {'schema_version': 1, 'application_version': __version__, 'generated_at': datetime.now(timezone.utc).isoformat(),
                  'status': 'review_ready_with_verification_gaps' if consistent and not unexpected and all(r['status'] == 'passed' for r in runs) else 'verification_failed',
                  'dataset': {'seed': 42, 'as_of': settings.as_of, 'input_hash': runs[0]['input_hash'], 'engine_version': runs[0]['engine_version']},
                  'checks': checks, 'fixture_evaluation': evaluation, 'known_discrepancies': known, 'unexpected_discrepancies': unexpected, 'rehearsals': runs,
                  'three_runs_identical_core_facts': consistent, 'timings_seconds': timings,
                  'targets': {'simulation_under_one_second': all(t < 1 for t in timings['simulate_hybrid']['samples']),
                              'warm_analysis_under_two_seconds': all(t < 2 for t in timings['analysis_cached']['samples']),
                              'cached_brief_under_one_second': all(t < 1 for t in timings['brief_cached']['samples'])},
                  'claim_limits': ['Synthetic component challenges; not production accuracy or clinical validation',
                                   'Tune/holdout labels were generated before the engine but were visible during development; not a blind held-out study',
                                   'Live source delivery freshness is unmeasured; unsupported fixture fields remain partial',
                                   'No real-model inference or visual browser verification was completed',
                                   'The simulation holdout has no feasible positive case; its precision/recall are undefined',
                                   'API timing samples use an in-process HTTP test client; exclude browser layout, network transit and human investigation time',
                                   'Atomic findings grouped by investigation are not a measured alert-noise or precision improvement'],
                  'release_gates': {'automated_regressions': not args.reports_only and all(c['status'] == 'passed' for c in checks),
                                    'repeatable_demo_api': consistent and all(r['status'] == 'passed' for r in runs),
                                    'no_unexpected_fixture_discrepancies': not unexpected,
                                    'all_fixture_cases_fully_matched': evaluation['status_counts']['passed'] == len(fixtures['cases']),
                                    'visual_browser_verified': False, 'live_model_verified': False},
                  'total_seconds': round(perf_counter() - started, 3)}
        atomic_json(output, report)
        write_summary(output.with_suffix('.md'), report)
        if report['status'] == 'verification_failed' or unexpected:
            raise RuntimeError('Release verification failed; inspect the generated report')
    print(json.dumps({'report': str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output), 'status': report['status']}))


if __name__ == '__main__':
    main()
