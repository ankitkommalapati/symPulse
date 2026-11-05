"""Independent staffing constraint boundaries and snapshot-bound HTTP behavior."""
import contextlib
import copy
import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from fastapi.testclient import TestClient
from scripts.generate_data import generate
from pulse.api import create_app
from pulse.config import Settings
from pulse.repository import SourceRepository
from pulse.intelligence.engine import IntelligenceEngine, content_hash
from pulse.simulation.engine import Policy, Simulator, interval_hours
from pulse.intelligence.rules import instant

CLOCK = '2026-11-05T14:00:00Z'


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.settings = Settings.load({}, Path(cls.temp.name))
        with contextlib.redirect_stdout(io.StringIO()):
            generate(42, cls.settings.data_dir)
        cls.tables = SourceRepository(cls.settings.database_path).snapshot(CLOCK)
        cls.packet = IntelligenceEngine(cls.tables, CLOCK).analyze()['investigations']['FAC-01:ICU:readiness']

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def sim(self, tables=None, policy=Policy()):
        return Simulator(tables or self.tables, self.packet, 'America/Chicago', policy)

    def test_pair_preserves_source_unit_and_residual_gap(self):
        before = content_hash(self.tables)
        plan = self.sim().evaluate('reassignment')
        self.assertEqual([a['employee_id'] for a in plan['actions']], ['SYN-RN-041', 'SYN-RN-042'])
        self.assertEqual(plan['modeled_uncovered_rn_hours'], 12)
        self.assertEqual(plan['incremental_cost_usd'], 0)
        self.assertEqual(plan['donor_checks'][0]['uncovered_rn_hours'], 0)
        self.assertEqual(before, content_hash(self.tables))

    def test_costs_reconcile_and_unverified_capacity_does_not_disappear(self):
        sim = self.sim()
        agency, hybrid = sim.evaluate('agency'), sim.evaluate('hybrid')
        self.assertEqual(agency['baseline_scheduled_cost_usd'], hybrid['baseline_scheduled_cost_usd'])
        self.assertEqual(agency['cost_scope_unit_ids'], hybrid['cost_scope_unit_ids'])
        self.assertEqual(agency['incremental_cost_usd'], 3960)
        self.assertEqual(hybrid['incremental_cost_usd'], 1320)
        self.assertEqual(agency['incremental_cost_usd'] - hybrid['incremental_cost_usd'], 2640)
        self.assertEqual(hybrid['modeled_uncovered_rn_hours'], 0)
        self.assertEqual(hybrid['gap_under_selected_assumptions'], 12)
        self.assertEqual(agency['gap_without_unverified_capacity'], 36)
        self.assertEqual(hybrid['modeled_total_cost_usd'], hybrid['baseline_scheduled_cost_usd'] + 1320)
        self.assertEqual(hybrid['status'], 'conditional')
        assumed = sim.evaluate('hybrid', assume_agency_available=True)
        self.assertEqual(assumed['gap_under_selected_assumptions'], 0)
        self.assertEqual(assumed['gap_without_unverified_capacity'], 12)
        self.assertEqual(assumed['status'], 'conditional')

    def test_overtime_is_additional_pay_and_needs_acceptance(self):
        plan = self.sim().evaluate('overtime')
        self.assertEqual(plan['incremental_cost_usd'], 2700)
        self.assertEqual(plan['modeled_uncovered_rn_hours'], 0)
        self.assertEqual(plan['gap_under_selected_assumptions'], 36)
        accepted = self.sim().evaluate('overtime', overtime_accepted=True)
        self.assertEqual(accepted['gap_under_selected_assumptions'], 0)
        self.assertEqual(accepted['gap_without_unverified_capacity'], 36)

    def test_missing_competency_rejects_candidate(self):
        c = self.sim().candidate('SYN-RN-043', 'reassignment')
        self.assertFalse(c['eligible'])
        self.assertTrue(any('competency' in reason for reason in c['reasons']))

    def test_expiring_qualification_is_not_whole_shift_eligible(self):
        data = copy.deepcopy(self.tables)
        for q in data['employee_qualifications']:
            if q['employee_number'] == 'SYN-RN-041' and q['qualification_code'] == 'ICU_COMPETENCY':
                q['effective_to'] = '2026-11-06T19:00:00Z'
        self.assertFalse(self.sim(data).candidate('SYN-RN-041', 'reassignment')['eligible'])

    def test_absence_and_overlap_are_rejected(self):
        self.assertFalse(self.sim().candidate('SYN-RN-009', 'overtime')['eligible'])
        data = copy.deepcopy(self.tables)
        row = copy.deepcopy(next(r for r in data['workforce_assignments'] if r['employee_number'] == 'SYN-RN-001'))
        row.update(record_id='test:conflict', shift_start='2026-11-06T14:00:00Z', shift_end='2026-11-06T15:00:00Z')
        data['workforce_assignments'].append(row)
        self.assertTrue(any('overlaps' in r for r in self.sim(data).candidate('SYN-RN-001', 'overtime')['reasons']))

    def test_rest_boundary_is_inclusive_but_shorter_rest_fails(self):
        self.assertTrue(self.sim().candidate('SYN-RN-041', 'reassignment')['eligible'])
        data = copy.deepcopy(self.tables)
        previous = next(r for r in data['workforce_assignments'] if r['employee_number'] == 'SYN-RN-041' and r['shift_start'] == '2026-11-05T13:00:00Z')
        previous['shift_end'] = '2026-11-06T01:00:01Z'
        self.assertTrue(any('rest buffer' in r for r in self.sim(data).candidate('SYN-RN-041', 'reassignment')['reasons']))

    def test_rolling_hours_policy_can_reject_otherwise_eligible_staff(self):
        self.assertTrue(any('168-hour' in r for r in self.sim(policy=replace(Policy(), maximum_rolling_168h_hours=12)).candidate('SYN-RN-041', 'reassignment')['reasons']))
        self.assertTrue(any('24-hour' in r for r in self.sim(policy=replace(Policy(), maximum_rolling_24h_hours=10)).candidate('SYN-RN-041', 'reassignment')['reasons']))

    def test_joint_donor_shortage_rejects_submitted_pair_atomically(self):
        data = copy.deepcopy(self.tables)
        for r in data['staffing_requirements']:
            if r['organization_code'] == '120' and r['shift_start'] == '2026-11-06T13:00:00Z':
                r['required_count'] = 7
        sim = self.sim(data)
        self.assertEqual(sim.evaluate('reassignment', ['SYN-RN-041'])['modeled_uncovered_rn_hours'], 24)
        pair = sim.evaluate('reassignment', ['SYN-RN-041', 'SYN-RN-042'])
        self.assertEqual(pair['status'], 'infeasible')
        self.assertEqual(pair['modeled_uncovered_rn_hours'], 36)
        self.assertEqual(pair['actions'], [])
        self.assertTrue(any('Joint plan' in reason for r in pair['rejected_candidates'] for reason in r['reasons']))

    def test_ineligible_explicit_selection_does_not_partially_apply(self):
        p = self.sim().evaluate('reassignment', ['SYN-RN-041', 'SYN-RN-043'])
        self.assertEqual(p['status'], 'infeasible')
        self.assertEqual(p['actions'], [])
        self.assertEqual(p['modeled_uncovered_rn_hours'], 36)

    def test_agency_onboarding_shortfall_cannot_claim_coverage(self):
        p = self.sim(policy=replace(Policy(), agency_onboarding_hours=48)).evaluate('agency')
        self.assertEqual(p['status'], 'infeasible')
        self.assertEqual(p['modeled_uncovered_rn_hours'], 36)

    def test_rate_edit_changes_cost_without_changing_capacity(self):
        p = self.sim().evaluate('agency', agency_rate=125)
        self.assertEqual(p['incremental_cost_usd'], 4500)
        self.assertEqual(p['modeled_uncovered_rn_hours'], 0)

    def test_missing_pay_rate_blocks_cost_claim(self):
        data = copy.deepcopy(self.tables)
        next(r for r in data['employees'] if r['employee_number'] == 'SYN-RN-009').pop('base_hourly_rate_usd')
        plan = self.sim(data).evaluate('agency')
        self.assertEqual(plan['status'], 'infeasible')
        self.assertIsNone(plan['baseline_scheduled_cost_usd'])
        self.assertIsNone(plan['modeled_total_cost_usd'])
        self.assertEqual(plan['modeled_uncovered_rn_hours'], 36)

    def test_duplicate_people_rejected_by_engine_too(self):
        with self.assertRaises(ValueError):
            self.sim().evaluate('reassignment', ['SYN-RN-041', 'SYN-RN-041'])

    def test_interval_union_does_not_double_count_overlapping_hours(self):
        rows = [{'shift_start': '2026-11-06T13:00:00Z', 'shift_end': '2026-11-06T20:00:00Z'},
                {'shift_start': '2026-11-06T19:00:00Z', 'shift_end': '2026-11-07T01:00:00Z'}]
        self.assertEqual(interval_hours(rows, instant('2026-11-06T00:00:00Z'), instant('2026-11-08T00:00:00Z')), 12)

    def test_api_rejects_stale_snapshot_duplicate_people_and_invalid_slots(self):
        with TestClient(create_app(self.settings)) as client:
            path = '/api/investigations/FAC-01:ICU:readiness'
            digest = client.get(path).json()['snapshot_id']
            body = {'snapshot_id': digest, 'kind': 'reassignment', 'employee_ids': ['SYN-RN-041', 'SYN-RN-041']}
            self.assertEqual(client.post(path + '/simulate', json=body).status_code, 409)
            self.assertEqual(client.post(path + '/simulate', json={**body, 'snapshot_id': '0' * 64}).status_code, 409)
            self.assertEqual(client.post(path + '/simulate', json={**body, 'agency_slots': 4}).status_code, 422)
            self.assertEqual(client.post(path + '/simulate', json={**body, 'agency_hourly_rate_usd': -1}).status_code, 422)

    def test_api_saves_simulation_and_inputs_without_modifying_source(self):
        before = self.settings.database_path.read_bytes()
        with TestClient(create_app(self.settings)) as client:
            path = '/api/investigations/FAC-01:ICU:readiness'
            digest = client.get(path).json()['snapshot_id']
            response = client.post(path + '/simulate', json={'snapshot_id': digest, 'kind': 'hybrid'})
            self.assertEqual(response.status_code, 200, response.text[:200])
            body = response.json()
            self.assertEqual(body['result']['incremental_cost_usd'], 1320)
            with TestClient(create_app(self.settings)) as restarted:
                saved = restarted.get(body['artifact_url']).json()
                inputs = restarted.get('/api/artifacts/' + body['input_snapshot_id']).json()
            self.assertEqual(saved['result'], body['result'])
            self.assertIn('workforce_assignments', inputs['tables'])
        self.assertEqual(before, self.settings.database_path.read_bytes())

    def test_no_gap_snapshot_has_no_staffing_intervention(self):
        earlier = '2026-11-05T10:00:00Z'
        tables = SourceRepository(self.settings.database_path).snapshot(earlier)
        packet = IntelligenceEngine(tables, earlier).analyze()['investigations']['FAC-01:ICU:readiness']
        context = Simulator(tables, packet, 'America/Chicago').context()
        self.assertIsNone(context['target_shift'])
        self.assertTrue(all(p['status'] == 'unavailable' for p in context['plans']))
