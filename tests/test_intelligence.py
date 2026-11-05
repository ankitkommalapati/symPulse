"""Analytical boundaries and source-to-investigation integration tests."""
import contextlib
import copy
import io
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from pulse.api import create_app
from pulse.config import Settings
from pulse.intelligence.engine import Evidence, IntelligenceEngine, content_hash
from pulse.intelligence.identity import IdentityResolver
from pulse.intelligence.rules import duration, instant, overtime_drift, quality_review, readiness_priority, uncovered_intervals
from pulse.repository import SourceRepository
from scripts.generate_data import generate

CLOCK = "2026-11-05T14:00:00Z"


class RuleTests(unittest.TestCase):
    def points(self, change=None):
        result = []
        for i in range(90):
            day = date(2026, 8, 7) + timedelta(days=i)
            value = 0.06 + day.weekday() * 0.002
            if change and i >= 56:
                value += change(i - 55)
            result.append({"date": day.isoformat(), "share": value})
        return result

    def test_gradual_change_crosses_ewma_boundary(self):
        result = overtime_drift(self.points(lambda t: t * 0.003))
        self.assertTrue(result["detected"])
        self.assertIsNotNone(result["first_breach_work_date"])
        self.assertEqual(result["baseline"]["end"], "2026-10-01")

    def test_stable_weekday_pattern_and_zero_variance_do_not_alert(self):
        self.assertFalse(overtime_drift(self.points())["detected"])
        points = self.points()
        for p in points:
            p["share"] = 0.06
        self.assertFalse(overtime_drift(points)["detected"])

    def test_baseline_is_not_refit_on_deteriorating_tail(self):
        stable = overtime_drift(self.points())
        changed = overtime_drift(self.points(lambda t: 0.20))
        self.assertEqual(stable["baseline"], changed["baseline"])

    def test_incomplete_history_does_not_invent_normal_values(self):
        points = self.points()
        points[20]["share"] = None
        self.assertEqual(overtime_drift(points)["status"], "insufficient_history")
        self.assertEqual(overtime_drift(self.points()[:30])["status"], "insufficient_history")
        self.assertEqual(overtime_drift(self.points()[:30] + self.points()[31:])["status"], "incomplete_history")

    def test_single_spike_is_not_sustained_drift(self):
        result = overtime_drift(self.points(lambda t: 0.2 if t == 34 else 0))
        self.assertFalse(result["detected"])
        self.assertTrue(result["monitoring"][-1]["point_anomaly"])

    def test_grants_can_cover_an_interval_together(self):
        self.assertEqual(uncovered_intervals("2026-11-06T13:00:00Z", "2026-11-07T01:00:00Z", [
            ("2026-11-06T12:00:00Z", "2026-11-06T19:00:00Z"),
            ("2026-11-06T19:00:00Z", "2026-11-07T01:00:00Z")]), [])

    def test_partial_and_exact_end_expiry(self):
        gaps = uncovered_intervals("2026-11-06T13:00:00Z", "2026-11-07T01:00:00Z", [
            ("2026-11-01T00:00:00Z", "2026-11-06T19:00:00Z")])
        self.assertEqual(sum(duration(a, b) for a, b in gaps), 6)
        self.assertEqual(uncovered_intervals("2026-11-06T13:00:00Z", "2026-11-07T01:00:00Z", [
            ("2026-11-01T00:00:00Z", "2026-11-07T01:00:00Z")]), [])

    def test_elapsed_hours_respect_dst(self):
        self.assertEqual(duration("2026-10-31T19:00:00-05:00", "2026-11-01T07:00:00-06:00"), 13)

    def test_quality_uses_rates_not_just_counts(self):
        self.assertFalse(quality_review(20, 40, 420, 840)["review_required"])
        self.assertTrue(quality_review(20, 40, 420, 420)["review_required"])
        self.assertFalse(quality_review(20, 40, 420, 420)["causal_claim_permitted"])

    def test_reporting_campaign_missing_denominator_and_sparse_counts(self):
        self.assertEqual(quality_review(20, 40, 420, 420, True)["status"], "reporting_context_changed")
        self.assertEqual(quality_review(20, 40, 420, None)["status"], "insufficient_denominator")
        self.assertEqual(quality_review(1, 4, 420, 420)["status"], "insufficient_report_volume")

    def test_priority_distinguishes_combined_risk_from_data_uncertainty(self):
        self.assertEqual(readiness_priority(rn_gap=True, provider_exposure=True), "high")
        self.assertEqual(readiness_priority(rn_gap=True), "medium")
        self.assertEqual(readiness_priority(quality=True), "informational")
        self.assertEqual(readiness_priority(unverified_gap=True), "review_required")
        self.assertEqual(readiness_priority(), "none")


class IdentityTests(unittest.TestCase):
    def mapping(self, canonical="ICU", facility="H01"):
        return {"record_id": "map-" + canonical + facility, "entity_type": "unit", "source_namespace": "workforce",
                "source_entity_id": "110", "source_facility_id": facility, "canonical_id": canonical,
                "mapping_status": "verified", "valid_from": "2026-01-01T00:00:00Z", "valid_to": "2027-01-01T00:00:00Z"}

    def test_duplicate_code_is_scoped_by_facility(self):
        resolver = IdentityResolver([self.mapping(), self.mapping("ED", "H02")])
        self.assertEqual(resolver.unit("workforce", "110", "H01", CLOCK, CLOCK), "ICU")

    def test_ambiguous_and_out_of_date_mapping_do_not_join(self):
        resolver = IdentityResolver([self.mapping(), self.mapping("ED")])
        self.assertIsNone(resolver.unit("workforce", "110", "H01", CLOCK, CLOCK))
        self.assertIsNone(IdentityResolver([self.mapping()]).unit("workforce", "110", "H01",
                                                               "2028-01-01T00:00:00Z", "2028-01-02T00:00:00Z"))

    def test_mapping_is_not_valid_at_its_exclusive_end(self):
        self.assertIsNone(IdentityResolver([self.mapping()]).unit(
            "workforce", "110", "H01", "2027-01-01T00:00:00Z", "2027-01-01T00:00:00Z"))


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="pulse-intelligence-")
        cls.settings = Settings.load({}, Path(cls.temp.name))
        with contextlib.redirect_stdout(io.StringIO()):
            generate(42, cls.settings.data_dir)
        cls.repo = SourceRepository(cls.settings.database_path)
        cls.tables = cls.repo.snapshot(CLOCK)
        cls.analysis = IntelligenceEngine(cls.tables, CLOCK).analyze()
        cls.packet = cls.analysis["investigations"]["FAC-01:ICU:readiness"]
        cls.unit = next(r for r in cls.tables["units"] if r["unit_id"] == "ICU")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_hero_facts_come_from_source_records(self):
        packet = self.packet
        self.assertEqual(packet["summary"]["priority"], "high")
        self.assertEqual(packet["metrics"]["coverage"]["uncovered_rn_hours"], 36)
        self.assertEqual(len(packet["metrics"]["coverage"]["gap_segments"]), 1)
        self.assertTrue(packet["metrics"]["overtime"]["detected"])
        self.assertEqual(len(packet["metrics"]["access"]["findings"]), 1)
        self.assertEqual(packet["metrics"]["quality"]["baseline_reports"], 10)
        self.assertEqual(packet["metrics"]["quality"]["current_reports"], 17)

    def test_full_horizon_keeps_physician_and_rn_hours_separate(self):
        provider = self.packet["metrics"]["provider"]
        first = next(r for r in provider["findings"] if r["assignment_record_id"].endswith("2026-11-06-DAY"))
        self.assertEqual(first["uncovered_physician_hours"], 6)
        self.assertEqual(provider["uncovered_physician_hours"], 19)
        renewal = next(r for r in provider["renewal_followups"] if r["provider_id"] == "SYN-PROV-002")
        self.assertTrue(renewal["all_evaluated_assignments_covered"])
        self.assertFalse(any(r["provider_id"] == "SYN-PROV-002" for r in provider["findings"]))

    def test_comparison_units_have_no_staffing_drift_or_coverage_gap(self):
        for unit in self.analysis["units"]:
            if unit["unit_id"] != "ICU":
                self.assertEqual(unit["uncovered_rn_hours"], 0)
                self.assertFalse(unit["overtime_drift"])

    def test_evidence_references_resolve_and_hashes_match(self):
        records = self.packet["source_records"]
        for key, group in self.packet["evidence_groups"].items():
            self.assertEqual(group["input_hash"], content_hash([records[r] for r in group["record_ids"]]))
        for key, row in records.items():
            self.assertEqual(self.packet["source_record_hashes"][key], content_hash(row))
            self.assertLessEqual(instant(row["available_at"]), instant(CLOCK))
        for observation in self.packet["observations"]:
            self.assertTrue(all(key in self.packet["evidence_groups"] for key in observation["evidence_group_ids"]))

    def test_no_future_absence_leaks_into_earlier_replay(self):
        clock = "2026-11-05T10:00:00Z"
        data = self.repo.snapshot(clock)
        metric = IntelligenceEngine(data, clock).coverage(self.unit, Evidence())
        self.assertEqual(metric["uncovered_rn_hours"], 0)

    def test_successive_approved_grant_covers_expiry(self):
        data = copy.deepcopy(self.tables)
        grant = copy.deepcopy(next(r for r in data["privilege_grants"] if r["provider_key"] == "P001"))
        grant.update(record_id="provider:privilege_grants:renewed", valid_from=grant["valid_to"], valid_to="2027-01-01T00:00:00Z")
        data["privilege_grants"].append(grant)
        self.assertFalse(IntelligenceEngine(data, CLOCK).provider_readiness(self.unit, Evidence())["findings"])

    def test_wrong_service_or_facility_grant_does_not_cover_assignment(self):
        data = copy.deepcopy(self.tables)
        for r in data["privilege_grants"]:
            if r["provider_key"] == "P002":
                r["service_code"] = "SERVICE-OTHER"
        metric = IntelligenceEngine(data, CLOCK).provider_readiness(self.unit, Evidence())
        self.assertTrue(any(r["provider_id"] == "SYN-PROV-002" for r in metric["findings"]))

    def test_unknown_grant_facility_is_unverified_not_confirmed_exposure(self):
        data = copy.deepcopy(self.tables)
        for r in data["privilege_grants"]:
            if r["provider_key"] == "P002":
                r["facility_code"] = "UNKNOWN"
        metric = IntelligenceEngine(data, CLOCK).provider_readiness(self.unit, Evidence())
        self.assertFalse(any(r["provider_id"] == "SYN-PROV-002" for r in metric["findings"]))
        self.assertTrue(metric["data_issues"])

    def test_same_unit_code_in_another_facility_does_not_join(self):
        data = copy.deepcopy(self.tables)
        facility_map = copy.deepcopy(next(r for r in data["entity_crosswalk"] if r["entity_type"] == "facility" and r["source_namespace"] == "access"))
        facility_map.update(record_id="mapping:other-facility", source_entity_id="OTHER", canonical_id="FAC-02")
        unit_map = copy.deepcopy(next(r for r in data["entity_crosswalk"] if r["entity_type"] == "unit" and r["source_namespace"] == "access" and r["canonical_id"] == "ICU"))
        unit_map.update(record_id="mapping:other-icu", source_facility_id="OTHER")
        data["entity_crosswalk"].extend([facility_map, unit_map])
        for visit in data["vendor_visits"]:
            if visit["source_record_id"] == "VISIT-HERO":
                visit["facility_code"] = "OTHER"
        self.assertFalse(IntelligenceEngine(data, CLOCK).access_readiness(self.unit, Evidence())["findings"])

    def test_rejected_quality_reports_are_not_counted(self):
        data = copy.deepcopy(self.tables)
        matching = [r for r in data["quality_events"] if r["location_code"] == "ICU-A"
                    and "2026-10-13" <= r["occurred_at"] < "2026-11-03"]
        matching[0]["workflow_status"] = "rejected"
        metric = IntelligenceEngine(data, CLOCK).quality(self.unit, Evidence())
        self.assertEqual(metric["current_reports"], self.packet["metrics"]["quality"]["current_reports"] - 1)

    def test_partial_absence_integrates_exact_hours(self):
        data = copy.deepcopy(self.tables)
        data["unavailability"] = [copy.deepcopy(data["unavailability"][0])]
        data["unavailability"][0]["end"] = "2026-11-06T19:00:00Z"
        metric = IntelligenceEngine(data, CLOCK).coverage(self.unit, Evidence())
        self.assertEqual(metric["uncovered_rn_hours"], 6)

    def test_qualification_expiry_mid_shift_changes_coverage(self):
        data = copy.deepcopy(self.tables)
        data["unavailability"] = []
        for r in data["employee_qualifications"]:
            if r["employee_number"] == "SYN-RN-009" and r["qualification_code"] == "ICU_COMPETENCY":
                r["effective_to"] = "2026-11-06T19:00:00Z"
        metric = IntelligenceEngine(data, CLOCK).coverage(self.unit, Evidence())
        self.assertGreater(metric["uncovered_rn_hours"], 0)
        self.assertEqual(metric["gap_segments"][0]["start"], "2026-11-06T19:00:00.000000+00:00")

    def test_missing_qualifications_are_unverified_not_safe(self):
        data = copy.deepcopy(self.tables)
        data["employee_qualifications"] = []
        metric = IntelligenceEngine(data, CLOCK).coverage(self.unit, Evidence())
        self.assertEqual(metric["status"], "insufficient_data")
        self.assertGreater(metric["unverified_gap_rn_hours"], 0)
        self.assertEqual(metric["uncovered_rn_hours"] - metric["unverified_gap_rn_hours"], 36)

    def test_missing_crosswalk_is_reported(self):
        data = copy.deepcopy(self.tables)
        data["entity_crosswalk"] = [r for r in data["entity_crosswalk"] if not (
            r["source_namespace"] == "quality" and r["canonical_id"] == "ICU")]
        analysis = IntelligenceEngine(data, CLOCK).analyze()
        self.assertTrue(analysis["data_quality"]["relationship_issues"])
        self.assertTrue(analysis["data_quality"]["completeness_limited"])

    def test_missing_source_table_rows_do_not_produce_an_all_clear(self):
        data = copy.deepcopy(self.tables)
        data["physician_assignments"] = []
        analysis = IntelligenceEngine(data, CLOCK).analyze()
        self.assertIn("physician_assignments", analysis["data_quality"]["missing_input_tables"])
        self.assertFalse(any(r["status"] == "no_current_finding" for r in analysis["units"]))

    def test_quality_only_review_is_informational(self):
        for unit in self.analysis["units"]:
            if unit["reason_codes"] == ["QUALITY_REPORT_RATE_REVIEW"]:
                self.assertEqual(unit["priority"], "informational")

    def test_other_unit_vendor_issue_does_not_join_icu(self):
        data = copy.deepcopy(self.tables)
        for visit in data["vendor_visits"]:
            if visit["source_record_id"] == "VISIT-HERO":
                visit["destination_code"] = "A-02"
        self.assertFalse(IntelligenceEngine(data, CLOCK).access_readiness(self.unit, Evidence())["findings"])

    def test_vendor_pending_approval_is_not_ready_and_does_not_assert_outage(self):
        finding = self.packet["metrics"]["access"]["findings"][0]
        self.assertIn("FACILITY_ORIENTATION", finding["unapproved_requirements"])
        self.assertFalse(finding["equipment_outage_asserted"])

    def test_quality_campaign_and_missing_context(self):
        data = copy.deepcopy(self.tables)
        for r in data["unit_activity"]:
            if r["unit_id"] == "ICU" and r["activity_date"] == "2026-10-16":
                r["reporting_campaign"] = True
        metric = IntelligenceEngine(data, CLOCK).quality(self.unit, Evidence())
        self.assertEqual(metric["status"], "reporting_context_changed")
        self.assertFalse(metric["review_required"])
        data["unit_activity"] = []
        self.assertEqual(IntelligenceEngine(data, CLOCK).quality(self.unit, Evidence())["status"], "insufficient_denominator")

    def test_api_persists_full_investigation_packet(self):
        with TestClient(create_app(self.settings)) as client:
            listing = client.get("/api/investigations").json()
            self.assertTrue(any(r["unit_id"] == "ICU" for r in listing["items"]))
            response = client.get("/api/investigations/FAC-01:ICU:readiness")
            self.assertEqual(response.status_code, 200)
            packet = response.json()
            saved = client.get(packet["artifact_url"]).json()
            self.assertEqual(saved["input_hash"], packet["input_hash"])
            self.assertEqual(saved["metrics"], packet["metrics"])
            self.assertEqual(client.get("/api/investigations/not-found").status_code, 404)
            self.assertEqual(client.get("/api/investigations?as_of=invalid").status_code, 422)
            self.assertEqual(len(client.get("/api/intelligence/units").json()["units"]), 6)

    def test_api_cache_refreshes_when_source_database_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings.load({}, Path(folder))
            settings.data_dir.mkdir(parents=True)
            shutil.copy2(self.settings.database_path, settings.database_path)
            with TestClient(create_app(settings)) as client:
                before = client.get("/api/investigations/FAC-01:ICU:readiness").json()
                with sqlite3.connect(settings.database_path) as conn:
                    conn.execute("UPDATE unavailability SET status = 'withdrawn'")
                after = client.get("/api/investigations/FAC-01:ICU:readiness").json()
                self.assertNotEqual(before["snapshot_id"], after["snapshot_id"])
                self.assertEqual(after["metrics"]["coverage"]["uncovered_rn_hours"], 0)
                saved = client.get(before["artifact_url"]).json()
                self.assertEqual(saved["metrics"]["coverage"]["uncovered_rn_hours"], 36)

    def test_investigation_storage_failure_is_explicit(self):
        from unittest.mock import patch
        from pulse.storage import EvidenceStore
        with TestClient(create_app(self.settings)) as client, patch.object(
                EvidenceStore, "put_json", side_effect=OSError("unavailable")):
            self.assertEqual(client.get("/api/investigations/FAC-01:ICU:readiness").status_code, 503)


if __name__ == "__main__":
    unittest.main()
