"""Transactional lifecycle, optimistic concurrency, residual risk and audit invariants."""
import contextlib
import io
import json
import shutil
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from fastapi.testclient import TestClient
from pulse.api import create_app
from pulse.config import Settings
from pulse.intelligence.service import IntelligenceService
from pulse.repository import SourceRepository
from pulse.simulation.service import SimulationService, SimulationRequest
from pulse.storage import EvidenceStore
from pulse.workflows.service import ACTOR, Change, CreatePlan, TaskEdit, Transition, WorkflowService
from pulse.workflows.store import WorkflowConflict, WorkflowStore, WorkflowUnavailable
from scripts.generate_data import generate


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.settings = Settings.load({}, Path(cls.temp.name))
        with contextlib.redirect_stdout(io.StringIO()):
            generate(42, cls.settings.data_dir)
        cls.evidence = EvidenceStore(cls.settings.evidence_dir)
        cls.intelligence = IntelligenceService(SourceRepository(cls.settings.database_path), cls.evidence, cls.settings.hospital_timezone)
        cls.packet = cls.intelligence.packet('FAC-01:ICU:readiness', cls.settings.as_of)
        service = SimulationService(SourceRepository(cls.settings.database_path), cls.evidence, cls.settings.hospital_timezone)
        cls.simulations = {kind: service.simulate(cls.packet['id'], cls.settings.as_of,
                          SimulationRequest(snapshot_id=cls.packet['snapshot_id'], kind=kind)) for kind in ('hybrid', 'reassignment')}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.settings = replace(self.__class__.settings, workflow_path=Path(self.folder.name) / 'plans.sqlite')
        self.store = WorkflowStore(self.settings.workflow_path)
        self.service = WorkflowService(self.store, self.intelligence, self.evidence)

    def create(self, kind='hybrid', key='workflow-test-request-001'):
        return self.service.create(CreatePlan(simulation_id=self.simulations[kind]['simulation_id'],
                                   snapshot_id=self.packet['snapshot_id'], idempotency_key=key), self.settings.as_of)

    def action(self, plan, name, **values):
        return self.service.change(plan['id'], Transition(expected_version=plan['version'], snapshot_id=plan['snapshot_id'],
                                   transition=name, acknowledge_demo=True, note='Explicit demo outcome note', **values))

    def monitoring(self, plan):
        for step in ('submit', 'approve', 'simulate_implementation', 'monitor'):
            plan = self.action(plan, step)
        return plan

    def complete_all(self, plan):
        for task in plan['tasks']:
            plan = self.service.task(plan['id'], task['id'], Change(expected_version=plan['version'],
                        snapshot_id=plan['snapshot_id'], acknowledge_demo=True, note='Simulated review completed with documented demo evidence.'), complete=True)
        return plan

    def test_idempotent_creation_and_restart_preserve_plan(self):
        plan = self.create(); repeated = self.create()
        self.assertEqual(plan['id'], repeated['id'])
        self.assertEqual(repeated['version'], 1)
        saved = WorkflowStore(self.settings.workflow_path).get(plan['id'])
        self.assertEqual(saved['state'], 'draft')
        self.assertEqual(len(saved['audit']), 1)
        self.assertEqual(saved['simulation_id'], self.simulations['hybrid']['simulation_id'])
        self.assertTrue(all(t['owner_role'] and t['due_at'] for t in saved['tasks']))
        with self.assertRaises(WorkflowConflict):
            self.create('reassignment')

    def test_full_lifecycle_closes_only_with_simulated_outcomes(self):
        source_before = self.settings.database_path.read_bytes()
        plan = self.monitoring(self.create())
        with self.assertRaises(WorkflowConflict):
            self.action(plan, 'close')
        plan = self.complete_all(plan)
        plan = self.action(plan, 'close')
        self.assertEqual(plan['state'], 'closed')
        self.assertTrue(plan['closure']['simulated'])
        self.assertEqual(len(plan['audit']), plan['version'])
        self.assertEqual(self.settings.database_path.read_bytes(), source_before)
        current = self.intelligence.packet(self.packet['id'], self.settings.as_of)
        self.assertEqual(current['metrics']['coverage']['uncovered_rn_hours'], 36)
        for task in plan['tasks']:
            outcome = self.evidence.get_json(task['completion_evidence_id'])
            self.assertTrue(outcome['simulated'])
            self.assertEqual(outcome['plan_id'], plan['id'])

    def test_approval_does_not_complete_tasks_or_resolve_plan(self):
        plan = self.action(self.action(self.create(), 'submit'), 'approve')
        self.assertEqual(plan['state'], 'approved')
        self.assertTrue(all(t['status'] == 'open' for t in plan['tasks']))
        self.assertIn('approval', plan)
        with self.assertRaises(WorkflowConflict):
            self.action(plan, 'close')

    def test_residual_gap_blocks_closure_even_after_all_tasks(self):
        plan = self.complete_all(self.monitoring(self.create('reassignment')))
        self.assertEqual(plan['proposal']['modeled_uncovered_rn_hours'], 12)
        with self.assertRaises(WorkflowConflict):
            self.action(plan, 'close')
        self.assertEqual(self.store.get(plan['id'])['state'], 'monitoring')

    def test_approval_requires_acknowledgement(self):
        plan = self.action(self.create(), 'submit')
        with self.assertRaises(WorkflowConflict):
            self.service.change(plan['id'], Transition(expected_version=plan['version'], snapshot_id=plan['snapshot_id'], transition='approve'))
        self.assertEqual(self.store.get(plan['id'])['version'], plan['version'])

    def test_task_owner_due_edit_only_in_draft(self):
        plan = self.create(); task = plan['tasks'][0]
        edited = self.service.task(plan['id'], task['id'], TaskEdit(expected_version=1, snapshot_id=plan['snapshot_id'],
                                  owner_role='house_supervisor', due_at='2026-11-06T08:00:00-06:00'))
        self.assertEqual(edited['tasks'][0]['due_at'], '2026-11-06T14:00:00.000000+00:00')
        self.assertEqual(edited['tasks'][0]['owner_role'], 'house_supervisor')
        submitted = self.action(edited, 'submit')
        with self.assertRaises(WorkflowConflict):
            self.service.task(plan['id'], task['id'], TaskEdit(expected_version=submitted['version'], snapshot_id=plan['snapshot_id'], owner_role='staffing_manager'))

    def test_missing_outcome_note_cannot_complete_task(self):
        plan = self.monitoring(self.create())
        with self.assertRaises(WorkflowConflict):
            self.service.task(plan['id'], plan['tasks'][0]['id'], Change(expected_version=plan['version'], snapshot_id=plan['snapshot_id'], acknowledge_demo=True), complete=True)

    def test_stale_version_rejects_overwrite(self):
        original = self.create(); plan = self.action(original, 'submit')
        with self.assertRaises(WorkflowConflict):
            self.action(original, 'submit')
        self.assertEqual(self.store.get(plan['id'])['version'], plan['version'])

    def test_concurrent_writers_commit_only_one_revision(self):
        plan = self.create()
        def attempt(_):
            try:
                return self.store.mutate(plan['id'], 1, ACTOR, 'test-edit', lambda body: {})['version']
            except WorkflowConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, range(2)))
        self.assertCountEqual(results, [2, 'conflict'])
        self.assertEqual(len(self.store.get(plan['id'])['audit']), 2)

    def test_dismissal_requires_reason_and_never_resolves_source(self):
        plan = self.create()
        with self.assertRaises(WorkflowConflict):
            self.service.change(plan['id'], Transition(expected_version=1, snapshot_id=plan['snapshot_id'], transition='dismiss'))
        dismissed = self.action(plan, 'dismiss')
        self.assertEqual(dismissed['state'], 'dismissed')
        self.assertTrue(all(t['status'] == 'open' for t in dismissed['tasks']))
        with self.assertRaises(WorkflowConflict):
            self.action(dismissed, 'submit')

    def test_changed_source_rejects_approval(self):
        copy_path = Path(self.folder.name) / 'sources.sqlite'
        shutil.copy2(self.settings.database_path, copy_path)
        intelligence = IntelligenceService(SourceRepository(copy_path), self.evidence, self.settings.hospital_timezone)
        service = WorkflowService(self.store, intelligence, self.evidence)
        plan = self.action(self.create(), 'submit')
        with sqlite3.connect(copy_path) as conn:
            conn.execute('UPDATE unavailability SET status="withdrawn"')
        with self.assertRaises(WorkflowConflict):
            service.change(plan['id'], Transition(expected_version=plan['version'], snapshot_id=plan['snapshot_id'], transition='approve', acknowledge_demo=True))
        self.assertEqual(self.store.get(plan['id'])['state'], 'awaiting_approval')

    def test_invalid_simulation_and_wrong_snapshot_cannot_create_plan(self):
        bad = self.evidence.put_json({**self.simulations['hybrid'], 'result': {**self.simulations['hybrid']['result'], 'status': 'infeasible'}})
        with self.assertRaises(WorkflowConflict):
            self.service.create(CreatePlan(simulation_id=bad, snapshot_id=self.packet['snapshot_id'], idempotency_key='workflow-invalid-request'), self.settings.as_of)
        with self.assertRaises(WorkflowConflict):
            self.service.create(CreatePlan(simulation_id=self.simulations['hybrid']['simulation_id'], snapshot_id='0' * 64, idempotency_key='workflow-mismatch-request'), self.settings.as_of)

    def test_failed_transaction_does_not_append_audit_or_update_state(self):
        plan = self.create()
        def fail(body):
            body['state'] = 'closed'
            raise WorkflowConflict('simulated failure')
        with self.assertRaises(WorkflowConflict):
            self.store.mutate(plan['id'], 1, ACTOR, 'bad', fail)
        saved = self.store.get(plan['id'])
        self.assertEqual(saved['state'], 'draft')
        self.assertEqual(len(saved['audit']), 1)

    def test_tampered_plan_and_event_are_detected(self):
        plan = self.create()
        with sqlite3.connect(self.settings.workflow_path) as conn:
            conn.execute('UPDATE plan_events SET event_hash=? WHERE plan_id=?', ('0' * 64, plan['id']))
        with self.assertRaises(WorkflowUnavailable):
            self.store.get(plan['id'])

    def test_cannot_use_source_database_as_workflow_database(self):
        with self.assertRaises(ValueError):
            create_app(replace(self.settings, workflow_path=self.settings.database_path))

    def test_closure_rejects_outcome_for_another_snapshot(self):
        plan = self.complete_all(self.monitoring(self.create()))
        task = plan['tasks'][0]
        original = self.evidence.get_json(task['completion_evidence_id'])
        wrong = self.evidence.put_json({**original, 'snapshot_id': '0' * 64})
        def alter(body):
            body['tasks'][0]['completion_evidence_id'] = wrong
            return {'fixture': 'mismatched-outcome'}
        plan = self.store.mutate(plan['id'], plan['version'], ACTOR, 'test-fixture', alter)
        with self.assertRaises(WorkflowConflict):
            self.action(plan, 'close')

    def test_outcome_storage_failure_rolls_back_task_and_audit(self):
        from unittest.mock import patch
        plan = self.monitoring(self.create())
        original = self.evidence.put_json
        def write(document):
            if document.get('kind') == 'workflow_task_outcome':
                raise OSError('Unavailable outcome storage')
            return original(document)
        with patch.object(self.evidence, 'put_json', side_effect=write), self.assertRaises(OSError):
            self.service.task(plan['id'], plan['tasks'][0]['id'], Change(expected_version=plan['version'],
                snapshot_id=plan['snapshot_id'], acknowledge_demo=True, note='Explicit simulated outcome.'), complete=True)
        saved = self.store.get(plan['id'])
        self.assertEqual(saved['version'], plan['version'])
        self.assertEqual(saved['tasks'][0]['status'], 'open')
        self.assertEqual(len(saved['audit']), len(plan['audit']))

    def test_workflow_storage_failure_is_not_reported_ready(self):
        directory = Path(self.folder.name) / 'directory'
        directory.mkdir()
        with TestClient(create_app(replace(self.settings, workflow_path=directory))) as client:
            self.assertEqual(client.get('/health/live').status_code, 200)
            self.assertEqual(client.get('/health/ready').status_code, 503)

    def test_http_plan_contract_and_persistent_completion(self):
        with TestClient(create_app(self.settings)) as client:
            payload = {'simulation_id': self.simulations['hybrid']['simulation_id'], 'snapshot_id': self.packet['snapshot_id'], 'idempotency_key': 'http-workflow-request-key'}
            response = client.post('/api/plans', json=payload)
            self.assertEqual(response.status_code, 201, response.text[:200])
            plan = response.json()
            self.assertEqual(client.get('/api/workflow/meta').json()['mode'], 'seeded_demo_persona')
            self.assertEqual(len(client.get('/api/plans', params={'investigation_id': self.packet['id']}).json()['items']), 1)
            path = '/api/plans/' + plan['id']
            bad = {'expected_version': 1, 'snapshot_id': plan['snapshot_id'], 'transition': 'close', 'acknowledge_demo': True}
            self.assertEqual(client.post(path + '/transition', json=bad).status_code, 409)
            self.assertEqual(client.patch(path + '/tasks/' + plan['tasks'][0]['id'], json={'expected_version': 1, 'snapshot_id': plan['snapshot_id'], 'due_at': '2026-11-05T08:00:00'}).status_code, 422)
        with TestClient(create_app(self.settings)) as restarted:
            self.assertEqual(restarted.get(path).json()['state'], 'draft')
