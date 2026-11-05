"""Adapt declared fixture inputs to operational records, then score actual engine outputs."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pulse.intelligence.engine import Evidence, IntelligenceEngine
from pulse.intelligence.rules import instant, overtime_drift, stamp
from pulse.simulation.engine import Simulator

CLOCK = '2026-11-05T14:00:00Z'
FRESHNESS_LIMIT = 'Live source-delivery freshness is not measured by the archive engine'


def known(tables):
    return {key: [r for r in rows if instant(r['available_at']) <= instant(CLOCK)] for key, rows in tables.items()}


def engine(tables):
    return IntelligenceEngine(known(tables), CLOCK, 'America/Chicago')


def run_input(family, inputs, base):
    """Only family/input are accepted here; no case name, split or expected label."""
    tables = deepcopy(base)
    unit = next(r for r in tables['units'] if r['unit_id'] == 'ICU')
    unsupported = {}
    details = {}
    if family == 'drift':
        points = [{'date': (date(2026, 8, 7) + timedelta(days=i)).isoformat(), 'share': value}
                  for i, value in enumerate(inputs['overtime_share'])]
        result = overtime_drift(points)
        output = {'finding': result['detected'], 'data_issue': result['status'] in ('insufficient_history', 'incomplete_history')}
        details = {'method': result['method'], 'first_breach_work_date': result['first_breach_work_date']}
        if not inputs['fresh']:
            unsupported['data_issue'] = FRESHNESS_LIMIT
    elif family == 'provider':
        assignment = deepcopy(next(r for r in tables['physician_assignments'] if r['source_record_id'].endswith('2026-11-06-DAY') and r['physician_code'] == 'DOC-001'))
        assignment.update(starts_at=inputs['assignment_start'], ends_at=inputs['assignment_end'])
        tables['physician_assignments'] = [assignment]
        grant = deepcopy(next(r for r in tables['privilege_grants'] if r['provider_key'] == 'P001'))
        grant['valid_to'] = inputs['grant_end']
        if not inputs['grant_facility_matches']:
            mapping = deepcopy(next(r for r in tables['entity_crosswalk'] if r['entity_type'] == 'facility' and r['source_namespace'] == 'provider'))
            mapping.update(record_id='fixture:other-facility', source_entity_id='OTHER', canonical_id='FAC-OTHER')
            tables['entity_crosswalk'].append(mapping)
            grant['facility_code'] = 'OTHER'
        tables['privilege_grants'] = [grant]
        tables['renewal_cases'] = [dict(r, workflow_status=inputs['renewal_status']) for r in tables['renewal_cases'] if r['provider_key'] == 'P001']
        result = engine(tables).provider_readiness(unit, Evidence())
        output = {'finding': bool(result['findings'])}
        details = {'uncovered_physician_hours': result['uncovered_physician_hours']}
    elif family == 'access':
        visit = deepcopy(next(r for r in tables['vendor_visits'] if r['source_record_id'] == 'VISIT-HERO'))
        if not inputs['unit_matches']:
            visit['destination_code'] = 'A-02'
        tables['vendor_visits'] = [visit]
        credentials = [r for r in tables['vendor_credentials'] if r['representative_key'] == visit['representative_key']]
        for row in credentials:
            row['verification_status'] = inputs['verification_status']
            if not inputs['available_by_clock']:
                row['available_at'] = '2026-11-05T15:00:00Z'
        if inputs['verification_status'] == 'missing':
            credentials = []
        tables['vendor_credentials'] = credentials
        result = engine(tables).access_readiness(unit, Evidence())
        output = {'finding': bool(result['findings']), 'data_issue': bool(result['data_issues'])}
        if not inputs['fresh'] or not inputs['available_by_clock']:
            unsupported['data_issue'] = FRESHNESS_LIMIT + '; missing approval is not a reliable feed-freshness signal'
        details = {'unapproved_requirements': [r['unapproved_requirements'] for r in result['findings']]}
    elif family == 'simulation':
        target = next(r for r in tables['staffing_requirements'] if r['organization_code'] == '120' and r['shift_start'] == '2026-11-06T13:00:00Z')
        donor_rows = sorted([r for r in tables['workforce_assignments'] if r['organization_code'] == '120' and r['shift_start'] == target['shift_start']], key=lambda r: r['employee_number'])
        selected = donor_rows[:inputs['requested_moves']]
        removed = {r['record_id'] for r in donor_rows[inputs['donor_assigned']:]}
        tables['workforce_assignments'] = [r for r in tables['workforce_assignments'] if r['record_id'] not in removed]
        target['required_count'] = inputs['donor_required']
        employee = selected[0]['employee_number']
        if not inputs['competency_valid']:
            for row in tables['employee_qualifications']:
                if row['employee_number'] == employee and row['qualification_code'] == 'ICU_COMPETENCY':
                    row['qualification_status'] = 'unverified'
        if inputs['has_overlap']:
            tables['workforce_assignments'].append({**selected[0], 'record_id': 'fixture:conflicting-assignment'})
        if inputs['rest_hours'] < 12:
            previous = max([r for r in tables['workforce_assignments'] if r['employee_number'] == employee and instant(r['shift_end']) <= instant(target['shift_start'])], key=lambda r: instant(r['shift_end']))
            previous['shift_end'] = stamp(instant(target['shift_start']) - timedelta(hours=inputs['rest_hours']))
        if inputs['approved_unavailability']:
            template = deepcopy(tables['unavailability'][0])
            template.update(record_id='fixture:donor-absence', employee_number=employee, start=target['shift_start'], end=target['shift_end'], status='approved')
            tables['unavailability'].append(template)
        prepared = engine(tables)
        packet = prepared.analyze()['investigations']['FAC-01:ICU:readiness']
        result = Simulator(known(tables), packet, 'America/Chicago').evaluate('reassignment', [r['employee_number'] for r in selected])
        output = {'feasible': result['status'] == 'feasible'}
        details = {'status': result['status'], 'residual_rn_hours': result['modeled_uncovered_rn_hours'], 'rejected': result['rejected_candidates']}
    elif family == 'quality':
        original = engine(tables).quality(unit, Evidence())
        baseline = date.fromisoformat(original['baseline_window']['start'])
        current = date.fromisoformat(original['current_window']['start'])
        event_template = deepcopy(next(r for r in tables['quality_events'] if r['location_code'] == 'ICU-A'))
        activity_template = deepcopy(next(r for r in tables['unit_activity'] if r['unit_id'] == 'ICU'))
        events, activity = [], []
        for period, start in [('baseline', baseline), ('current', current)]:
            for i in range(inputs[period + '_reports']):
                row = {**event_template, 'record_id': f'fixture:quality:{period}:{i}', 'workflow_status': 'submitted', 'event_type': 'near_miss',
                       'occurred_at': (datetime.combine(start + timedelta(days=i % 21), datetime.min.time(), timezone.utc) + timedelta(hours=18)).isoformat()}
                if period == 'current' and not inputs['reports_available']:
                    row['available_at'] = '2026-11-05T15:00:00Z'
                events.append(row)
            denominator = inputs[period + '_patient_days']
            for i in range(21):
                activity.append({**activity_template, 'record_id': f'fixture:activity:{period}:{i}', 'activity_date': (start + timedelta(days=i)).isoformat(),
                                 'patient_days': None if denominator is None else denominator / 21,
                                 'reporting_campaign': inputs['reporting_campaign'] if period == 'current' else False})
        tables['quality_events'], tables['unit_activity'] = events, activity
        result = engine(tables).quality(unit, Evidence())
        output = {'unexplained_rate_review': result['review_required'], 'causal_claim_permitted': result['causal_claim_permitted'],
                  'data_issue': result['status'] == 'insufficient_denominator'}
        if not inputs['reports_available']:
            unsupported['data_issue'] = 'Late report delivery cannot be inferred from an empty known reporting window'
        details = {'status': result['status'], 'rate_ratio': result['rate_ratio']}
    else:
        raise ValueError('Unsupported evaluation family')
    return output, unsupported, details


def summarize(rows):
    summaries = []
    for family in sorted({r['family'] for r in rows}):
        for split in ('tune', 'holdout'):
            selected = [r for r in rows if r['family'] == family and r['split'] == split]
            key = {'drift': 'finding', 'provider': 'finding', 'access': 'finding', 'simulation': 'feasible', 'quality': 'unexplained_rate_review'}[family]
            eligible = [r for r in selected if key not in r['unsupported_fields'] and r['observed'] is not None]
            tp = sum(r['expected'][key] and r['observed'][key] for r in eligible)
            fp = sum(not r['expected'][key] and r['observed'][key] for r in eligible)
            fn = sum(r['expected'][key] and not r['observed'][key] for r in eligible)
            tn = len(eligible) - tp - fp - fn
            summaries.append({'family': family, 'split': split, 'primary_decision': key, 'cases': len(selected),
                'fully_matched': sum(r['status'] == 'passed' for r in selected), 'partially_evaluated': sum(r['status'] == 'partial' for r in selected),
                'failed': sum(r['status'] in ('failed', 'error') for r in selected), 'primary_scored': len(eligible),
                'true_positive': tp, 'false_positive': fp, 'false_negative': fn, 'true_negative': tn,
                'precision': tp / (tp + fp) if tp + fp else None, 'recall': tp / (tp + fn) if tp + fn else None})
    return summaries


def evaluate(cases, base):
    results = []
    for case in cases:
        try:
            observed, unsupported, details = run_input(case['family'], deepcopy(case['input']), base)
            mismatches = {key: {'expected': value, 'observed': observed.get(key)} for key, value in case['expected'].items()
                          if key not in unsupported and observed.get(key) != value}
            status = 'failed' if mismatches else 'partial' if unsupported else 'passed'
            error = None
        except (KeyError, ValueError, TypeError, StopIteration) as exc:
            observed, unsupported, details, mismatches, status, error = None, {}, {}, {}, 'error', type(exc).__name__ + ': ' + str(exc)
        results.append({'case_id': case['case_id'], 'family': case['family'], 'split': case['split'], 'expected': case['expected'],
                        'observed': observed, 'unsupported_fields': unsupported, 'mismatches': mismatches,
                        'status': status, 'details': details, 'error': error})
    return {'schema_version': 1, 'scope': 'Thirty synthetic component fixtures with explicit adapters; not a hospital generalization or clinical-outcome study',
            'configuration_frozen': True, 'case_count': len(results), 'families': summarize(results), 'cases': results,
            'status_counts': {status: sum(r['status'] == status for r in results) for status in ('passed', 'partial', 'failed', 'error')}}
