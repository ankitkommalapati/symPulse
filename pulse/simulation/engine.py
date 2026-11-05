"""Evaluate hypothetical staffing changes without mutating source records."""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import timedelta
from math import ceil
from decimal import Decimal, ROUND_HALF_UP

from pulse.intelligence.engine import Evidence, IntelligenceEngine, content_hash
from pulse.intelligence.rules import duration, instant, overlaps, stamp


@dataclass(frozen=True)
class Policy:
    version: str = 'demo-staffing-policy-1'
    minimum_rest_hours: float = 12
    maximum_rolling_24h_hours: float = 24
    maximum_rolling_168h_hours: float = 60
    overtime_multiplier: float = 1.5
    agency_hourly_rate_usd: float = 110
    agency_onboarding_hours: float = 12
    agency_slots: int = 3


def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def interval_hours(rows, left, right):
    intervals = sorted((max(left, instant(r['shift_start'])), min(right, instant(r['shift_end'])))
                       for r in rows if overlaps(r['shift_start'], r['shift_end'], left, right))
    merged = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return sum(duration(a, b) for a, b in merged)


class Simulator:
    def __init__(self, tables, packet, timezone, policy=Policy()):
        self.tables, self.packet, self.policy = tables, packet, policy
        self.engine = IntelligenceEngine(tables, packet['as_of'], timezone)
        self.timezone = timezone
        self.unit = next(r for r in tables['units'] if r['unit_id'] == packet['summary']['unit_id']
                         and r['facility_id'] == packet['summary']['facility_id'])
        gaps = packet['metrics']['coverage']['gap_segments']
        self.target = None
        if gaps:
            candidate = next(r for r in tables['staffing_requirements'] if r['record_id'] == gaps[0]['requirement_record_id'])
            if instant(candidate['shift_start']) >= self.engine.now:
                self.target = candidate
        self.baseline = packet['metrics']['coverage']
        self.candidate_evidence = {}
        self.candidate_cache = {}

    def candidate(self, employee_id, kind):
        p, target = self.policy, self.target
        employee = self.engine.employees.get(employee_id)
        reasons, evidence = [], []
        result = {'employee_id': employee_id, 'kind': kind, 'eligible': False, 'reasons': reasons,
                  'source_assignment_id': None, 'source_unit_id': None, 'evidence_ids': evidence}
        if not target:
            reasons.append('No complete future shift with a recorded deficit is available')
            return result
        start, end = instant(target['shift_start']), instant(target['shift_end'])
        if not employee:
            reasons.append('Employee record is not known at this snapshot')
            return result
        evidence.append(employee['record_id'])
        if employee['employment_status'] != 'active' or employee['job_class'] != 'RN':
            reasons.append('Active RN employment is required')
        if self.engine._facility('workforce', employee['facility_code'], start, end) != self.unit['facility_id']:
            reasons.append('Facility permission is unverified')
        needed = {'RN_LICENSE'} | ({'ICU_COMPETENCY'} if self.unit['unit_id'] == 'ICU' else set())
        qualifications = self.engine.qualifications[employee_id]
        evidence.extend(r['record_id'] for r in qualifications)
        valid = {r['qualification_code'] for r in qualifications if r['qualification_status'] == 'verified'
                 and instant(r['effective_from']) <= start and instant(r['effective_to']) >= end
                 and r['facility_code'] == target['facility_code'] and target['organization_code'] in r['eligible_org_codes']}
        if not needed <= valid:
            reasons.append('Required license or destination competency does not cover the entire shift')
        absences = self.engine.absences[employee_id]
        evidence.extend(r['record_id'] for r in absences)
        if any(overlaps(r['start'], r['end'], start, end) for r in absences):
            reasons.append('Approved unavailability overlaps the shift')
        work = self.engine.work[employee_id]
        evidence.extend(r['record_id'] for r in work if overlaps(r['shift_start'], r['shift_end'], start - timedelta(days=7), end + timedelta(days=7)))
        occupied = [r for r in work if overlaps(r['shift_start'], r['shift_end'], start, end)]
        replaced = None
        if kind == 'reassignment':
            if len(occupied) != 1 or instant(occupied[0]['shift_start']) != start or instant(occupied[0]['shift_end']) != end:
                reasons.append('Reassignment requires exactly one matching full source shift')
            else:
                replaced = occupied[0]
                source_unit = self.engine._unit('workforce', replaced['organization_code'], replaced['facility_code'], start, end)
                result.update(source_assignment_id=replaced['record_id'], source_unit_id=source_unit)
                if not source_unit or source_unit == self.unit['unit_id']:
                    reasons.append('A different, uniquely mapped source department is required')
                if self.engine._facility('workforce', replaced['facility_code'], start, end) != self.unit['facility_id']:
                    reasons.append('Source assignment facility does not match the destination')
        elif occupied:
            reasons.append('An existing assignment overlaps the proposed additional shift')
        other = [r for r in work if r is not replaced]
        for r in other:
            a, b = instant(r['shift_start']), instant(r['shift_end'])
            if overlaps(a, b, start, end):
                continue
            rest = duration(b, start) if b <= start else duration(end, a)
            if rest < p.minimum_rest_hours:
                reasons.append('Minimum rest buffer is not met')
                break
        proposed = {'shift_start': stamp(start), 'shift_end': stamp(end)}
        roster = other + [proposed]
        # A rolling-window maximum occurs at a work boundary or that boundary minus the window.
        for width, maximum, label in [(24, p.maximum_rolling_24h_hours, '24-hour'), (168, p.maximum_rolling_168h_hours, '168-hour')]:
            span = timedelta(hours=width)
            boundaries = {instant(r[k]) for r in roster for k in ('shift_start', 'shift_end')
                          if start - span <= instant(r[k]) <= end + span}
            anchors = boundaries | {b - span for b in boundaries}
            if any(a < end and a + span > start and interval_hours(roster, a, a + span) > maximum + 1e-8 for a in anchors):
                reasons.append('Maximum rolling ' + label + ' work hours would be exceeded')
        rate = employee.get('base_hourly_rate_usd')
        if not isinstance(rate, (float, int)) or rate < 0:
            reasons.append('Base pay rate is unavailable')
        result.update(eligible=not reasons, reasons=list(dict.fromkeys(reasons)), base_hourly_rate_usd=rate)
        self.candidate_evidence[employee_id] = sorted(set(evidence))
        return result

    def candidates(self, kind):
        if kind not in self.candidate_cache:
            self.candidate_cache[kind] = [self.candidate(key, kind) for key in sorted(self.engine.employees)]
        return self.candidate_cache[kind]

    def _move(self, tables, candidate, index, kind):
        target = self.target
        if kind == 'reassignment':
            tables['workforce_assignments'] = [r for r in tables['workforce_assignments'] if r['record_id'] != candidate['source_assignment_id']]
        tables['workforce_assignments'].append({**target, 'record_id': 'simulation:workforce_assignments:' + str(index),
            'employee_number': candidate['employee_id'], 'home_org_code': target['organization_code'],
            'assignment_status': 'scheduled', 'requirement_record_id': target['record_id']})

    def _metrics(self, tables, unit):
        return IntelligenceEngine(tables, self.packet['as_of'], self.timezone).coverage(unit, Evidence())

    def evaluate(self, kind, employee_ids=None, agency_slots=None, agency_rate=None, overtime_accepted=False, assume_agency_available=False):
        if employee_ids is not None and len(employee_ids) != len(set(employee_ids)):
            raise ValueError('An employee cannot occupy more than one proposed slot')
        if not self.target:
            return {'kind': kind, 'status': 'unavailable', 'reasons': ['No complete future gap shift is available'], 'actions': []}
        source_kind = 'overtime' if kind == 'overtime' else 'reassignment'
        candidates = self.candidates(source_kind)
        index = {r['employee_id']: r for r in candidates}
        selected, rejected, donor_checks = [], [], []
        tables = deepcopy(self.tables)
        if employee_ids is None:
            pool = [r['employee_id'] for r in candidates if r['eligible']] if kind in ('reassignment', 'overtime', 'hybrid') else []
        else:
            pool = employee_ids
        target_start, target_end = instant(self.target['shift_start']), instant(self.target['shift_end'])
        demand = self._shift_gap(self.baseline)
        duration_hours = duration(target_start, target_end)
        for employee_id in pool:
            if employee_ids is None and len(selected) * duration_hours >= demand - 1e-8:
                break
            candidate = index.get(employee_id) or self.candidate(employee_id, source_kind)
            if not candidate['eligible']:
                rejected.append({'employee_id': employee_id, 'reasons': candidate['reasons']})
                continue
            trial = deepcopy(tables)
            self._move(trial, candidate, len(selected), source_kind)
            donor = None
            if source_kind == 'reassignment':
                donor = next((u for u in tables['units'] if u['unit_id'] == candidate['source_unit_id'] and u['facility_id'] == self.unit['facility_id']), None)
                metric = self._metrics(trial, donor) if donor else None
                if metric is None or metric['status'] == 'insufficient_data' or metric['uncovered_rn_hours'] > 0:
                    rejected.append({'employee_id': employee_id, 'reasons': ['Joint plan does not preserve verified source-department minimum coverage']})
                    continue
            tables = trial
            selected.append(candidate)
        explicit_invalid = employee_ids is not None and bool(rejected)
        if explicit_invalid:
            selected = []
            tables = deepcopy(self.tables)
        internal = self._metrics(tables, self.unit)
        slots = agency_slots if agency_slots is not None else (min(self.policy.agency_slots, int(ceil(self._shift_gap(internal) / duration_hours))) if kind in ('agency', 'hybrid') else 0)
        reasons = []
        if slots and duration(self.engine.now, target_start) < self.policy.agency_onboarding_hours:
            reasons.append('Agency onboarding lead time is insufficient')
        if self.baseline['status'] == 'insufficient_data':
            reasons.append('Staffing evidence is incomplete; feasibility cannot be established')
        if explicit_invalid:
            reasons.append('One or more selected employees failed a hard constraint; the submitted plan is rejected')
        for unit_id in sorted({r['source_unit_id'] for r in selected if r['source_unit_id']}):
            unit = next(u for u in tables['units'] if u['unit_id'] == unit_id and u['facility_id'] == self.unit['facility_id'])
            after = self._metrics(tables, unit)
            donor_checks.append({'unit_id': unit_id, 'uncovered_rn_hours': after['uncovered_rn_hours'], 'status': after['status']})
        # Keep the labor-cost boundary identical across every alternative.
        donor_ids = {r['source_unit_id'] for r in self.candidates('reassignment') if r['eligible']}
        affected = [self.unit] + [u for u in self.tables['units'] if u['unit_id'] in donor_ids
                                 and u['facility_id'] == self.unit['facility_id']]
        baseline_cost = self._scheduled_cost(affected)
        if baseline_cost is None:
            reasons.append('Scheduled labor cost is unavailable because a required pay rate is missing')
        rate = self.policy.agency_hourly_rate_usd if agency_rate is None else agency_rate
        overtime_cost = sum(r['base_hourly_rate_usd'] * self.policy.overtime_multiplier * duration_hours for r in selected) if source_kind == 'overtime' else 0
        agency_cost = slots * duration_hours * rate
        internal_improvement = max(0, self.baseline['uncovered_rn_hours'] - internal['uncovered_rn_hours'])
        projected_gap = internal['uncovered_rn_hours'] - min(self._shift_gap(internal), slots * duration_hours)
        if reasons:
            projected_gap = self.baseline['uncovered_rn_hours']
        supported_gap = internal['uncovered_rn_hours'] if source_kind == 'reassignment' or overtime_accepted else self.baseline['uncovered_rn_hours']
        # Scenario confirmations are hypothetical, never treated as source verification.
        conditional_gap = projected_gap if assume_agency_available else internal['uncovered_rn_hours']
        if reasons:
            conditional_gap = self.baseline['uncovered_rn_hours']
        if source_kind == 'overtime' and not overtime_accepted:
            conditional_gap = supported_gap
        actions = [{'employee_id': r['employee_id'], 'kind': source_kind, 'source_unit_id': r['source_unit_id'],
                    'source_assignment_id': r['source_assignment_id'], 'start': stamp(target_start), 'end': stamp(target_end),
                    'evidence_ids': r['evidence_ids']} for r in selected]
        dependencies = (['Voluntary overtime acceptance is unverified; acceptance toggle is a scenario assumption'] if source_kind == 'overtime' and selected else [])
        if slots:
            dependencies += ['Agency capacity, license, competency and onboarding are hypothetical inputs, not verified staff records']
        return {'kind': kind, 'status': 'infeasible' if reasons else 'conditional' if dependencies else 'feasible' if selected else 'unavailable',
                'reasons': reasons, 'dependencies': dependencies, 'actions': actions, 'rejected_candidates': rejected,
                'donor_checks': donor_checks, 'agency_slots': slots, 'agency_hourly_rate_usd': rate,
                'baseline_uncovered_rn_hours': self.baseline['uncovered_rn_hours'],
                'modeled_uncovered_rn_hours': round(projected_gap, 6),
                'gap_under_selected_assumptions': round(conditional_gap, 6),
                'gap_without_unverified_capacity': round(internal['uncovered_rn_hours'] if source_kind == 'reassignment' and not reasons else self.baseline['uncovered_rn_hours'], 6),
                'modeled_added_rn_hours': round(self.baseline['uncovered_rn_hours'] - projected_gap, 6),
                'baseline_scheduled_cost_usd': baseline_cost, 'incremental_cost_usd': money(overtime_cost + agency_cost),
                'modeled_total_cost_usd': money(baseline_cost + overtime_cost + agency_cost) if baseline_cost is not None else None,
                'cost_scope_unit_ids': [u['unit_id'] for u in affected],
                'cost_basis': 'Scheduled base pay for target and affected donor departments across 72 hours, including unavailable assignments; incremental coverage cost added separately. Not payroll or realized savings.',
                'assumptions': {'overtime_accepted': overtime_accepted, 'agency_available': assume_agency_available},
                'unresolved': ['Residual nursing coverage gap' ] * (projected_gap > 0) + ['Physician authorization, vendor access and quality review remain separate from staffing simulation'],
                'source_records_changed': False}

    def _shift_gap(self, metric):
        start, end = instant(self.target['shift_start']), instant(self.target['shift_end'])
        return sum(duration(max(start, instant(g['start'])), min(end, instant(g['end']))) * g['gap_rns']
                   for g in metric['gap_segments'] if overlaps(g['start'], g['end'], start, end))

    def _scheduled_cost(self, units):
        costs = []
        for row in self.tables['workforce_assignments']:
            if row['assignment_status'] not in ('scheduled', 'confirmed') or not overlaps(
                    row['shift_start'], row['shift_end'], self.engine.now, self.engine.end):
                continue
            if not any(self.engine._matches_unit('workforce', row['organization_code'], row['facility_code'], unit,
                       row['shift_start'], row['shift_end']) for unit in units):
                continue
            employee = self.engine.employees.get(row['employee_number'])
            rate = employee.get('base_hourly_rate_usd') if employee else None
            if not isinstance(rate, (float, int)) or rate < 0:
                return None
            costs.append(duration(max(self.engine.now, instant(row['shift_start'])), min(self.engine.end, instant(row['shift_end']))) * rate)
        return money(sum(costs))

    def context_policy(self):
        return asdict(self.policy)

    def context(self):
        plans = [self.evaluate(kind) for kind in ('reassignment', 'overtime', 'agency', 'hybrid')]
        agency = next(p for p in plans if p['kind'] == 'agency')
        hybrid = next(p for p in plans if p['kind'] == 'hybrid')
        return {'version': 'pulse-simulation-1', 'policy': asdict(self.policy), 'policy_hash': content_hash(asdict(self.policy)),
                'target_shift': self.target, 'baseline': self.baseline, 'plans': plans,
                'candidates': {'reassignment': self.candidates('reassignment'), 'overtime': self.candidates('overtime')} if self.target else {},
                'modeled_agency_cost_difference_usd': money(agency['incremental_cost_usd'] - hybrid['incremental_cost_usd'])
                    if all(p['status'] in ('feasible', 'conditional') for p in (agency, hybrid)) else None,
                'synthetic': True, 'source_records_changed': False}
