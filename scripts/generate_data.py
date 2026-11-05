#!/usr/bin/env python3
"""Generate workflow-informed fictional records. No real symplr schemas or people."""
import argparse
import hashlib
import json
import random
import sqlite3
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/Chicago")
AS_OF = datetime(2026, 11, 5, 8, tzinfo=TZ)
FIRST = date(2026, 8, 7)
TARGET = date(2026, 11, 6)
SOURCE_CODES = {
    "workforce": ["110", "120", "130", "140", "150", "160"],
    "provider": ["CC", "SD", "EM", "SU", "MS", "RE"],
    "physician_scheduling": ["CCT", "STEP", "ED", "SURG", "MED", "REH"],
    "quality": ["ICU-A", "STEP-A", "EMERG", "PERIOP", "MEDSURG", "REHAB"],
    "access": ["A-01", "A-02", "A-03", "A-04", "A-05", "A-06"],
}
UNITS = ["ICU", "STEPDOWN", "ED", "SURGERY", "MEDSURG", "REHAB"]


def iso(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def dt(day, hour):
    return datetime.combine(day, time(hour), TZ)


def shift_bounds(day, shift):
    start = dt(day, 7 if shift == "DAY" else 19)
    end = dt(day, 19) if shift == "DAY" else dt(day + timedelta(days=1), 7)
    return start, end


def hours(start, end):
    return (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 3600


def parse(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def generate(seed, output):
    rng = random.Random(seed)
    tables = defaultdict(list)

    def add(table, source, source_id, available, **fields):
        row = {
            "record_id": source + ":" + table + ":" + source_id,
            "source_system": source,
            "source_record_id": source_id,
            "record_version": 1,
            "source_updated_at": iso(available),
            "available_at": iso(available),
            "is_deleted": False,
            "synthetic": True,
        }
        row.update(fields)
        tables[table].append(row)
        return row

    initial = dt(FIRST - timedelta(days=7), 8)
    add("facilities", "planning_context", "FAC-01", initial,
        facility_id="FAC-01", name="St. Mary's Demo Medical Center", timezone="America/Chicago")
    source_facilities = {"workforce": "H01", "provider": "SM-DEMO", "physician_scheduling": "MAIN",
                         "quality": "STMARY", "access": "ST-MAIN"}
    for source, code in source_facilities.items():
        add("entity_crosswalk", "planning_context", source + "-FACILITY", initial,
            entity_type="facility", source_namespace=source, source_entity_id=code,
            canonical_id="FAC-01", facility_id="FAC-01", mapping_status="verified_demo_mapping",
            valid_from=iso(initial), valid_to="2027-12-31T23:59:59Z")
    for u, unit in enumerate(UNITS):
        add("units", "planning_context", unit, initial, unit_id=unit, facility_id="FAC-01",
            display_name=unit.replace("STEPDOWN", "Step-down").title(),
            required_rns=8 if u == 0 else 6, policy_label="Illustrative demo staffing requirement")
        for source, codes in SOURCE_CODES.items():
            add("entity_crosswalk", "planning_context", source + "-" + unit, initial,
                entity_type="unit", source_namespace=source, source_entity_id=codes[u],
                source_facility_id=source_facilities[source],
                canonical_id=unit, facility_id="FAC-01", mapping_status="verified_demo_mapping",
                valid_from=iso(initial), valid_to="2027-12-31T23:59:59Z")

    employee_by_unit = {}
    for u, unit in enumerate(UNITS):
        staff = []
        for i in range(32):
            employee_id = "SYN-RN-%03d" % (u * 32 + i + 1)
            staff.append(employee_id)
            add("employees", "workforce", employee_id, initial, employee_number=employee_id,
                display_name="Demo Nurse %03d" % (u * 32 + i + 1),
                home_org_code=SOURCE_CODES["workforce"][u], facility_code="H01",
                job_class="RN", employment_status="active", fte=1.0,
                base_hourly_rate_usd=50.0, cohort=i // 8)
            for qualification in ["RN_LICENSE"] + (["ICU_COMPETENCY"] if u == 0 or (u == 1 and i % 8 < 2) else []):
                add("employee_qualifications", "workforce", employee_id + "-" + qualification,
                    initial, employee_number=employee_id, qualification_code=qualification,
                    qualification_status="verified", effective_from=iso(initial),
                    effective_to="2027-12-31T23:59:59Z", facility_code="H01",
                    eligible_org_codes=SOURCE_CODES["workforce"] if qualification == "RN_LICENSE" else ["110", "120"])
        employee_by_unit[unit] = staff

    target_cancellations = []
    target_donors = []
    for day_index in range(97):
        day = FIRST + timedelta(days=day_index)
        for u, unit in enumerate(UNITS):
            # Small, stable weekday context. Patient-days are aggregate context, not PHI.
            if day < AS_OF.date():
                available = dt(day + timedelta(days=1), 3)
                add("unit_activity", "planning_context", unit + "-" + day.isoformat(), available,
                    unit_id=unit, activity_date=day.isoformat(),
                    patient_days=max(8, (20 if u == 0 else 28) + rng.randint(-2, 2)),
                    reporting_campaign=False, denominator_origin="synthetic aggregate planning context")
            for shift in ("DAY", "NIGHT"):
                start, end = shift_bounds(day, shift)
                planned_at = min(start - timedelta(days=14), AS_OF - timedelta(days=1))
                unit_code = SOURCE_CODES["workforce"][u]
                req = add("staffing_requirements", "workforce", "%s-%s-%s" % (unit, day, shift),
                          planned_at, organization_code=unit_code, facility_code="H01",
                          shift_start=iso(start), shift_end=iso(end), shift_class=shift,
                          job_class="RN", required_count=8 if u == 0 else 6)
                block = 0 if day_index % 4 < 2 else 1
                cohort = block + (2 if shift == "NIGHT" else 0)
                staff = employee_by_unit[unit][cohort * 8:cohort * 8 + 8]
                for pos, employee_id in enumerate(staff):
                    assignment_id = "%s-%s-%s-%02d" % (unit, day, shift, pos)
                    row = add("workforce_assignments", "workforce", assignment_id, planned_at,
                              employee_number=employee_id, organization_code=unit_code,
                              home_org_code=unit_code, facility_code="H01", job_class="RN",
                              shift_start=iso(start), shift_end=iso(end), shift_class=shift,
                              assignment_status="scheduled", requirement_record_id=req["record_id"])
                    if day == TARGET and shift == "DAY" and unit == "ICU" and pos < 3:
                        target_cancellations.append(row)
                        notice = AS_OF - timedelta(hours=3 - pos)
                        add("unavailability", "workforce", "ABS-HERO-%s" % pos, notice,
                            employee_number=employee_id, start=iso(start), end=iso(end),
                            status="approved", reason_code="UNAVAILABLE", assignment_record_id=row["record_id"])
                    if day == TARGET and shift == "DAY" and unit == "STEPDOWN" and pos < 2:
                        target_donors.append(row)
                    if end <= AS_OF:
                        duration = hours(start, end)
                        # Classified paid-time extract, not an inferred legal/payroll engine.
                        share = 0.06 + rng.uniform(-0.012, 0.012)
                        if unit == "ICU" and day_index >= 56:
                            share += (day_index - 55) * 0.0035
                        overtime = round(duration * share, 3)
                        regular = round(duration - overtime, 3)
                        for code, amount in (("REG", regular), ("OT", overtime)):
                            add("paid_time", "workforce", assignment_id + "-" + code,
                                end + timedelta(minutes=20), employee_number=employee_id,
                                organization_code=unit_code, facility_code="H01",
                                assignment_record_id=row["record_id"], work_date=day.isoformat(),
                                shift_class=shift, worked_start=iso(start), worked_end=iso(end),
                                pay_code=code, hours=amount,
                                hourly_rate_usd=75.0 if code == "OT" else 50.0,
                                classification_origin="Synthetic preclassified productive paid time; not payroll-law calculation")

    for u, unit in enumerate(UNITS):
        for i in range(3):
            n = u * 3 + i + 1
            source_provider = "P%03d" % n
            canonical = "SYN-PROV-%03d" % n
            add("providers", "provider", source_provider, initial, provider_key=source_provider,
                synthetic_provider_id=canonical, display_name="Demo Physician %03d" % n,
                specialty="Critical Care" if u == 0 else unit.title(), status="active",
                facility_code="SM-DEMO", department_code=SOURCE_CODES["provider"][u])
            add("entity_crosswalk", "planning_context", "PROV-%03d" % n, initial,
                entity_type="provider", source_namespace="physician_scheduling",
                source_entity_id="DOC-%03d" % n, canonical_id=canonical, facility_id="FAC-01",
                provider_source_key=source_provider, mapping_status="verified_demo_mapping",
                valid_from=iso(initial), valid_to="2027-12-31T23:59:59Z")
            expiry = dt(date(2027, 6, 30), 19)
            if n == 1:
                expiry = dt(TARGET, 13)
            elif n == 2:
                expiry = dt(date(2026, 11, 20), 19)
            grant = add("privilege_grants", "provider", "GRANT-%03d" % n, initial,
                        provider_key=source_provider, facility_code="SM-DEMO",
                        department_code=SOURCE_CODES["provider"][u], service_code="SERVICE-" + unit,
                        grant_status="active", valid_from=iso(initial), valid_to=iso(expiry))
            if n <= 2:
                add("renewal_cases", "provider", "RENEW-%03d" % n, AS_OF - timedelta(days=10),
                    provider_key=source_provider, grant_record_id=grant["record_id"],
                    workflow_status="pending_committee_review", due_at=iso(expiry),
                    submitted_at=iso(AS_OF - timedelta(days=12)), approved_at=None)
        for d in range(97):
            day = FIRST + timedelta(days=d)
            for shift in ("DAY", "NIGHT"):
                start, end = shift_bounds(day, shift)
                n = u * 3 + (0 if shift == "DAY" else 1) + 1
                add("physician_assignments", "physician_scheduling", "%s-%s-%s" % (unit, day, shift),
                    min(start - timedelta(days=21), AS_OF - timedelta(days=1)),
                    physician_code="DOC-%03d" % n, department_code=SOURCE_CODES["physician_scheduling"][u],
                    facility_code="MAIN", service_code="SERVICE-" + unit,
                    starts_at=iso(start), ends_at=iso(end), assignment_status="confirmed")

    quality_seq = 0
    for d in range(90):
        day = FIRST + timedelta(days=d)
        for u, unit in enumerate(UNITS):
            # Intentionally sparse reports, with a stronger final-period ICU change.
            probability = 0.40 if unit == "ICU" else 0.25
            if unit == "ICU" and d >= 69:
                probability = 0.80
            count = int(rng.random() < probability) + int(rng.random() < probability * 0.22)
            for _ in range(count):
                quality_seq += 1
                occurred = dt(day, rng.randint(0, 23)) + timedelta(minutes=rng.randint(0, 59))
                reported = occurred + timedelta(hours=rng.choice([2, 4, 8, 24, 48]))
                available = reported + timedelta(minutes=15)
                event = add("quality_events", "quality", "EVT-%05d" % quality_seq, available,
                            facility_code="STMARY", location_code=SOURCE_CODES["quality"][u],
                            occurred_at=iso(occurred), reported_at=iso(reported),
                            event_type="near_miss", actual_harm="none", workflow_status="submitted",
                            narrative="Synthetic near-miss report for operational review; no patient or reporter identity.")
                if quality_seq % 29 == 0:
                    revision = dict(event)
                    revision.update(record_version=2, workflow_status="under_review",
                                    source_updated_at=iso(available + timedelta(hours=12)),
                                    available_at=iso(available + timedelta(hours=12)))
                    tables["quality_events"].append(revision)

    for v in range(8):
        vendor = "SYN-VENDOR-%02d" % (v + 1)
        add("vendors", "access", vendor, initial, vendor_key=vendor,
            company_name="Demo Service Supplier %02d" % (v + 1))
        for j in range(2):
            rep = "SYN-REP-%02d" % (v * 2 + j + 1)
            add("vendor_representatives", "access", rep, initial,
                representative_key=rep, vendor_key=vendor, name="Demo Representative %02d" % (v * 2 + j + 1))
            for credential in ("FACILITY_ORIENTATION", "SCREENING"):
                pending = rep == "SYN-REP-01" and credential == "FACILITY_ORIENTATION"
                add("vendor_credentials", "access", rep + "-" + credential,
                    AS_OF - timedelta(hours=4) if pending else initial,
                    representative_key=rep, facility_code="ST-MAIN", policy_code="PATIENT_AREA_DEMO",
                    credential_code=credential, verification_status="pending_review" if pending else "approved",
                    valid_from=iso(initial), valid_to="2027-12-31T23:59:59Z")
    for d in range(0, 97, 3):
        day = FIRST + timedelta(days=d)
        for u in range(2):
            start = dt(day, 10)
            add("vendor_visits", "access", "VISIT-%s-%s" % (day, u),
                min(start - timedelta(days=20), AS_OF - timedelta(days=1)),
                representative_key="SYN-REP-%02d" % (u * 2 + 2), facility_code="ST-MAIN",
                destination_code=SOURCE_CODES["access"][u], scheduled_start=iso(start),
                scheduled_end=iso(start + timedelta(hours=2)), purpose="scheduled_service",
                visit_status="scheduled", policy_code="PATIENT_AREA_DEMO")
    visit = add("vendor_visits", "access", "VISIT-HERO", AS_OF - timedelta(days=20),
                representative_key="SYN-REP-01", facility_code="ST-MAIN", destination_code="A-01",
                scheduled_start=iso(dt(TARGET, 10)), scheduled_end=iso(dt(TARGET, 12)),
                purpose="scheduled_service", visit_status="scheduled", policy_code="PATIENT_AREA_DEMO")
    for credential in ("FACILITY_ORIENTATION", "SCREENING"):
        add("access_policy_requirements", "access", "PATIENT_AREA_DEMO-" + credential, initial,
            facility_code="ST-MAIN", policy_code="PATIENT_AREA_DEMO", credential_code=credential,
            required=True, valid_from=iso(initial), valid_to="2027-12-31T23:59:59Z")
    add("service_dependencies", "planning_context", "DEPENDENCY-HERO", AS_OF - timedelta(days=20),
        unit_id="ICU", visit_record_id=visit["record_id"], importance="time_sensitive",
        description="Demo planned equipment service; no outage or asset capacity asserted",
        criticality_origin="Local synthetic planning context; not an Access product field")

    output.mkdir(parents=True, exist_ok=True)
    # Only files owned by this generator are replaced. SQLite is rebuilt atomically below.
    manifest = {"schema_version": "pulse-demo-1.0", "seed": seed, "as_of": iso(AS_OF),
                "hospital_timezone": str(TZ), "historical_start": FIRST.isoformat(),
                "synthetic": True, "private_symplr_schema": False,
                "archive_includes_future_arrivals": True,
                "archive_note": "Replay archive, not an as-of export; filter available_at before using records",
                "tables": {}}
    dictionary = {}
    db_tmp = output / "pulse_demo.sqlite.tmp"
    if db_tmp.exists():
        db_tmp.unlink()
    conn = sqlite3.connect(db_tmp)
    for table, records in sorted(tables.items()):
        data = "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in records)
        (output / (table + ".jsonl")).write_text(data)
        manifest["tables"][table] = {"records": len(records), "sha256": hashlib.sha256(data.encode()).hexdigest()}
        columns = sorted(set().union(*(r.keys() for r in records)))
        inferred = {}
        for column in columns:
            values = [r.get(column) for r in records if r.get(column) is not None]
            inferred[column] = sorted({type(v).__name__ for v in values})
        dictionary[table] = {"grain": "source record/version; see DATA_SPEC.md", "fields": inferred}
        sqltypes = {}
        for column, types in inferred.items():
            sqltypes[column] = "INTEGER" if set(types) <= {"int", "bool"} else "REAL" if set(types) <= {"int", "float"} else "TEXT"
        conn.execute('CREATE TABLE "%s" (%s)' % (table, ",".join('"%s" %s' % (c, sqltypes[c]) for c in columns)))
        def value(row, col):
            item = row.get(col)
            return json.dumps(item, sort_keys=True) if isinstance(item, (list, dict)) else item
        conn.executemany('INSERT INTO "%s" VALUES (%s)' % (table, ",".join("?" for _ in columns)),
                         [[value(r, c) for c in columns] for r in records])
        conn.execute('CREATE INDEX "%s_availability" ON "%s" (available_at)' % (table, table))
        conn.execute('CREATE INDEX "%s_identity" ON "%s" (record_id, record_version)' % (table, table))
    conn.commit()
    conn.close()
    db_tmp.replace(output / "pulse_demo.sqlite")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "data_dictionary.json").write_text(json.dumps(dictionary, indent=2) + "\n")
    write_evaluation(output)
    # This is a computed arithmetic sanity summary, not a detector result.
    duration = hours(*shift_bounds(TARGET, "DAY"))
    summary = {
        "kind": "computed_hero_fixture_summary_not_detector_output", "as_of": iso(AS_OF),
        "target_shift_start": iso(shift_bounds(TARGET, "DAY")[0]),
        "target_shift_end": iso(shift_bounds(TARGET, "DAY")[1]),
        "icu_required_rns": 8, "planned_rns": 8,
        "known_unavailable_rns": len(target_cancellations),
        "eligible_available_rns_before": 8 - len(target_cancellations),
        "uncovered_rn_hours_before": len(target_cancellations) * duration,
        "proposed_reassignment_employee_ids": [r["employee_number"] for r in target_donors],
        "uncovered_rn_hours_after_two_reassignments": (len(target_cancellations) - len(target_donors)) * duration,
        "donor_required_rns": 6, "donor_rns_after": 8 - len(target_donors),
        "unresolved": ["Residual ICU RN gap", "Provider grant interval", "Vendor verification", "Quality review"],
        "no_realized_savings_claim": True,
    }
    (output / "hero_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"output": str(output), "table_count": len(tables),
                      "total_source_records": sum(len(r) for r in tables.values()),
                      "hero": summary}, indent=2))


def write_evaluation(output):
    """Small independent challenge inputs. Labels are NOT detector features."""
    cases = []
    def case(name, family, inputs, expected, split):
        cases.append({"case_id": name, "family": family, "split": split,
                      "input": inputs, "expected": expected, "synthetic": True})
    for i, kind in enumerate(("sudden_spike", "gradual_drift", "stable", "weekday_seasonality", "zero_variance", "stale_feed")):
        values = [0.06 + (0.002 if j % 7 < 5 else -0.005) for j in range(90)]
        if kind == "sudden_spike":
            values[-4:] = [0.22] * 4
        if kind == "gradual_drift":
            values[56:] = [0.06 + (j + 1) * 0.003 for j in range(34)]
        if kind == "zero_variance":
            values = [0.06] * 90
        case("DRIFT-" + kind, "drift", {"overtime_share": values, "baseline_days": 56,
             "fresh": kind != "stale_feed"}, {"finding": kind in ("sudden_spike", "gradual_drift"),
             "data_issue": kind == "stale_feed"}, "tune" if i % 3 == 0 else "holdout")
    provider_cases = [
        ("expires_mid_shift", "2026-11-06T19:00:00Z", "pending", True),
        ("pending_valid", "2026-11-21T01:00:00Z", "pending", False),
        ("expired_before_shift", "2026-11-05T19:00:00Z", "pending", True),
        ("ends_at_shift_end", "2026-11-07T01:00:00Z", "pending", False),
        ("wrong_facility", "2027-01-01T00:00:00Z", "approved", True),
        ("renewed_effective", "2027-01-01T00:00:00Z", "approved", False),
    ]
    for i, (name, end, renewal, finding) in enumerate(provider_cases):
        case("PROVIDER-" + name, "provider", {"assignment_start": "2026-11-06T13:00:00Z",
             "assignment_end": "2026-11-07T01:00:00Z", "grant_end": end,
             "grant_facility_matches": name != "wrong_facility", "renewal_status": renewal},
             {"finding": finding}, "tune" if i % 3 == 0 else "holdout")
    for i, name in enumerate(("missing_credential", "pending_review", "all_valid", "wrong_unit", "late_arrival", "stale_status")):
        case("ACCESS-" + name, "access", {"verification_status": "missing" if name == "missing_credential" else
             "pending_review" if name == "pending_review" else "approved", "unit_matches": name != "wrong_unit",
             "available_by_clock": name != "late_arrival", "fresh": name != "stale_status"},
             {"finding": name in ("missing_credential", "pending_review"),
              "data_issue": name in ("late_arrival", "stale_status")}, "tune" if i % 3 == 0 else "holdout")
    for i, name in enumerate(("feasible_two", "missing_competency", "joint_donor_shortage", "overlap", "insufficient_rest", "absence")):
        case("PLAN-" + name, "simulation", {"donor_assigned": 8 if name != "joint_donor_shortage" else 7,
             "donor_required": 6, "requested_moves": 2,
             "competency_valid": name != "missing_competency", "has_overlap": name == "overlap",
             "rest_hours": 6 if name == "insufficient_rest" else 12,
             "approved_unavailability": name == "absence"},
             {"feasible": name == "feasible_two"}, "tune" if i % 3 == 0 else "holdout")
    for i, name in enumerate(("rate_rise", "stable_rate", "reporting_campaign", "denominator_growth", "missing_denominator", "late_reports")):
        case("QUALITY-" + name, "quality", {"baseline_reports": 20, "current_reports": 40 if name != "stable_rate" else 20,
             "baseline_patient_days": 420, "current_patient_days": None if name == "missing_denominator" else
             840 if name == "denominator_growth" else 420,
             "reporting_campaign": name == "reporting_campaign", "reports_available": name != "late_reports"},
             {"unexplained_rate_review": name == "rate_rise", "causal_claim_permitted": False,
              "data_issue": name in ("missing_denominator", "late_reports")}, "tune" if i % 3 == 0 else "holdout")
    (output / "evaluation_cases.json").write_text(json.dumps({
        "description": "30 labeled component fixtures, not measured application results. Families have distinct labels; do not pool unlike tasks into a single accuracy claim.",
        "cases": cases}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "generated")
    args = parser.parse_args()
    generate(args.seed, args.output)
