"""Evaluation scoring and label isolation; not another set of detector labels."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from pulse.api import create_app
from pulse.config import Settings
from pulse.evaluation.fixtures import evaluate, summarize
from pulse.intelligence.engine import content_hash
from pulse.repository import SourceRepository
from pulse.storage import EvidenceStore
from scripts.generate_data import generate


class ScoringTests(unittest.TestCase):
    def row(self, expected, observed, status='passed', unsupported=None):
        return {'family': 'access', 'split': 'holdout', 'expected': {'finding': expected},
                'observed': {'finding': observed}, 'status': status, 'unsupported_fields': unsupported or {}}

    def test_confusion_counts_use_actual_decisions(self):
        rows = [self.row(True, True), self.row(False, True, 'failed'), self.row(True, False, 'failed'), self.row(False, False)]
        summary = next(r for r in summarize(rows) if r['split'] == 'holdout')
        self.assertEqual([summary[k] for k in ('true_positive', 'false_positive', 'false_negative', 'true_negative')], [1, 1, 1, 1])
        self.assertEqual(summary['precision'], .5)
        self.assertEqual(summary['recall'], .5)

    def test_undefined_scores_are_null_and_unsupported_decisions_are_excluded(self):
        summary = next(r for r in summarize([self.row(False, False), self.row(True, True, 'partial', {'finding': 'unsupported'})]) if r['split'] == 'holdout')
        self.assertEqual(summary['primary_scored'], 1)
        self.assertIsNone(summary['precision'])
        self.assertIsNone(summary['recall'])

    def test_expected_labels_are_only_used_after_prediction(self):
        case = {'case_id': 'a', 'family': 'access', 'split': 'holdout', 'input': {'opaque': 'input'}, 'expected': {'finding': True}}
        with patch('pulse.evaluation.fixtures.run_input', return_value=({'finding': True}, {}, {})) as predictor:
            first = evaluate([case], {})
            second = evaluate([{**case, 'expected': {'finding': False}}], {})
        self.assertEqual(predictor.call_args_list[0], predictor.call_args_list[1])
        self.assertEqual(first['cases'][0]['observed'], second['cases'][0]['observed'])
        self.assertEqual(second['cases'][0]['status'], 'failed')


class FixtureIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.settings = Settings.load({}, Path(cls.temp.name))
        with contextlib.redirect_stdout(io.StringIO()):
            generate(42, cls.settings.data_dir)
        cls.tables = SourceRepository(cls.settings.database_path).snapshot(cls.settings.as_of)
        cls.cases = json.loads((cls.settings.data_dir / 'evaluation_cases.json').read_text())['cases']
        cls.report = evaluate(cls.cases, cls.tables)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_adapters_run_and_known_discrepancy_remains_visible(self):
        self.assertEqual(self.report['case_count'], 30)
        self.assertEqual(self.report['status_counts'], {'passed': 26, 'partial': 3, 'failed': 1, 'error': 0})
        failed = [r for r in self.report['cases'] if r['status'] == 'failed']
        self.assertEqual([r['case_id'] for r in failed], ['ACCESS-late_arrival'])
        self.assertEqual(failed[0]['observed']['finding'], True)
        self.assertEqual(failed[0]['expected']['finding'], False)

    def test_partial_freshness_checks_are_not_counted_as_fully_matched(self):
        partial = [r for r in self.report['cases'] if r['status'] == 'partial']
        self.assertEqual(len(partial), 3)
        self.assertTrue(all('data_issue' in r['unsupported_fields'] for r in partial))

    def test_read_only_report_route_flags_a_different_snapshot(self):
        root = Path(self.temp.name)
        report_path = root / 'docs/validation/release_report.json'
        report_path.parent.mkdir(parents=True, exist_ok=True)
        from pulse.intelligence import ENGINE_VERSION
        report_path.write_text(json.dumps({'schema_version': 1, 'dataset': {'input_hash': content_hash(self.tables), 'engine_version': ENGINE_VERSION}}))
        with patch('pulse.api.ROOT', root):
            app = create_app(self.settings)
        with TestClient(app) as client:
            current = client.get('/api/evaluation').json()
            self.assertTrue(current['matches_selected_snapshot'])
            earlier = client.get('/api/evaluation?as_of=2026-11-05T10:00:00Z').json()
            self.assertFalse(earlier['matches_selected_snapshot'])
            self.assertEqual(client.get('/api/records/evaluation_cases').status_code, 404)

    def test_valid_evidence_objects_are_not_rewritten(self):
        store = EvidenceStore(Path(self.temp.name) / 'immutable')
        digest = store.put_json({'kind': 'test', 'count': 1})
        path = store.root / digest[:2] / (digest + '.json')
        before = path.stat().st_mtime_ns
        with patch('pulse.storage.os.replace', side_effect=AssertionError('Unexpected rewrite')):
            self.assertEqual(store.put_json({'count': 1, 'kind': 'test'}), digest)
        self.assertEqual(path.stat().st_mtime_ns, before)
