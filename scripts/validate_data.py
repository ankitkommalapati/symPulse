#!/usr/bin/env python3
"""Validate fixture integrity and hero arithmetic, not Pulse detection performance."""
import argparse
import hashlib
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def elapsed(start, end):
    return (parse(end) - parse(start)).total_seconds() / 3600


def validate(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    clock = manifest["as_of"]
    tables = {}
    checks = []
    def check(condition, description):
        if not condition:
            raise AssertionError(description)
        checks.append(description)

    db = sqlite3.connect("file:%s?mode=ro" % (folder / "pulse_demo.sqlite"), uri=True)
    for table, meta in manifest["tables"].items():
        raw = (folder / (table + ".jsonl")).read_bytes()
        check(hashlib.sha256(raw).hexdigest() == meta["sha256"], table + " manifest hash")
        rows = [json.loads(line) for line in raw.splitlines()]
        tables[table] = rows
        check(len(rows) == meta["records"], table + " record count")
        check(db.execute('SELECT count(*) FROM "%s"' % table).fetchone()[0] == len(rows), table + " SQLite parity")
        keys = [(r["record_id"], r["record_version"]) for r in rows]
        check(len(keys) == len(set(keys)), table + " unique record versions")
        check(all(r["synthetic"] is True for r in rows), table + " synthetic marker")
        check(all(parse(r["source_updated_at"]) <= parse(r["available_at"]) for r in rows), table + " availability ordering")
    db.close()

    crosswalk = {(r["source_namespace"], r["source_entity_id"]): r["canonical_id"]
                 for r in tables["entity_crosswalk"] if r["entity_type"] == "unit"}
    employees = {r["employee_number"]: r for r in tables["employees"]}
    assignments = {r["record_id"]: r for r in tables["workforce_assignments"]}
    check(all(r["employee_number"] in employees for r in assignments.values()), "Assignment employee foreign keys")
    check(all(("workforce", r["organization_code"]) in crosswalk for r in assignments.values()), "Assignment department mappings")
    check(all(parse(r["shift_start"]) < parse(r["shift_end"]) for r in assignments.values()), "Positive assignment intervals")
    by_employee = defaultdict(list)
    for row in assignments.values():
        by_employee[row["employee_number"]].append(row)
    for rows in by_employee.values():
        ordered = sorted(rows, key=lambda r: r["shift_start"])
        check(all(parse(a["shift_end"]) <= parse(b["shift_start"]) for a, b in zip(ordered, ordered[1:])),
              "No baseline schedule overlap: " + rows[0]["employee_number"])

    paid = defaultdict(float)
    for r in tables["paid_time"]:
        check(r["assignment_record_id"] in assignments, "Paid time assignment foreign key")
        check(parse(r["worked_end"]) <= parse(clock), "No future worked time")
        paid[r["assignment_record_id"]] += r["hours"]
    check(all(abs(paid[k] - elapsed(assignments[k]["shift_start"], assignments[k]["shift_end"])) < 0.002 for k in paid),
          "Regular plus overtime equals elapsed worked hours")
    dst = [r for r in assignments.values() if r["source_record_id"].startswith("ICU-2026-10-31-NIGHT")]
    check(len(dst) == 8 and all(elapsed(r["shift_start"], r["shift_end"]) == 13 for r in dst), "DST night is 13 elapsed hours")

    hero = json.loads((folder / "hero_summary.json").read_text())
    target_start, target_end = hero["target_shift_start"], hero["target_shift_end"]
    target = [r for r in assignments.values() if r["shift_start"] == target_start and r["organization_code"] == "110"]
    absences = [r for r in tables["unavailability"] if parse(r["available_at"]) <= parse(clock) and
                parse(r["start"]) < parse(target_end) and parse(r["end"]) > parse(target_start)]
    check(len(target) == 8 and len(absences) == 3, "Hero has eight planned RNs and three known absences")
    req = [r for r in tables["staffing_requirements"] if r["organization_code"] == "110" and r["shift_start"] == target_start][0]
    unavailable = {r["employee_number"] for r in absences}
    before = req["required_count"] - sum(r["employee_number"] not in unavailable for r in target)
    check(before * elapsed(target_start, target_end) == hero["uncovered_rn_hours_before"] == 36, "Hero 36 RN-hours reconcile")
    donors = [r for r in assignments.values() if r["shift_start"] == target_start and r["organization_code"] == "120"]
    proposed = hero["proposed_reassignment_employee_ids"]
    donor_req = [r for r in tables["staffing_requirements"] if r["organization_code"] == "120" and r["shift_start"] == target_start][0]
    check(len(donors) - len(proposed) >= donor_req["required_count"], "Joint donor coverage remains feasible")
    for employee in proposed:
        quals = [r for r in tables["employee_qualifications"] if r["employee_number"] == employee and
                 r["qualification_status"] == "verified" and parse(r["effective_from"]) <= parse(target_start) and
                 parse(r["effective_to"]) >= parse(target_end)]
        check({"RN_LICENSE", "ICU_COMPETENCY"} <= {r["qualification_code"] for r in quals}, "Donor has valid license and ICU competency")
        other = [r for r in by_employee[employee] if r["shift_start"] != target_start]
        rest_ok = all(parse(r["shift_end"]) <= parse(target_start) - timedelta(hours=12) or
                      parse(r["shift_start"]) >= parse(target_end) + timedelta(hours=12) for r in other)
        check(rest_ok, "Donor has at least demo 12-hour rest buffer")
        recent = [r for r in by_employee[employee] if parse(target_end) - timedelta(days=7) <= parse(r["shift_start"]) < parse(target_end)]
        check(sum(elapsed(r["shift_start"], r["shift_end"]) for r in recent) <= 60, "Donor within illustrative weekly hours cap")
    check((before - len(proposed)) * elapsed(target_start, target_end) == hero["uncovered_rn_hours_after_two_reassignments"] == 12,
          "Hero residual 12 RN-hours reconcile")
    unqualified = [r for r in donors if r["employee_number"] not in proposed][0]["employee_number"]
    check(not any(r["employee_number"] == unqualified and r["qualification_code"] == "ICU_COMPETENCY"
                  for r in tables["employee_qualifications"]), "Apparently available candidate lacks ICU competency")

    provider_map = {r["source_entity_id"]: r["provider_source_key"] for r in tables["entity_crosswalk"]
                    if r["entity_type"] == "provider"}
    check(all(r["physician_code"] in provider_map for r in tables["physician_assignments"]), "Physician assignment identity mappings")
    grants = {r["provider_key"]: r for r in tables["privilege_grants"]}
    physician_day = [r for r in tables["physician_assignments"] if r["starts_at"] == target_start and r["department_code"] == "CCT"][0]
    expiring = grants[provider_map[physician_day["physician_code"]]]
    check(parse(target_start) < parse(expiring["valid_to"]) < parse(target_end), "Provider grant expires mid-assignment")
    check(elapsed(expiring["valid_to"], target_end) == 6, "Provider exposure is six physician-hours")
    check(parse(grants["P002"]["valid_to"]) > parse(target_end), "Second pending renewal retains valid grant")

    check(all(r["actual_harm"] == "none" for r in tables["quality_events"] if r["event_type"] == "near_miss"), "Near misses have no actual harm")
    check(all(parse(r["occurred_at"]) <= parse(r["reported_at"]) <= parse(r["available_at"]) for r in tables["quality_events"]), "Quality event reporting chronology")
    check(any(parse(r["available_at"]) > parse(clock) for r in tables["quality_events"]), "Late-arrival records exist and require as-of filtering")
    check(len({r["record_id"] for r in tables["quality_events"]}) < len(tables["quality_events"]), "Revised events exist and require version deduplication")
    reps = {r["representative_key"] for r in tables["vendor_representatives"]}
    check(all(r["representative_key"] in reps for r in tables["vendor_credentials"] + tables["vendor_visits"]), "Access representative foreign keys")
    check(any(r["representative_key"] == "SYN-REP-01" and r["verification_status"] == "pending_review"
              for r in tables["vendor_credentials"]), "Hero vendor has unapproved required credential")
    cases = json.loads((folder / "evaluation_cases.json").read_text())["cases"]
    check(len(cases) == 30 and len({c["case_id"] for c in cases}) == 30, "Thirty unique analytical fixtures")
    check({c["split"] for c in cases} == {"tune", "holdout"}, "Tuning and holdout fixtures tagged")
    result = {"status": "passed", "checks": len(checks), "source_records": sum(map(len, tables.values())),
              "tables": len(tables), "evaluation_fixtures": len(cases),
              "scope": "Data integrity and hero arithmetic only; detector/model/UI evaluation not implemented"}
    (folder / "validation_report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "generated")
    validate(parser.parse_args().data_dir)
