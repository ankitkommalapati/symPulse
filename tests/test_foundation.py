"""Foundation boundaries; detection and staffing calculations are outside this suite."""
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from pulse.api import create_app
from pulse.__main__ import prepare
from pulse.config import Settings, utc_timestamp
from pulse.repository import DatasetUnavailable, SourceRepository
from pulse.storage import EvidenceStore
from scripts.generate_data import generate


class SettingsTests(unittest.TestCase):
    def test_paths_are_relative_to_project_root(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            settings = Settings.load({}, root)
            self.assertEqual(settings.data_dir, root / "data/generated")
            self.assertEqual(settings.database_path, settings.data_dir / "pulse_demo.sqlite")

    def test_environment_overrides_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / ".env").write_text("PULSE_PORT=8123\nPULSE_EVIDENCE_DIR=objects\n")
            settings = Settings.load({"PULSE_PORT": "8124"}, root)
            self.assertEqual(settings.port, 8124)
            self.assertEqual(settings.evidence_dir, root / "objects")

    def test_invalid_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for env in ({"PULSE_PORT": "0"}, {"PULSE_PORT": "65536"}, {"PULSE_PORT": ""},
                        {"PULSE_AS_OF": "2026-11-05T08:00:00"}, {"PULSE_TIMEZONE": "Unknown/Zone"}):
                with self.subTest(env=env), self.assertRaises((ValueError, KeyError)):
                    Settings.load(env, Path(folder))

    def test_clock_normalization_preserves_microseconds(self):
        self.assertEqual(utc_timestamp("2026-11-05T08:00:00.000001-06:00"),
                         "2026-11-05T14:00:00.000001+00:00")


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = EvidenceStore(Path(self.temp.name))

    def test_objects_are_deterministic_and_persistent(self):
        digest = self.store.put_json({"text": "é", "count": 2})
        self.assertEqual(digest, self.store.put_json({"count": 2, "text": "é"}))
        self.assertEqual(EvidenceStore(self.store.root).get_json(digest), {"count": 2, "text": "é"})

    def test_invalid_paths_are_rejected(self):
        for value in ("../file", "a" * 63, "A" * 64, "a" * 64 + "/file"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.store.get_json(value)

    def test_corrupted_object_is_rejected_and_can_be_repaired(self):
        digest = self.store.put_json({"count": 2})
        (self.store.root / digest[:2] / (digest + ".json")).write_text('{}')
        with self.assertRaises(ValueError):
            self.store.get_json(digest)
        self.assertEqual(self.store.put_json({"count": 2}), digest)
        self.assertEqual(self.store.get_json(digest), {"count": 2})

    def test_non_json_numbers_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.put_json({"value": float("nan")})


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "source #1.sqlite"
        with sqlite3.connect(self.path) as conn:
            conn.execute("CREATE TABLE quality_events (record_id TEXT, record_version INTEGER, available_at TEXT, is_deleted INTEGER, synthetic INTEGER, workflow_status TEXT)")
            conn.executemany("INSERT INTO quality_events VALUES (?, ?, ?, ?, ?, ?)", [
                ("quality:quality_events:E1", 1, "2026-11-05T14:00:00Z", 0, 1, "submitted"),
                ("quality:quality_events:E1", 2, "2026-11-05T15:00:00Z", 0, 1, "under_review"),
                ("quality:quality_events:E1", 3, "2026-11-05T16:00:00Z", 1, 1, "deleted"),
                ("quality:quality_events:E2", 1, "2026-11-05T14:00:00.000001Z", 0, 1, "submitted"),
            ])
        self.repo = SourceRepository(self.path)

    def test_future_revision_does_not_hide_current_record(self):
        rows = self.repo.records("quality_events", "2026-11-05T14:00:00Z")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_version"], 1)
        self.assertIs(rows[0]["synthetic"], True)
        self.assertNotIn("_revision_rank", rows[0])

    def test_offset_clock_and_subsecond_availability(self):
        rows = self.repo.records("quality_events", "2026-11-05T08:00:00.000001-06:00")
        self.assertEqual(len(rows), 2)

    def test_later_revision_and_tombstone(self):
        record = self.repo.record("quality:quality_events:E1", "2026-11-05T15:00:00Z")
        self.assertEqual(record["workflow_status"], "under_review")
        self.assertIsNone(self.repo.record("quality:quality_events:E1", "2026-11-05T16:00:00Z"))

    def test_missing_database_does_not_create_empty_file(self):
        path = self.path.parent / "missing.sqlite"
        with self.assertRaises(DatasetUnavailable):
            SourceRepository(path).check()
        self.assertFalse(path.exists())

    def test_source_connection_is_read_only(self):
        with self.assertRaises(DatasetUnavailable):
            with self.repo.connect() as conn:
                conn.execute("DELETE FROM quality_events")
        self.assertEqual(len(self.repo.records("quality_events", "2026-11-05T14:00:00Z")), 1)

    def test_table_and_pagination_validation(self):
        for table in ("evaluation_cases", 'quality_events"; DROP TABLE quality_events;--'):
            with self.assertRaises(ValueError):
                self.repo.records(table, "2026-11-05T14:00:00Z")
        for limit, offset in ((501, 0), (0, 0), (1, -1)):
            with self.assertRaises(ValueError):
                self.repo.records("quality_events", "2026-11-05T14:00:00Z", limit, offset)


class PreparationTests(unittest.TestCase):
    def test_empty_directory_prepares_idempotently(self):
        with tempfile.TemporaryDirectory(prefix="pulse clean ") as folder:
            settings = Settings.load({}, Path(folder))
            with contextlib.redirect_stdout(io.StringIO()):
                prepare(settings)
                before = settings.database_path.stat().st_mtime_ns
                prepare(settings)
            self.assertEqual(before, settings.database_path.stat().st_mtime_ns)
            report = json.loads((settings.data_dir / "validation_report.json").read_text())
            self.assertEqual(report["status"], "passed")

    def test_partial_dataset_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings.load({}, Path(folder))
            settings.data_dir.mkdir(parents=True)
            manifest = settings.data_dir / "manifest.json"
            manifest.write_text('{"keep": true}')
            with self.assertRaises(ValueError):
                prepare(settings)
            self.assertEqual(manifest.read_text(), '{"keep": true}')


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="pulse foundation ")
        root = Path(cls.temp.name)
        cls.settings = Settings.load({}, root)
        with contextlib.redirect_stdout(io.StringIO()):
            generate(42, cls.settings.data_dir)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.client = TestClient(create_app(self.settings))
        self.addCleanup(self.client.close)

    def test_health_and_metadata(self):
        self.assertEqual(self.client.get("/health/live").status_code, 200)
        self.assertEqual(self.client.get("/health/ready").json()["status"], "ready")
        meta = self.client.get("/api/meta").json()
        self.assertTrue(meta["synthetic"])
        self.assertEqual(meta["source_access"], "read_only")
        self.assertNotIn("database_path", meta)

    def test_source_inventory_and_units(self):
        inventory = self.client.get("/api/sources").json()["items"]
        self.assertEqual(len(inventory), 21)
        self.assertEqual(sum(row["archive_record_versions"] for row in inventory), 30316)
        self.assertEqual(len(self.client.get("/api/units").json()["items"]), 6)

    def test_future_schedule_can_be_known_now(self):
        record = "workforce:workforce_assignments:ICU-2026-11-06-DAY-00"
        response = self.client.get("/api/evidence/" + record)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["record"]["shift_start"], "2026-11-06T13:00:00Z")

    def test_evidence_round_trip_survives_new_application(self):
        response = self.client.get("/api/evidence/planning_context:units:ICU").json()
        with TestClient(create_app(self.settings)) as restarted:
            stored = restarted.get(response["artifact_url"]).json()
        self.assertEqual(response["record"], stored["record"])
        self.assertEqual(response["evidence_id"], stored["evidence_id"])

    def test_future_and_unknown_evidence_are_not_returned(self):
        record = "workforce:unavailability:ABS-HERO-0"
        response = self.client.get("/api/evidence/" + record, params={"as_of": "2026-11-04T14:00:00Z"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/api/evidence/missing").status_code, 404)

    def test_records_paginate_and_arrays_are_decoded(self):
        first = self.client.get("/api/records/employees?limit=2&offset=0").json()["items"]
        second = self.client.get("/api/records/employees?limit=2&offset=2").json()["items"]
        self.assertEqual(len(first), 2)
        self.assertTrue({r["record_id"] for r in first}.isdisjoint({r["record_id"] for r in second}))
        row = self.client.get("/api/records/employee_qualifications?limit=1").json()["items"][0]
        self.assertIsInstance(row["eligible_org_codes"], list)

    def test_clock_and_limit_errors(self):
        for query in ("as_of=invalid", "as_of=2026-11-05T14:00:00", "limit=501", "offset=-1"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/api/records/employees?" + query).status_code, 422)

    def test_evaluation_fixtures_are_not_exposed(self):
        self.assertEqual(self.client.get("/api/records/evaluation_cases").status_code, 404)

    def test_missing_dependencies_have_separate_liveness_and_readiness(self):
        missing = replace(self.settings, database_path=self.settings.data_dir / "not-present.sqlite")
        with TestClient(create_app(missing)) as client:
            self.assertEqual(client.get("/health/live").status_code, 200)
            self.assertEqual(client.get("/health/ready").status_code, 503)
            self.assertEqual(client.get("/api/units").status_code, 503)

    def test_storage_failure_is_not_reported_ready(self):
        with patch.object(EvidenceStore, "check", side_effect=OSError("not writable")):
            self.assertEqual(self.client.get("/health/ready").status_code, 503)

    def test_openapi_contains_working_routes_only(self):
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/evidence/{record_id}", schema["paths"])
        self.assertNotIn("/api/plans", schema["paths"])


if __name__ == "__main__":
    unittest.main()
