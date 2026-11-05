# Synthetic data specification and supplied starter

Version `pulse-demo-1.0` • seed `42` • wholly fictional • not a private symplr schema.

The public workflow evidence and its limitations are in [RESEARCH.md](RESEARCH.md). This document specifies **our data design**, including field names, enums, timing, scale and test cases. Those choices are not claims about symplr's implementation.

## 1. What is supplied

Run `python3 scripts/generate_data.py`, followed by `python3 scripts/validate_data.py` from the project root. The starter creates:

- A source-shaped JSONL file per table and matching SQLite tables.
- Ninety completed historical dates, August 7–November 4, plus seven schedule dates, November 5–11, 2026. Actual completed night shifts can finish on November 5 before the clock.
- One fictional hospital, six units, 192 nurses, 18 physicians, eight supplier companies and 16 vendor representatives.
- 21 tables and, for seed 42, **30,316 source record versions**.
- Source-local organization and provider identifiers with explicit crosswalks.
- Three known absences on the ICU's November 6 day shift, two qualified donor nurses, a mid-assignment privilege expiry, a pending-valid renewal and an unapproved required vendor credential.
- Sparse quality events, reporting delay and a handful of revised records.
- A generated field/type dictionary, counts, hashes, a computed hero summary and **30 separate labeled component fixtures**.

This is a **replay archive**. Some late reports become available after the frozen clock; they deliberately exist in the files so as-of filtering can be tested. An application must filter them out before presenting the November 5 investigation. The package is not an export allegedly collected from actual source products.

## 2. Domain ownership and fidelity

| Domain / logical feed | Synthetic record family | Public grounding | Designed assumptions |
|---|---|---|---|
| Workforce | employees, qualifications, requirements, assignments, unavailability, paid time | Scheduling, timekeeping and eligibility workflow concepts | Exact fields, pay codes, staffing counts, rates, rotation and classifications |
| Provider | providers, privilege grants, renewal cases | Credential/privilege/renewal lifecycle | Codes, grant intervals, statuses, case contents |
| Physician Scheduling | physician assignments | Assignment/report workflow | Exact report shape and person mapping |
| Quality | quality events and revisions | Near misses, event reporting and follow-up | Sparse event distribution, reporting lags, narrative and enums |
| Access | suppliers, representatives, credentials, policies, visits | Representative/facility compliance and visit workflow | Requirement list, policy code, visit purpose and statuses |
| Demo planning context | facilities, units, crosswalks, unit activity, service dependencies | Additional context needed by our decision | Entire feed; not represented as an export from a symplr product |

Four core operational domains require **five logical product feeds** when physician assignments are included. Planning context is additional synthetic input, not a sixth claimed symplr integration.

## 3. Common record envelope

Every source-shaped row contains:

| Field | Meaning / rule |
|---|---|
| `record_id` | Globally namespaced `source:table:source_id`; stable across revisions |
| `source_system` | `workforce`, `provider`, `physician_scheduling`, `quality`, `access`, `planning_context` |
| `source_record_id` | Identifier inside that source family |
| `record_version` | Positive integer; unique with `record_id` |
| `source_updated_at` | When the source revision became available for extraction in this scenario |
| `available_at` | When Pulse may know this revision; must not precede source update |
| `is_deleted` | Tombstone capability; all main-pack rows initially false |
| `synthetic` | Always true |

Payload uses source-specific names: Workforce's `organization_code`, Quality's `location_code`, Access's `destination_code`. The normalized application layer may add canonical IDs after mapping, while preserving the source payload. There is no fabricated official symplr API route or private source column name.

Recommended extension for actual adapters: `extract_id`, `ingested_at`, `schema_version`, payload checksum and raw-file hash. Record update time is not a feed heartbeat; a valid unchanged grant can be old without the integration being stale. Track successful extraction separately.

## 4. Table contracts

For exact generated keys and types, open `data/generated/data_dictionary.json`. Lists are JSON arrays in JSONL and serialized JSON text in SQLite; booleans become SQLite integers. NULL remains NULL.

| Table | Grain | Important keys and invariants |
|---|---|---|
| `facilities` | One canonical hospital | `facility_id`, display name, IANA timezone |
| `units` | One canonical department | `unit_id`, `facility_id`, illustrative requirement; not inferred from patient ratio |
| `entity_crosswalk` | Source identity to canonical identity interval | entity type, namespace, source ID, canonical ID; unit mapping scoped by source facility |
| `employees` | Workforce employee | employee number, home organization, role, active state, FTE, base rate, synthetic rotation cohort |
| `employee_qualifications` | Employee qualification interval | license/ICU competency, verification state, effective interval, facility and eligible units |
| `staffing_requirements` | Unit × shift × role | start/end, requirement count, job class; interval-based needs |
| `workforce_assignments` | One employee assignment | employee, actual assigned unit, home unit, interval, requirement record; absence evaluated separately |
| `unavailability` | Approved absence interval | employee, start/end, notice availability, associated assignment; no medical reason details |
| `paid_time` | Assignment × classified pay-code component | regular/OT hours; productive components sum to actual elapsed hours |
| `unit_activity` | Unit × completed date | synthetic patient-days and reporting-campaign context; no individual patient data |
| `providers` | Provider source master | source provider key, intentionally fake canonical ID, specialty and home context |
| `privilege_grants` | Provider × facility × service grant | status and valid interval; current `active` text cannot override interval expiry |
| `renewal_cases` | Grant renewal workflow | pending review, submitted/due/approval timestamps; pending does not mean grant revoked |
| `physician_assignments` | Physician × assigned interval/service | scheduling identity, facility, department, service, starts/ends |
| `quality_events` | Report identity/version | occurrence/report/availability time, type, actual harm, workflow status and structured-safe narrative |
| `vendors` | Supplier company | company identity; not interchangeable with representative identity |
| `vendor_representatives` | Visiting individual | representative key linked to company |
| `vendor_credentials` | Representative × facility/policy × requirement | verification status, effective interval; pending is not approved |
| `access_policy_requirements` | Facility/policy required credential | applicable interval and required flag |
| `vendor_visits` | Scheduled representative visit | destination, interval, purpose, policy; no invented check-in for a future visit |
| `service_dependencies` | Local plan dependency | visit ID, canonical unit, importance; explicitly not Access equipment telemetry |

Canonical person mapping is explicit between Scheduling's `DOC-001` and Provider's `P001` via `SYN-PROV-001`. Employee IDs use `SYN-RN-*`; no NPI, SSN, license number, email or real person is copied. Vendor names are intentionally generic.

## 5. Normalization and as-of semantics

Use this ordering for every source table:

1. Filter revisions to `available_at <= requested_as_of`.
2. Select the greatest version for each `record_id` from the remaining rows.
3. Exclude rows whose selected version is a tombstone.
4. Resolve identity using the mapping valid for the relevant event/assignment interval.
5. Apply event, service or effective interval logic for the requested question.

Selecting the latest version **before** the availability filter leaks future corrections. Filtering only the event date loses legitimate known future schedules and can include unknown late reports.

Example SQLite pattern:

```sql
WITH known AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY record_id ORDER BY record_version DESC
  ) AS revision_rank
  FROM quality_events
  WHERE available_at <= :as_of
)
SELECT * FROM known
WHERE revision_rank = 1 AND is_deleted = 0;
```

Generated UTC strings are normalized consistently, so lexical comparison is valid within the supplied files. External adapters must parse/normalize timezone values before relying on string order.

All work/service intervals are half-open `[start, end)`. A grant ending exactly at shift end covers the shift; one ending at shift start does not. Validity must cover every instant of the assignment. The prototype's datetime `valid_to` is an exclusive instant, not an ambiguous date-only expiry. A real adapter needs the product/customer's expiry semantics.

The hospital uses America/Chicago. The October 31 night shift crosses the November 1 daylight-saving fallback and lasts **13 elapsed hours**. Never subtract naive local datetimes or assume every night shift lasts 12 hours.

## 6. Generation mechanics and limits

### Baseline and drift

The first 56 dates have approximately 6% synthetic source-classified overtime share, with small random variation. ICU paid-time shares drift upward thereafter; other departments remain broadly stable. This is a controllable analytical signal, not a measured population distribution. Records are generated from assignments, so totals reconcile.

Overtime components are **preclassified source inputs**, not output of a legal payroll implementation. A later payroll engine must implement actual customer pay rules. The generator does not claim that fractional overtime on every assignment follows a real hospital's weekly classification policy.

### Staffing feasibility

There are eight scheduled nurses per unit/shift in the simple rotation. ICU requires eight; other units require six, creating explicit donor capacity. This is a transparent toy staffing policy and intentionally overprovides donor capacity; it is not representative staffing calibration.

All staff have an effective license assertion. ICU staff and a small subset of Step-down nurses have verified ICU competency. For the target shift, `SYN-RN-041` and `SYN-RN-042` are qualified donors; other apparently available donor staff include unqualified controls. Main-pack history does not attempt to model every illness, swap, skill mix, break or union rule. Add these only when needed by the decision, and preserve the simple hero math.

### Provider and Access

One ICU physician grant expires at 13:00 hospital time during the November 6 day shift, leaving six physician-hours exposed. Another pending renewal remains valid until November 20. The upcoming vendor representative has one required credential pending review, while a second representative is fully approved. No actual grant renewal or credential approval is manufactured after the clock.

### Quality

Quality events are intentionally sparse; the final ICU period has increased near-miss reporting probability. Occurrence-to-report delay ranges from hours to two days; revisions arrive later. Main-pack events are all near misses with no actual harm. This keeps the hero focused; the component suite adds reporting-campaign and denominator controls. The event stream does not establish real adverse-event incidence or causal relationships with workforce measures.

### Freshness assumptions for the eventual application

Proposed demo adapter checks: workforce extract within 30 minutes; physician assignments within one hour; Provider and Access status snapshots within four hours; quality export within 24 hours, with a separate completeness lag. These are configurable prototype assumptions, **not symplr SLAs**. Implement `last_successful_extract_at` in a feed-health store. The current generator supplies replay timestamps but does not run connectors or manufacture connector uptime.

## 7. Challenge fixtures and evaluation isolation

`evaluation_cases.json` has 30 component fixtures, six per family:

| Family | Cases |
|---|---|
| Drift | sudden spike, gradual drift, stable, weekday seasonality, zero variance, stale feed |
| Provider | mid-shift expiry, pending-valid, already expired, exact-end boundary, wrong facility, renewed-effective grant |
| Access | missing credential, pending review, approved, other-unit distractor, future arrival, stale snapshot |
| Simulation | feasible pair, missing competency, joint donor shortage, overlap, insufficient rest, absence |
| Quality | unexplained rate rise, stable rate, reporting campaign, denominator growth, missing denominator, late reports |

Each case has `input`, `expected`, `family` and a predetermined `tune`/`holdout` tag. Holdout labels are present for the evaluator; keep the entire file outside the application's evidence/model context. These are hand-designed challenge inputs, not independent empirical evidence. “Renewed effective” contains the resulting valid grant interval; do not infer validity from its case name.

Evaluation must define a family-specific result contract. Drift/provider/access use findings; simulation uses feasibility; quality uses review/confounder decisions. Report each family separately, with positive/negative counts. No detector is implemented or scored by this package.

Suggested additional integration mutations after P0: revoke one qualification before the shift; add a donor unit absence; remove a mapping; tombstone a quality event; replace a credential status in a later revision; add a model prompt-injection narrative. Store mutated archives separately with their expected outcomes rather than corrupting the baseline hero.

## 8. Validation actually performed

`validate_data.py` checks file hashes/counts against the manifest and SQLite, unique source versions, synthetic markers, timestamp ordering, employee/assignment mappings, no baseline schedule overlaps, paid-time reconciliation, DST duration, donor qualifications/rest/hours and combined donor coverage, hero gap arithmetic, physician mapping/expiry, quality chronology/revisions/late arrivals and Access references.

It writes `validation_report.json`. Passing these checks establishes data integrity and fixture arithmetic. It does **not** validate the unbuilt application, prove detector precision, score LLM quality or demonstrate real clinical/financial benefit.

Reproducibility: rerun with seed 42 and compare JSONL hashes. Use a different output directory for perturbation seeds: `python3 scripts/generate_data.py --seed 43 --output /tmp/pulse-seed-43`. The seed changes background data; it deliberately preserves the principal hero constraints.

## 9. Data growth after the hackathon

Before claiming close statistical resemblance to production, obtain approved aggregate ranges and redacted export examples from each product owner. Validate grain, enum meaning, update cadence, missingness, effective dates, corrections and crosswalk stability. Then calibrate distributions and noise. Until that happens, describe the supplied data as **workflow-informed and internally consistent**, not validated replicas of actual symplr exports.
