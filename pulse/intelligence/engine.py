"""Unit readiness investigations computed exclusively from known operational records."""
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pulse.intelligence import ENGINE_VERSION
from pulse.intelligence.identity import IdentityResolver
from pulse.intelligence.rules import (RuleConfig, duration, instant, overlaps, overtime_drift,
                                      quality_review, readiness_priority, stamp, uncovered_intervals)


def content_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class Evidence:
    def __init__(self):
        self.records = {}
        self.groups = {}

    def group(self, group_id, rows, formula):
        unique = {r["record_id"]: r for r in rows}
        self.records.update(unique)
        self.groups[group_id] = {"id": group_id, "formula": formula,
                                 "record_ids": sorted(unique), "input_hash": content_hash([unique[key] for key in sorted(unique)])}
        return group_id


class IntelligenceEngine:
    def __init__(self, tables, as_of, hospital_timezone="America/Chicago", config=RuleConfig()):
        self.tables = tables
        self.now = instant(as_of)
        self.end = self.now + timedelta(hours=config.horizon_hours)
        self.zone = ZoneInfo(hospital_timezone)
        self.config = config
        self.identity = IdentityResolver(tables["entity_crosswalk"])
        self.mapping_issues = set()
        self.input_hash = content_hash(tables)
        self.employees = {r["employee_number"]: r for r in tables["employees"]}
        self.qualifications = defaultdict(list)
        self.absences = defaultdict(list)
        self.work = defaultdict(list)
        for r in tables["employee_qualifications"]:
            self.qualifications[r["employee_number"]].append(r)
        for r in tables["unavailability"]:
            if r["status"] == "approved":
                self.absences[r["employee_number"]].append(r)
        for r in tables["workforce_assignments"]:
            if r["assignment_status"] in ("scheduled", "confirmed"):
                self.work[r["employee_number"]].append(r)

    def _unit(self, source, code, facility, start=None, end=None):
        result = self.identity.unit(source, code, facility, start or self.now, end or self.end)
        if result is None:
            self.mapping_issues.add("%s department %s at facility %s has no unique valid crosswalk" % (source, code, facility))
        return result

    def _facility(self, source, code, start=None, end=None):
        result = self.identity.facility(source, code, start or self.now, end or self.end)
        if result is None:
            self.mapping_issues.add("%s facility %s has no unique valid crosswalk" % (source, code))
        return result

    def _matches_unit(self, source, code, facility, unit, start, end):
        return (self._unit(source, code, facility, start, end) == unit["unit_id"]
                and self._facility(source, facility, start, end) == unit["facility_id"])

    def coverage(self, unit, evidence):
        requirements, assignments = [], []
        for r in self.tables["staffing_requirements"]:
            if overlaps(r["shift_start"], r["shift_end"], self.now, self.end) and self._matches_unit(
                    "workforce", r["organization_code"], r["facility_code"], unit, r["shift_start"], r["shift_end"]):
                requirements.append(r)
        for r in self.tables["workforce_assignments"]:
            if r["assignment_status"] in ("scheduled", "confirmed") and overlaps(
                    r["shift_start"], r["shift_end"], self.now, self.end) and self._matches_unit(
                    "workforce", r["organization_code"], r["facility_code"], unit, r["shift_start"], r["shift_end"]):
                assignments.append(r)
        supporting = list(requirements) + list(assignments)
        segments, issues = [], []
        covered_hours, gap_hours, required_hours, unknown_hours = 0.0, 0.0, 0.0, 0.0
        for requirement in requirements:
            left, right = max(self.now, instant(requirement["shift_start"])), min(self.end, instant(requirement["shift_end"]))
            points = {left, right}
            cursor = left
            while cursor < right:
                points.add(cursor)
                cursor += timedelta(minutes=15)
            candidates = [r for r in assignments if overlaps(r["shift_start"], r["shift_end"], left, right)]
            for assignment in candidates:
                employee = assignment["employee_number"]
                supporting.extend(self.qualifications[employee] + self.absences[employee])
                if employee in self.employees:
                    supporting.append(self.employees[employee])
                for r, a, b in [(assignment, "shift_start", "shift_end")] + [
                        (r, "effective_from", "effective_to") for r in self.qualifications[employee]] + [
                        (r, "start", "end") for r in self.absences[employee]] + [
                        (r, "shift_start", "shift_end") for r in self.work[employee]]:
                    for field in (a, b):
                        point = instant(r[field])
                        if left < point < right:
                            points.add(point)
            for start, end in zip(sorted(points), sorted(points)[1:]):
                active_requirements = [r for r in requirements if overlaps(r["shift_start"], r["shift_end"], start, end)]
                if len(active_requirements) != 1:
                    issues.append("Overlapping staffing requirements require reconciliation")
                    continue
                if requirement["job_class"] != "RN":
                    issues.append("Staffing requirement has an unsupported role")
                    continue
                active = [r for r in candidates if instant(r["shift_start"]) <= start and instant(r["shift_end"]) >= end]
                eligible, excluded, uncertain_people = set(), [], set()
                for r in active:
                    employee = self.employees.get(r["employee_number"])
                    key = r["employee_number"]
                    reason = None
                    uncertain = False
                    if any(overlaps(a["start"], a["end"], start, end) for a in self.absences[key]):
                        reason = "approved_unavailability"
                    elif employee is None:
                        reason, uncertain = "employee_record_missing", True
                    elif employee["employment_status"] != "active" or employee["job_class"] != "RN":
                        reason = "employment_or_role_ineligible"
                    elif self._facility("workforce", employee["facility_code"], start, end) != unit["facility_id"]:
                        reason, uncertain = "facility_permission_unverified", True
                    elif len([a for a in self.work[key] if overlaps(a["shift_start"], a["shift_end"], start, end)]) > 1:
                        reason = "conflicting_assignments"
                        supporting.extend(a for a in self.work[key] if overlaps(a["shift_start"], a["shift_end"], start, end))
                    else:
                        needed = {"RN_LICENSE"} | ({"ICU_COMPETENCY"} if unit["unit_id"] == "ICU" else set())
                        valid = {q["qualification_code"] for q in self.qualifications[key]
                                 if q["qualification_status"] == "verified"
                                 and instant(q["effective_from"]) <= start and instant(q["effective_to"]) >= end
                                 and r["organization_code"] in q["eligible_org_codes"]
                                 and q["facility_code"] == r["facility_code"]}
                        if not needed <= valid:
                            reason = "required_qualification_not_valid"
                            uncertain = uncertain or not needed <= {q["qualification_code"] for q in self.qualifications[key]}
                    if reason:
                        excluded.append({"employee_id": key, "reason": reason, "assignment_record_id": r["record_id"]})
                        if uncertain:
                            uncertain_people.add(key)
                    else:
                        eligible.add(key)
                required = requirement["required_count"]
                elapsed = duration(start, end)
                gap = max(0, required - len(eligible))
                unverified_gap = min(gap, len(uncertain_people - eligible))
                if not active:
                    unverified_gap = gap
                required_hours += required * elapsed
                covered_hours += min(required, len(eligible)) * elapsed
                gap_hours += gap * elapsed
                unknown_hours += unverified_gap * elapsed
                if gap:
                    segment = {"start": stamp(start), "end": stamp(end), "required_rns": required,
                               "eligible_rns": len(eligible), "gap_rns": gap, "uncovered_rn_hours": gap * elapsed,
                               "eligibility_uncertain": bool(unverified_gap), "excluded": excluded,
                               "requirement_record_id": requirement["record_id"]}
                    if segments and {k: v for k, v in segments[-1].items() if k not in ("start", "end", "uncovered_rn_hours")} == {
                            k: v for k, v in segment.items() if k not in ("start", "end", "uncovered_rn_hours")} and segments[-1]["end"] == segment["start"]:
                        segments[-1]["end"] = segment["end"]
                        segments[-1]["uncovered_rn_hours"] += segment["uncovered_rn_hours"]
                    else:
                        segments.append(segment)
        if not requirements:
            issues.append("No staffing requirements are known for the requested window")
        else:
            missing_window = uncovered_intervals(self.now, self.end, [(r["shift_start"], r["shift_end"]) for r in requirements])
            if missing_window:
                issues.append("Staffing requirements do not cover the entire requested window")
        group = evidence.group("workforce_coverage", supporting,
                               "Sum(max(0, required RN count - distinct eligible assigned RNs) * interval hours); 15-minute and exact event boundaries")
        return {"status": "insufficient_data" if issues or unknown_hours else "gap" if gap_hours else "covered",
                "required_rn_hours": required_hours, "covered_rn_hours": covered_hours,
                "uncovered_rn_hours": gap_hours, "unverified_gap_rn_hours": unknown_hours,
                "gap_segments": segments, "data_issues": sorted(set(issues)), "evidence_group_ids": [group]}

    def drift(self, unit, evidence):
        today = self.now.astimezone(self.zone).date()
        rows = [r for r in self.tables["paid_time"] if date.fromisoformat(r["work_date"]) < today
                and instant(r["worked_end"]) <= self.now and self._matches_unit(
                    "workforce", r["organization_code"], r["facility_code"], unit, r["worked_start"], r["worked_end"])]
        by_day_shift = defaultdict(lambda: {"paid": 0.0, "ot": 0.0})
        for r in rows:
            if r["pay_code"] in ("REG", "OT"):
                bucket = by_day_shift[(r["work_date"], r["shift_class"])]
                bucket["paid"] += r["hours"]
                bucket["ot"] += r["hours"] if r["pay_code"] == "OT" else 0
        dates = sorted({d for d, _ in by_day_shift})
        # The baseline is anchored to the archive's first observed date, never a rolling refit.
        if today > date.fromisoformat(self.config.baseline_start):
            first = date.fromisoformat(self.config.baseline_start)
            last = min(first + timedelta(days=self.config.history_days - 1), today - timedelta(days=1))
            dates = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
        shifts = {}
        for shift in ("DAY", "NIGHT"):
            series = []
            for day in dates:
                values = by_day_shift[(day, shift)]
                series.append({"date": day, "overtime_hours": values["ot"], "paid_hours": values["paid"],
                               "share": values["ot"] / values["paid"] if values["paid"] else None})
            shifts[shift] = overtime_drift(series, self.config)
        group = evidence.group("overtime_drift", rows,
                               "OT productive hours / (REG + OT productive hours), by work date and shift; first 56 days frozen, weekday-adjusted EWMA")
        return {"detected": any(s["detected"] for s in shifts.values()), "shifts": shifts,
                "data_complete": all(s["status"] in ("drift", "stable") for s in shifts.values()),
                "evidence_group_ids": [group]}

    def provider_readiness(self, unit, evidence):
        providers = {r["synthetic_provider_id"]: r for r in self.tables["providers"]}
        findings, followups, issues, supporting = [], [], [], []
        for assignment in self.tables["physician_assignments"]:
            if assignment["assignment_status"] != "confirmed" or not overlaps(
                    assignment["starts_at"], assignment["ends_at"], self.now, self.end):
                continue
            if not self._matches_unit("physician_scheduling", assignment["department_code"], assignment["facility_code"],
                                      unit, assignment["starts_at"], assignment["ends_at"]):
                continue
            left, right = max(self.now, instant(assignment["starts_at"])), min(self.end, instant(assignment["ends_at"]))
            supporting.append(assignment)
            canonical = self.identity.resolve("provider", "physician_scheduling", assignment["physician_code"], left, right)
            provider = providers.get(canonical)
            if provider is None:
                issues.append("Physician assignment identity cannot be resolved uniquely")
                continue
            supporting.append(provider)
            grants = [r for r in self.tables["privilege_grants"] if r["provider_key"] == provider["provider_key"]]
            supporting.extend(grants)
            mapped_grants = [(r, self._facility("provider", r["facility_code"], left, right)) for r in grants]
            if any(facility is None for _, facility in mapped_grants):
                issues.append("Assigned physician privilege facility identity cannot be verified")
                continue
            qualifying = [r for r, facility in mapped_grants if r["grant_status"] == "active"
                          and provider["status"] == "active" and r["service_code"] == assignment["service_code"]
                          and facility == unit["facility_id"]]
            if not grants:
                issues.append("No privilege records are known for an assigned physician")
                continue
            gaps = uncovered_intervals(left, right, [(r["valid_from"], r["valid_to"]) for r in qualifying])
            if gaps:
                findings.append({"assignment_record_id": assignment["record_id"], "provider_id": canonical,
                                 "assignment_start": assignment["starts_at"], "assignment_end": assignment["ends_at"],
                                 "uncovered_physician_hours": sum(duration(a, b) for a, b in gaps),
                                 "uncovered_intervals": [{"start": stamp(a), "end": stamp(b)} for a, b in gaps],
                                 "reason": "No active facility/service privilege covers the full assigned interval"})
            renewals = [r for r in self.tables["renewal_cases"] if r["provider_key"] == provider["provider_key"]]
            supporting.extend(renewals)
            for renewal in renewals:
                if renewal["workflow_status"] != "approved":
                    followups.append({"renewal_record_id": renewal["record_id"], "provider_id": canonical,
                                      "due_at": renewal["due_at"], "all_evaluated_assignments_covered": not bool(gaps),
                                      "note": "Pending renewal alone does not invalidate an existing grant"})
        unique_followups = {r["renewal_record_id"]: r for r in followups}
        # A case can affect multiple assignments: covered is true only if all evaluated ones are covered.
        for followup in followups:
            if not followup["all_evaluated_assignments_covered"]:
                unique_followups[followup["renewal_record_id"]] = followup
        group = evidence.group("provider_readiness", supporting,
                               "Assigned service interval minus union of active grants for the same provider, facility and service; renewal workflow does not revoke a grant")
        return {"findings": findings, "uncovered_physician_hours": sum(f["uncovered_physician_hours"] for f in findings),
                "renewal_followups": list(unique_followups.values()), "data_issues": sorted(set(issues)),
                "evidence_group_ids": [group]}

    def access_readiness(self, unit, evidence):
        findings, issues, supporting = [], [], []
        representatives = {r["representative_key"]: r for r in self.tables["vendor_representatives"]}
        for visit in self.tables["vendor_visits"]:
            if visit["visit_status"] != "scheduled" or not overlaps(
                    visit["scheduled_start"], visit["scheduled_end"], self.now, self.end):
                continue
            if not self._matches_unit("access", visit["destination_code"], visit["facility_code"],
                                      unit, visit["scheduled_start"], visit["scheduled_end"]):
                continue
            supporting.append(visit)
            rep = representatives.get(visit["representative_key"])
            if rep is None:
                issues.append("Visiting representative identity is missing")
                continue
            supporting.append(rep)
            policies = [r for r in self.tables["access_policy_requirements"] if r["required"]
                        and r["facility_code"] == visit["facility_code"] and r["policy_code"] == visit["policy_code"]
                        and overlaps(r["valid_from"], r["valid_to"], visit["scheduled_start"], visit["scheduled_end"])]
            credentials = [r for r in self.tables["vendor_credentials"] if r["representative_key"] == visit["representative_key"]
                           and r["facility_code"] == visit["facility_code"] and r["policy_code"] == visit["policy_code"]]
            dependencies = [r for r in self.tables["service_dependencies"] if r["visit_record_id"] == visit["record_id"]
                            and r["unit_id"] == unit["unit_id"]]
            supporting.extend(policies + credentials + dependencies)
            if not policies:
                issues.append("Visit credential requirements are not known")
                continue
            blocked = []
            for policy in policies:
                left = max(instant(visit["scheduled_start"]), instant(policy["valid_from"]))
                right = min(instant(visit["scheduled_end"]), instant(policy["valid_to"]))
                valid = [(r["valid_from"], r["valid_to"]) for r in credentials
                         if r["credential_code"] == policy["credential_code"] and r["verification_status"] == "approved"]
                if uncovered_intervals(left, right, valid):
                    blocked.append(policy["credential_code"])
            if blocked:
                findings.append({"visit_record_id": visit["record_id"], "representative_id": visit["representative_key"],
                                 "start": visit["scheduled_start"], "end": visit["scheduled_end"],
                                 "unapproved_requirements": sorted(set(blocked)),
                                 "importance": dependencies[0]["importance"] if dependencies else "not_established",
                                 "reason": "Required credential approval does not cover the scheduled visit",
                                 "equipment_outage_asserted": False})
        group = evidence.group("access_readiness", supporting,
                               "Required facility/policy credentials must be approved for each applicable instant of the visit; importance comes from a separate planning dependency")
        return {"findings": findings, "data_issues": sorted(set(issues)), "evidence_group_ids": [group]}

    def quality(self, unit, evidence):
        end_day = self.now.astimezone(self.zone).date() - timedelta(days=self.config.quality_reporting_lag_days)
        recent_start = end_day - timedelta(days=self.config.quality_window_days)
        baseline_start = recent_start - timedelta(days=self.config.quality_window_days)
        events = [r for r in self.tables["quality_events"] if r["event_type"] == "near_miss"
                  and r["workflow_status"] not in ("rejected", "void")
                  and baseline_start <= instant(r["occurred_at"]).astimezone(self.zone).date() < end_day
                  and self._matches_unit("quality", r["location_code"], r["facility_code"], unit, r["occurred_at"], r["occurred_at"]) ]
        activity = [r for r in self.tables["unit_activity"] if r["unit_id"] == unit["unit_id"]
                    and baseline_start <= date.fromisoformat(r["activity_date"]) < end_day]
        def patient_days(left, right):
            rows = [r for r in activity if left <= date.fromisoformat(r["activity_date"]) < right]
            selected = {r["activity_date"]: r["patient_days"] for r in rows}
            if len(selected) != self.config.quality_window_days or len(rows) != len(selected) or any(
                    value is None or value < 0 for value in selected.values()):
                return None
            return sum(selected.values())
        baseline_count = sum(instant(r["occurred_at"]).astimezone(self.zone).date() < recent_start for r in events)
        current_count = len(events) - baseline_count
        campaign = any(r["reporting_campaign"] for r in activity if date.fromisoformat(r["activity_date"]) >= recent_start)
        result = quality_review(baseline_count, current_count, patient_days(baseline_start, recent_start),
                                patient_days(recent_start, end_day), campaign, self.config)
        group = evidence.group("quality_reports", events + activity,
                               "Known non-rejected near-miss reports by occurrence date / aggregate patient-days * 1000; two complete 21-day windows with two-day reporting lag")
        result.update(baseline_window={"start": baseline_start.isoformat(), "end_exclusive": recent_start.isoformat()},
                      current_window={"start": recent_start.isoformat(), "end_exclusive": end_day.isoformat()},
                      reporting_lag_days=self.config.quality_reporting_lag_days,
                      reporting_campaign=campaign, evidence_group_ids=[group],
                      interpretation="Reported events are not a measure of true harm incidence; association does not establish causation")
        return result

    def analyze(self):
        summaries, packets = [], {}
        for unit in self.tables["units"]:
            evidence = Evidence()
            coverage = self.coverage(unit, evidence)
            drift = self.drift(unit, evidence)
            provider = self.provider_readiness(unit, evidence)
            access = self.access_readiness(unit, evidence)
            quality = self.quality(unit, evidence)
            mappings = [r for r in self.identity.used.values() if r["canonical_id"] in
                        (unit["unit_id"], unit["facility_id"]) or r["entity_type"] == "provider"
                        and any(f["provider_id"] == r["canonical_id"] for f in provider["findings"] + provider["renewal_followups"])]
            evidence.group("entity_relationships", mappings + [unit], "Verified, effective-dated source facility/unit/person crosswalks; no name matching")
            reasons, observations, reviews = [], [], []
            if coverage["uncovered_rn_hours"]:
                confirmed = coverage["uncovered_rn_hours"] - coverage["unverified_gap_rn_hours"]
                reasons.append("RN_COVERAGE_GAP" if confirmed else "RN_COVERAGE_UNVERIFIED")
                observations.append({"domain": "workforce", "fact": "The recorded plan does not establish required eligible RN coverage",
                                     "uncovered_rn_hours": coverage["uncovered_rn_hours"],
                                     "unverified_gap_rn_hours": coverage["unverified_gap_rn_hours"],
                                     "evidence_group_ids": coverage["evidence_group_ids"]})
                reviews.append({"id": "review-staffing", "owner_role": "Staffing manager", "task": "Review upcoming coverage and eligible staffing options"})
            if drift["detected"]:
                reasons.append("OVERTIME_DRIFT")
                observations.append({"domain": "workforce", "fact": "Overtime share has persistently exceeded the frozen baseline",
                                     "evidence_group_ids": drift["evidence_group_ids"]})
            for domain, metric, reason, owner, task in (
                ("provider", provider, "PROVIDER_ASSIGNMENT_EXPOSURE", "Medical staff coordinator", "Verify privilege status or arrange an authorized replacement"),
                ("access", access, "VENDOR_VISIT_NOT_READY", "Access coordinator", "Complete credential verification or arrange a compliant representative")):
                if metric["findings"]:
                    reasons.append(reason)
                    fact = "Assigned physician service has an uncovered privilege interval" if domain == "provider" else "A scheduled visit lacks required credential approval"
                    observations.append({"domain": domain, "fact": fact, "finding_count": len(metric["findings"]), "evidence_group_ids": metric["evidence_group_ids"]})
                    reviews.append({"id": "review-" + domain, "owner_role": owner, "task": task})
            if quality["review_required"]:
                reasons.append("QUALITY_REPORT_RATE_REVIEW")
                observations.append({"domain": "quality", "fact": "Near-miss report rate increased in the completed comparison window",
                                     "evidence_group_ids": quality["evidence_group_ids"]})
                reviews.append({"id": "review-quality", "owner_role": "Quality reviewer", "task": "Review reporting context and contributing factors without inferring causation"})
            issues = coverage["data_issues"] + provider["data_issues"] + access["data_issues"]
            if coverage["status"] == "insufficient_data":
                issues.append("RN coverage eligibility is not fully verified")
            if not drift["data_complete"]:
                issues.append("Overtime monitoring lacks a complete frozen baseline and observation period")
            if quality["status"] == "insufficient_denominator":
                issues.append("Quality trend has an insufficient denominator")
            priority = readiness_priority(
                rn_gap=coverage["uncovered_rn_hours"] > coverage["unverified_gap_rn_hours"],
                provider_exposure=bool(provider["findings"]), drift=drift["detected"],
                access=bool(access["findings"]), quality=quality["review_required"],
                issues=bool(issues), unverified_gap=bool(coverage["unverified_gap_rn_hours"]))
            investigation_id = unit["facility_id"] + ":" + unit["unit_id"] + ":readiness"
            summary = {"unit_id": unit["unit_id"], "facility_id": unit["facility_id"], "display_name": unit["display_name"],
                       "investigation_id": investigation_id if reasons or issues else None,
                       "priority": priority, "reason_codes": reasons,
                       "coverage_status": coverage["status"], "uncovered_rn_hours": coverage["uncovered_rn_hours"],
                       "provider_exposure_hours": provider["uncovered_physician_hours"],
                       "vendor_visits_not_ready": len(access["findings"]), "overtime_drift": drift["detected"],
                       "quality_report_review": quality["review_required"], "data_issues": sorted(set(issues)),
                       "status": "attention" if any(r != "RN_COVERAGE_UNVERIFIED" for r in reasons)
                       else "insufficient_data" if issues or coverage["unverified_gap_rn_hours"] else "no_current_finding"}
            summaries.append(summary)
            if not reasons and not issues:
                continue
            records = {key: evidence.records[key] for key in sorted(evidence.records)}
            packet = {"kind": "investigation_evidence", "schema_version": 1, "synthetic": True,
                      "engine_version": ENGINE_VERSION, "id": investigation_id,
                      "title": unit["display_name"] + " operational readiness", "summary": summary,
                      "as_of": stamp(self.now), "window": {"start": stamp(self.now), "end": stamp(self.end)},
                      "input_hash": self.input_hash, "rule_config": self.config.to_dict(),
                      "metrics": {"coverage": coverage, "overtime": drift, "provider": provider,
                                  "access": access, "quality": quality},
                      "observations": observations, "hypotheses": [{"text": "Overtime drift and the upcoming staffing gap may reflect sustained operational pressure",
                          "evidence_group_ids": ["workforce_coverage", "overtime_drift"], "confirmed_cause": False}] if drift["detected"] and coverage["uncovered_rn_hours"] > coverage["unverified_gap_rn_hours"] else [],
                      "unknowns": ["No causal relationship between staffing and quality reports has been established",
                                   "Live source-delivery freshness is not measured by this fixed replay archive"] + sorted(set(issues)),
                      "recommended_reviews": reviews, "evidence_groups": evidence.groups, "source_records": records,
                      "source_record_hashes": {key: content_hash(value) for key, value in records.items()},
                      "relationships": [{"crosswalk_record_id": r["record_id"], "entity_type": r["entity_type"],
                                         "source_namespace": r["source_namespace"], "source_entity_id": r["source_entity_id"],
                                         "source_facility_id": r.get("source_facility_id"),
                                         "facility_id": r.get("facility_id"), "canonical_id": r["canonical_id"]} for r in mappings]}
            packets[investigation_id] = packet
        relationship_issues = sorted(self.mapping_issues)
        expected_nonempty = {"employees", "employee_qualifications", "staffing_requirements", "workforce_assignments",
                             "providers", "privilege_grants", "physician_assignments", "vendor_representatives",
                             "vendor_credentials", "access_policy_requirements", "vendor_visits", "unit_activity",
                             "entity_crosswalk", "units", "facilities", "paid_time"}
        missing_inputs = sorted(name for name in expected_nonempty if not self.tables[name])
        global_issues = relationship_issues + ["No source rows are known for " + name for name in missing_inputs]
        data_quality = {"relationship_issues": relationship_issues, "missing_input_tables": missing_inputs,
                        "source_delivery_freshness": "not_measured", "completeness_limited": bool(global_issues)}
        if global_issues:
            for summary in summaries:
                if summary["status"] == "no_current_finding":
                    summary.update(status="insufficient_data", priority="review_required")
            for packet in packets.values():
                packet["unknowns"].extend(global_issues)
        for packet in packets.values():
            packet["data_quality"] = data_quality
        return {"as_of": stamp(self.now), "engine_version": ENGINE_VERSION, "input_hash": self.input_hash,
                "window": {"start": stamp(self.now), "end": stamp(self.end)},
                "data_quality": data_quality,
                "units": summaries, "investigations": packets}
