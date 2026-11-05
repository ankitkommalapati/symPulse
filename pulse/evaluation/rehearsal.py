"""Isolated, timed API rehearsal of the real demo lifecycle, without external inference."""
from pathlib import Path
from time import perf_counter
from dataclasses import replace
from fastapi.testclient import TestClient
from pulse.api import create_app
from pulse.explanations.provider import ModelConfig
from pulse.intelligence.engine import content_hash


class RehearsalFailure(RuntimeError):
    pass


def rehearse(settings, folder, repeat=1):
    settings = replace(settings, evidence_dir=Path(folder) / 'evidence', workflow_path=Path(folder) / 'workflow.sqlite')
    app = create_app(settings)
    app.state.explanations.config = ModelConfig()
    timings, steps = {}, []
    with TestClient(app) as client:
        def request(name, method, path, body=None, expected=200):
            start = perf_counter()
            result = client.request(method, path, json=body) if body is not None else client.request(method, path)
            timings[name] = round(perf_counter() - start, 6)
            if result.status_code != expected:
                raise RehearsalFailure(f'{name}: HTTP {result.status_code}: {result.text[:200]}')
            steps.append(name)
            return result.json()
        request('ready', 'GET', '/health/ready')
        analysis = request('analysis_cold', 'GET', '/api/intelligence/units')
        request('analysis_cached', 'GET', '/api/intelligence/units')
        path = '/api/investigations/FAC-01:ICU:readiness'
        packet = request('investigation', 'GET', path)
        context = request('simulation_context', 'GET', path + '/simulation')
        simulation = request('simulate_hybrid', 'POST', path + '/simulate', {'snapshot_id': packet['snapshot_id'], 'kind': 'hybrid'})
        brief = request('brief_fallback', 'POST', path + '/explain', {'snapshot_id': packet['snapshot_id']})
        cached = request('brief_cached', 'POST', path + '/explain', {'snapshot_id': packet['snapshot_id']})
        plan = request('create_plan', 'POST', '/api/plans', {'simulation_id': simulation['simulation_id'], 'snapshot_id': packet['snapshot_id'], 'idempotency_key': f'rehearsal-{repeat:04d}-response-plan'}, 201)
        initial_tasks = len(plan['tasks'])
        plan_path = '/api/plans/' + plan['id']
        for action in ('submit', 'approve', 'simulate_implementation', 'monitor'):
            plan = request(action, 'POST', plan_path + '/transition', {'expected_version': plan['version'], 'snapshot_id': packet['snapshot_id'], 'transition': action, 'acknowledge_demo': True, 'note': 'Explicit isolated demo rehearsal step.'})
        request('reject_unfinished_closure', 'POST', plan_path + '/transition', {'expected_version': plan['version'], 'snapshot_id': packet['snapshot_id'], 'transition': 'close', 'acknowledge_demo': True, 'note': 'Closure must fail with unfinished work.'}, 409)
        for task in plan['tasks']:
            plan = request('complete_' + task['id'], 'POST', plan_path + '/tasks/' + task['id'] + '/complete', {'expected_version': plan['version'], 'snapshot_id': packet['snapshot_id'], 'acknowledge_demo': True, 'note': 'Synthetic task outcome recorded for isolated demo rehearsal.'})
        plan = request('close', 'POST', plan_path + '/transition', {'expected_version': plan['version'], 'snapshot_id': packet['snapshot_id'], 'transition': 'close', 'acknowledge_demo': True, 'note': 'All synthetic follow-up outcomes are recorded; this closes the demo workflow only.'})
        current = request('source_still_unresolved', 'GET', path)
        artifact = request('saved_simulation', 'GET', simulation['artifact_url'])
    restarted = create_app(settings)
    restarted.state.explanations.config = ModelConfig()
    with TestClient(restarted) as client:
        saved = client.get(plan_path).json()
        restored = saved.get('state') == 'closed' and len(saved.get('audit', [])) == saved.get('version')
    plans = {r['kind']: r for r in context['plans']}
    facts = {'rn_gap': packet['metrics']['coverage']['uncovered_rn_hours'],
             'physician_exposure_hours': packet['metrics']['provider']['uncovered_physician_hours'],
             'reassignment_residual_rn_hours': plans['reassignment']['modeled_uncovered_rn_hours'],
             'reassignment_employees': [r['employee_id'] for r in plans['reassignment']['actions']],
             'hybrid_incremental_cost_usd': simulation['result']['incremental_cost_usd'],
             'agency_incremental_cost_usd': plans['agency']['incremental_cost_usd'],
             'hybrid_modeled_residual_rn_hours': simulation['result']['modeled_uncovered_rn_hours'],
             'hybrid_gap_without_unverified_capacity': simulation['result']['gap_without_unverified_capacity'],
             'donor_gap_rn_hours': plans['reassignment']['donor_checks'][0]['uncovered_rn_hours'],
             'source_gap_after_demo_closure': current['metrics']['coverage']['uncovered_rn_hours'],
             'restored_plan_state': saved.get('state'), 'task_count': initial_tasks,
             'brief_status': brief['status']}
    checks = {'rn_gap_36': facts['rn_gap'] == 36, 'physician_hours_19': facts['physician_exposure_hours'] == 19,
              'reassignment_residual_12': facts['reassignment_residual_rn_hours'] == 12,
              'donor_preserved': facts['donor_gap_rn_hours'] == 0,
              'modeled_costs_reconcile': facts['agency_incremental_cost_usd'] - facts['hybrid_incremental_cost_usd'] == 2640,
              'hybrid_modeled_gap_zero': facts['hybrid_modeled_residual_rn_hours'] == 0,
              'unverified_capacity_still_visible': facts['hybrid_gap_without_unverified_capacity'] == 12,
              'source_still_unresolved': facts['source_gap_after_demo_closure'] == 36,
              'offline_brief_and_cache': brief['status'] == 'fallback' and cached['cache_hit'],
              'restart_restores_audit': restored, 'simulation_evidence_matches': artifact['result'] == simulation['result']}
    return {'repeat': repeat, 'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks, 'facts': facts,
            'core_facts_hash': content_hash(facts), 'timings_seconds': timings, 'step_count': len(steps),
            'atomic_reason_count': sum(len(u['reason_codes']) for u in analysis['units']),
            'investigation_count': sum(u['investigation_id'] is not None for u in analysis['units']),
            'input_hash': packet['input_hash'], 'engine_version': packet['engine_version']}
