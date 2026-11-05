# symplr Pulse — product and workflow research

Research date: **November 5, 2026**. Public-source diligence, not an internal product audit. Current product pages take precedence over older naming in brochures. Product marketing describes intended capabilities; it does not prove deployment status at a particular customer.

## 1. Decision supported by the research

Build Pulse as a **proposed application on the symplr Operations Platform**, focused on a cross-domain operational readiness decision. Avoid pitching a new platform, generic hospital dashboard, standalone staffing optimizer or automated clinical root-cause system.

The Operations Platform already positions itself around connecting workforce, provider, quality and spend workflows. Pulse fits that direction; connection itself is not a defensible differentiator. [Platform overview](https://www.symplr.com/healthcare-platform)

The current Quality page goes further than the original concept assumes: it describes a shared SaaS foundation spanning quality, safety, risk, provider performance and analytics, including emerging-risk identification and coordinated action. The narrow opportunity is to show a reproducible decision that also uses workforce availability, provider eligibility and vendor access in an overlapping future window. That opportunity is a **product hypothesis**, not proof that symplr lacks it. [symplr Quality](https://www.symplr.com/products/symplr-quality)

## 2. Portfolio map and relevance

| Product area | Relevant products / public positioning | Pulse decision |
|---|---|---|
| Workforce | Time and Scheduling integrates scheduling and timekeeping; symplr Scheduling, formerly Smart Square, is also presented as a scheduling offering | Core: staffing requirements, assignments, actual paid time, absence and qualifications |
| Provider data | Provider handles credentialing and privileging; Directory curates provider information; CVO supplies verification services; Payer serves health-plan workflows | Core: use Provider-like grants and renewal workflows; do not substitute directory listings for privileges |
| Quality and safety | Quality now presents Navigator, Analytics and Performance; older material also names Midas Care Management, DataVision and Statit; Safety has incident workflows | Core: use one quality-event feed, not duplicate events from every product |
| Physician scheduling | Physician Scheduling manages provider assignments and scheduling | Supporting core feed: required to join a physician's privilege interval to an actual assignment |
| Access | Access manages vendor representatives, facility requirements and visits | Core: representative-level compliance at a specific facility and visit |
| Contract | Contract centralizes agreements, renewal workflows and obligations | Defer; no essential dependency in the hero staffing decision |
| Spend | Value Analysis coordinates product requests, evidence and financial evaluation | Defer; not a general-purpose inventory or live equipment-maintenance system |
| Talent | Recruiting, Learning, Performance and related capabilities | Defer ingestion; prototype workforce qualification records provide the needed competency input |
| Communication | Clinical Communications supports care-team communication | Defer live notifications; local action plan is sufficient |
| Compliance and payer network | Compliance, Evidence Analysis and payer-oriented offerings address wider obligations | Defer; adds breadth without strengthening the two-day demonstration |

Portfolio categories and product discovery: [symplr homepage](https://www.symplr.com/), [About symplr](https://www.symplr.com/about), [Workforce](https://www.symplr.com/products/symplr-workforce/), [Provider](https://www.symplr.com/products/symplr-provider), [Learning](https://www.symplr.com/products/symplr-learning). Historical product names remain visible in the [login directory](https://www.symplr.com/login); this does not establish that similarly named products share a database.

## 3. Existing overlap that judges may recognize

**Staffing intelligence already exists.** Current Workforce material describes predictive demand, schedule balancing, open-shift management, enterprise visibility, premium-pay alerts and configurable pay rules. Scheduling advertises integration with HR, payroll, timekeeping and EMR systems. Do not claim Pulse invents predictive scheduling or eligible-staff matching. [Workforce](https://www.symplr.com/products/symplr-workforce/), [Scheduling](https://www.symplr.com/products/smart-square)

**Cross-product workflows already exist or have been publicly planned.** The 2025 CIO guide lists Provider–Directory and Provider–Quality Review connections as live. It labels Provider–Physician Scheduling as an early-adopter workflow planned for later in 2025, including handling credential-related scheduling gaps. That dated plan is not evidence of general availability in November 2026. [CIO guide, pp. 5–6 and 14](https://www.symplr.com/wp-content/uploads/2025/04/CIO-Guide-to-symplr-Products-2025.pdf)

**Explainability is already part of symplr's AI story.** The AI page describes traceable outputs, AWS Bedrock, scheduling, quality modeling, contract intelligence and evidence summarization. A sourced explanation alone is insufficient differentiation. Pulse should demonstrate temporal evidence joins, refusal of an unsafe intervention and transparent before/after arithmetic in the same investigation. [AI capabilities](https://www.symplr.com/platform/ai-in-healthcare)

**Workflow automation and root-cause review also exist.** Safety describes incident capture, root-cause analysis, tasks, routing and scheduled reports. Pulse should reuse that mental model instead of implying that operational follow-up is new. [Safety](https://www.symplr.com/products/symplr-safety)

**Supply-chain connections are also established.** Value Analysis describes Access credential validation and downstream Contract requests. Defer these domains rather than using them to inflate the prototype's apparent breadth. [Value Analysis](https://www.symplr.com/products/symplr-value-analysis)

Recommended differentiation: **“Pulse assembles a time-bounded, cross-product readiness investigation and compares feasible interventions before a leader approves a plan.”** This is a testable demonstration claim, not a market-wide novelty claim.

## 4. Workforce: how data is created, maintained and consumed

### Publicly evidenced workflow

Schedules and open-shift requests involve employees and managers; clockings and timecards record worked time; exceptions and approvals alter the lifecycle. The published mobile employee guide's indexed contents include time-off requests, shift trades, open-shift requests, clock corrections and timecard sign-off. Direct retrieval of that PDF failed during this research, so treat this as **indexed documentation evidence**, not a fully inspected manual. [Employee guide, version 2024.5.0](https://help.symplr.com/workforce/workforce_app/employee_guide_-_workforce_app__symplr_workforce__2024.5.0.pdf)

Publicly readable legacy help shows a configurable organizational hierarchy and local labels. A transaction can carry hours, date, pay code, job class, labor distribution and source information. These are useful field concepts, but an older customer-hosted help page cannot establish the current Time and Scheduling API. [Organization units](https://rvon1446.apihealthcare.com/apihc/tass/webportal/apihealthcare_rvon1446_live/help/configuration/organization_unit_card/organization_unit.htm), [Transaction fields](https://rvon1446.apihealthcare.com/APIHC/TASS/WebPortal/APIHealthcare_RVON1446_Live/help/employee/employee_actions/add_adjustment/general_tab.htm)

Assignment validation explicitly addresses active employment, valid licenses, position/station skills, education, overtime, schedule overlap, minimum buffers and unavailability. These are stronger foundations for a staffing simulation than matching only a job title. [Qualification rules](https://api.lvh.com/apihc/tass/webportal/apihealthcare/help/7993.htm)

### Implications for synthetic records

- Separate **planned assignment**, **absence notice** and **actual paid time**. A canceled shift must not produce worked hours.
- Store home unit and worked unit separately; floating changes the worked unit, not the employee's home department.
- Use source-local organization codes and a canonical crosswalk. Do not make every extract conveniently contain the same department ID.
- Use effective-dated RN license and ICU competency assertions. A course completion alone does not prove full ICU assignment readiness.
- Actual overtime is paid time classified by a demo rule, not “scheduled hours minus required hours.” Keep historical actuals separate from hypothetical future costs.
- Record local shift time and UTC instants. The history crosses the November 1 US daylight-saving change; night-shift duration must reflect elapsed time.
- Maintain source update and availability timestamps so a replay cannot see a cancellation before it was reported.

### Output evidence and gaps

Scheduling's product page documents system integration categories; it does not expose a source schema or export contract. A user's phone calendar export is not a hospital-wide staffing extract. The prototype will therefore use **designed JSONL report adapters**, with explicit mapping and freshness assumptions. No undocumented “symplr REST endpoint” should appear in the demo.

## 5. Provider and physician assignments: two different truths

### Publicly evidenced workflow

Provider describes applications, verification, credentialing, committee review, privileging, enrollment and recredentialing. It also describes expiration tracking, audit trails, configurable alerts and ad hoc spreadsheet/report output, plus downstream integrations. These establish lifecycle and reporting concepts, not a field-level public API. [Provider](https://www.symplr.com/products/symplr-provider)

Physician Scheduling describes monthly schedules, daily assignments, schedule changes and time tracking. Its public help documents date-filtered downloadable reports and selectable file types. That supports simulating an assignment report, but does not establish a specific JSON or CSV column layout. [Physician Scheduling](https://www.symplr.com/products/symplr-physician-scheduling), [Report wizard](https://www.spinfusion.com/SpinSchedules/assets/help/Content/Topics/Reports.htm)

### Implications for synthetic records

- License, facility privilege grant and renewal case are separate objects with separate dates.
- A renewal case marked pending does **not** revoke an existing grant. Eligibility is evaluated for the whole assignment interval.
- A grant that expires before the assigned service ends creates an actual temporal conflict; a grant expiring in two weeks creates follow-up urgency, not today's coverage loss.
- Provider privileges can be facility- and service-specific. A general provider “active” flag is insufficient.
- Join physician assignments to grants through an explicit source-ID mapping. Never join names or assume NPI alone contains privilege status.
- Use intentionally fake identifiers such as `SYN-PROV-001`, not randomly generated potentially real NPIs.
- Nurse assignment eligibility comes from workforce qualifications in this prototype; physician credentialing is a distinct domain.

The key demo distinction is one upcoming physician assignment crossing an expiring grant and a second pending renewal whose current grant remains valid. Pulse must flag the former and explain why the latter is not a coverage loss.

## 6. Quality and safety: events are reports, not ground truth of incidence

### Publicly evidenced workflow

Navigator documents configurable event capture, risk investigation, follow-up, peer review and reporting, with multi-EMR aggregation. Historical Midas material provides concrete event concepts: falls, equipment concerns, medication events and near misses, attributed to facilities, departments and other entities. [Navigator](https://www.symplr.com/products/symplr-quality/symplr-quality-navigator), [Midas brochure](https://www.symplr.com/wp-content/uploads/2024/08/Midas-Care-Management.pdf)

Safety separately describes dynamic forms, submission, task accountability, notifications and incident tracking. For Pulse, choose a Navigator-inspired event feed and use Safety as corroborating workflow research. Do not ingest two feeds as though their event populations are disjoint. [Safety](https://www.symplr.com/products/symplr-safety)

### Implications for synthetic records

- Separate `occurred_at`, `reported_at`, `available_at` and later revisions. Reports can arrive late.
- Distinguish near miss, no harm, harm and unsafe condition. A near miss has no actual-harm severity attached as though injury occurred.
- Deduplicate corrected records using stable event identity and version.
- Use a denominator when available: reports per 1,000 synthetic patient-days. Patient-days are a separate aggregate context feed, not something the event table automatically knows.
- Include a reporting-campaign control scenario. AHRQ evidence describes substantial increases in reporting after education and feedback; higher report counts can reflect a healthier reporting culture. [AHRQ study](https://www.ahrq.gov/sites/default/files/2025-05/fraser-dunagan-report.pdf)
- A report-rate change is an investigation prompt. It must not become a claimed probability of patient harm or a claim that overtime caused incidents.
- Keep patient and reporter identities out of this operational prototype. Synthetic structured summaries are enough.

## 7. Access: the person, facility policy and visit matter

### Publicly evidenced workflow

Access describes facility-specific credential requirements, checks and reminders, mobile/kiosk check-in, appointment management, compliance visibility and reporting. The real product already prevents noncompliant check-in under its described Smart Badge workflow; Pulse should flag readiness before the visit, not invent an access bypass. [Access](https://www.symplr.com/products/symplr-access)

A public health-system procedure illustrates representative access levels tied to work location, appointment context and maintenance visits. Those are customer policies, not universal symplr settings. We use the entity relationships as inspiration, without copying the policy or its requirements. [The Resource Group vendor procedure, updated June 2026](https://www.theresourcegroup.com/-/media/project/microsites/the-resource-group/documents/vendor-access-support-procedure.pdf)

### Implications for synthetic records

- A supplier organization and its visiting representative are different entities.
- Compliance is evaluated for the representative under the destination facility's applicable policy at visit time.
- A submitted document awaiting review is not an approved credential.
- A visit has planned start/end, destination unit, purpose and approval status; check-in/check-out are distinct actual events.
- Credential noncompliance creates an access-readiness issue, not proof of equipment downtime.
- If the demo says the visit is operationally important, a separate **demo service dependency** must supply that criticality. Do not imply Access stores equipment inventory, maintenance deadlines or replacement-device capacity.
- Show a credentialing coordinator task or an eligible substitute representative, never “approve expired credentials.”

The generator includes a synthetic scheduled service visit linked to the ICU. Its criticality is explicitly owned by a local planning-context feed.

## 8. Deferred domains and commercial direction

Contract includes agreement repositories, versions, renewal alerts, obligations and ERP-related spend visibility. A future Pulse investigation could join staffing-service agreements to available agency capacity, but doing so credibly requires contract terms and supplier availability that the MVP does not possess. [Contract](https://www.symplr.com/products/symplr-contract/)

Value Analysis includes new-product requests, review workflows, evidence and price comparisons. It is a plausible later supply-chain use case, but it should not be presented as a continuous bedside inventory stream. [Value Analysis](https://www.symplr.com/products/symplr-value-analysis)

Learning could later contribute effective-dated education completion and competency evidence. For the MVP these are synthetic workforce qualification assertions with explicit provenance. [Learning](https://www.symplr.com/products/symplr-learning)

Commercial hypothesis: sell an optional cross-product readiness application to existing multi-product health-system customers, with a bounded first use case, mapped customer identifiers and measured investigation time. Buyer willingness, pricing, actual data access and overlap with internal roadmaps remain unvalidated.

## 9. Evidence register and confidence

| ID | Primary source | What it supports | Limit |
|---|---|---|---|
| S01 | [Platform](https://www.symplr.com/healthcare-platform) | Cross-domain platform positioning | Not an integration contract |
| S02 | [Current Quality](https://www.symplr.com/products/symplr-quality) | Current suite structure and substantial concept overlap | Marketing, not a customer deployment inventory |
| S03 | [Workforce](https://www.symplr.com/products/symplr-workforce/) | Scheduling/timekeeping, rules, alerts | No field-level schema |
| S04 | [Scheduling](https://www.symplr.com/products/smart-square) | Smart Square naming and integration categories | Does not imply all Workforce versions are identical |
| S05 | [Provider](https://www.symplr.com/products/symplr-provider) | Credential lifecycle and reporting | No private enums or export spec |
| S06 | [Physician Scheduling](https://www.symplr.com/products/symplr-physician-scheduling) | Assignment ownership | Separate from privileges |
| S07 | [Scheduling reports](https://www.spinfusion.com/SpinSchedules/assets/help/Content/Topics/Reports.htm) | Date-filtered downloads and report types | Older help; schemas unavailable |
| S08 | [Navigator](https://www.symplr.com/products/symplr-quality/symplr-quality-navigator) | Event/review workflow and aggregation | Does not establish API or migration equivalence |
| S09 | [Midas brochure](https://www.symplr.com/wp-content/uploads/2024/08/Midas-Care-Management.pdf) | Historical event concepts and EMR linking | Historical product material |
| S10 | [Safety](https://www.symplr.com/products/symplr-safety) | Incident/task/report lifecycle | Alternative feed family, not extra unique events |
| S11 | [Access](https://www.symplr.com/products/symplr-access) | Representative compliance, policies, visits | No public raw export layout |
| S12 | [Vendor procedure](https://www.theresourcegroup.com/-/media/project/microsites/the-resource-group/documents/vendor-access-support-procedure.pdf) | Customer operational context | One customer's policy; not copied |
| S13 | [CIO guide](https://www.symplr.com/wp-content/uploads/2025/04/CIO-Guide-to-symplr-Products-2025.pdf) | Dated cross-product workflow statuses | Planned 2025 is not verified 2026 GA |
| S14 | [AI](https://www.symplr.com/platform/ai-in-healthcare) | Existing AI portfolio and Bedrock positioning | Not proof the user's account is provisioned |
| S15 | [Qualification rules](https://api.lvh.com/apihc/tass/webportal/apihealthcare/help/7993.htm) | Eligibility constraints | Legacy, customer-hosted product help |
| S16 | [Organization hierarchy](https://rvon1446.apihealthcare.com/apihc/tass/webportal/apihealthcare_rvon1446_live/help/configuration/organization_unit_card/organization_unit.htm) | Configurable unit hierarchy | Not a modern API model |
| S17 | [Transaction fields](https://rvon1446.apihealthcare.com/APIHC/TASS/WebPortal/APIHealthcare_RVON1446_Live/help/employee/employee_actions/add_adjustment/general_tab.htm) | Hours, pay code, labor distribution concepts | Legacy UI field meanings |
| S18 | [Employee manual](https://help.symplr.com/workforce/workforce_app/employee_guide_-_workforce_app__symplr_workforce__2024.5.0.pdf) | Indexed mobile workflow topics | Direct document inaccessible |
| S19 | [2025 configuration manual](https://help.symplr.com/workforce/workforce_app/configuration_guide_-_workforce_app__symplr_workforce__2025.1.0.pdf) | Indexed configurable pay-code/job-class topics | Open redirected to secure/error page; not fully reviewed |
| S20 | [Contract](https://www.symplr.com/products/symplr-contract/) | Deferred agreement/obligation domain | No license pricing or private schema inferred |
| S21 | [Value Analysis](https://www.symplr.com/products/symplr-value-analysis) | Deferred requests/evidence workflow | Not inventory or maintenance telemetry |
| S22 | [Learning](https://www.symplr.com/products/symplr-learning) | Deferred education domain | Course completion not full competency |
| S23 | [Technology/security](https://www.symplr.com/platform/technology-security) | Product security context | Pulse inherits no certification |
| S24 | [Operational transformation guide](https://www.symplr.com/wp-content/uploads/2025/09/eBook-TransformingHeathcareOperations-090625.pdf) | Platform business rationale | Not independent impact validation |
| S25 | [AHRQ reporting study](https://www.ahrq.gov/sites/default/files/2025-05/fraser-dunagan-report.pdf) | Reporting-culture confounding | Not a model calibration dataset |
| S26 | [NIST EWMA](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm) | Explainable sequential monitoring method | Hospital thresholds require validation |
| S27 | [UAMS quick start](https://supplychain.uams.edu/wp-content/uploads/sites/11/2024/06/Symplr-Physician-Clinician-Quick-Start-Guide.pdf) | Customer product-request handoffs | Deferred domain, not an export specification |

### Research limits that change implementation

Public material did **not** establish the private table layouts, APIs, access entitlements, event delivery semantics, latency SLAs or universal ID conventions of the five required feeds. The research therefore supports **workflow fidelity**, not byte-for-byte reproduction. Every schema, source code, enum, cadence, population size and statistical distribution in this repository is a documented prototype design choice unless explicitly attributed above.

The supplied Medium article could not be retrieved. It was not used as evidence. No authenticated customer application, employee record or confidential symplr document was accessed. The repository metadata confirmed an empty public repository; the generated data is wholly fictional.

Before a real pilot, validate with a product owner: exact SKU/version, approved data access, export samples, field semantics, facility/employee crosswalk, update/delete behavior, latency, retention, restricted quality fields, permitted LLM deployment and internal roadmap overlap. This list is a future integration dependency, not a prerequisite for the synthetic hackathon build.
