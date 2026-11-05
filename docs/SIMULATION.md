# Staffing intervention simulation

Pulse compares hypothetical changes against the exact investigation snapshot. It never writes to the source schedule. The simulator uses operational records, not evaluation labels or the precomputed hero summary.

## Experience

Open an investigation and select **Compare interventions**. Four alternatives show a computed residual gap and incremental coverage cost: internal reassignment, voluntary overtime, agency, and reassignment plus agency. The first complete future shift with a recorded deficit is the target. Coverage totals continue to include the full 72-hour investigation window, so gaps outside the targeted shift remain unresolved.

Select internal candidates, change agency slots/rate and explore hypothetical acceptance/availability. Calculate again after edits; the interface labels the old result until recalculation. Excluded employees show reasons and cannot be selected through the UI. The API independently validates submitted employees and rejects a hard-invalid plan atomically.

Results distinguish three quantities:

- **Modeled residual gap:** assumes all proposed capacity materializes.
- **Gap excluding unverified additional capacity:** counts verified eligible internal reassignments, excluding agency and voluntary overtime acceptance.
- **Gap under selected scenario assumptions:** applies the user's hypothetical availability/acceptance selections. These toggles do not verify real people or source-system consent.

All figures describe proposals. Even a feasible reassignment still requires human approval before implementation. A zero modeled nursing gap does not close physician, vendor or quality follow-ups.

## Constraints and selection

Eligibility requires active RN employment, a valid facility mapping, a verified license and required destination competency covering the entire shift, permitted destination codes, no approved absence, no overlapping work, and policy-compliant rest/work hours.

An internal move requires exactly one matching full source shift. It removes that assignment from a copy and adds the destination assignment. The engine checks donor coverage across the entire horizon after every proposed move, including all previously selected moves. Two individually possible moves can therefore be jointly rejected. Explicit invalid selections reject the entire submitted plan; no partial proposal is presented as accepted.

Default illustrative policy `demo-staffing-policy-1`: 12 hours minimum rest, at most 24 hours of work in any rolling 24 hours and 60 hours in any rolling 168 hours. Rolling calculations integrate the union of work intervals at critical boundaries. These are configurable engine policy inputs, not universal hospital policy or a payroll implementation.

Automatic selection is deterministic, ordered by employee ID, stopping when the targeted shift gap is covered or eligible capacity is exhausted. It is a bounded greedy comparison, not a globally optimal hospital staffing solver. The default seed discovers two Step-down donors without hardcoding their IDs. Rejected automatic candidates remain available for inspection.

Agency inputs represent at most three hypothetical qualified/onboarded slots at $110/hour, with 12 hours onboarding lead time. They are explicitly assumptions, not fabricated agency employee records. An insufficient lead time makes the plan infeasible. Voluntary overtime uses each eligible nurse's source base rate multiplied by 1.5; acceptance remains unverified even when assumed for a scenario.

## Cost arithmetic

Cost scope is identical across alternatives: the target department plus departments with eligible donor candidates, over the same 72 hours. Scheduled base pay includes known unavailable assignments; reassignment transfers already scheduled work without duplicating pay. Additional overtime/agency is incremental. Missing pay rates prevent a total-cost claim.

This is scheduled base-pay modeling, not payroll: no benefits, taxes, shift differentials, leave rules, minimum agency bookings or negotiated premiums are inferred. Rate overrides change the explicit agency assumption only. Currency is USD and monetary outputs round to cents.

Default seed-42 results:

| Proposal | Internal nurses | Agency slots | Modeled residual RN-hours | Gap excluding unverified extra capacity | Incremental coverage cost |
|---|---:|---:|---:|---:|---:|
| Reassignment | 2 | 0 | 12 | 12 | $0 |
| Voluntary overtime | 3 | 0 | 0 | 36 | $2,700 |
| Agency | 0 | 3 | 0 | 36 | $3,960 |
| Reassignment + agency | 2 | 1 | 0 | 12 | $1,320 |

Both moves preserve Step-down's required coverage. The $2,640 agency-only versus hybrid difference is a modeled reduction in incremental coverage cost if all proposed capacity materializes. It is not realized savings or measured hospital ROI.

## API and evidence

- `GET /api/investigations/{id}/simulation?as_of=...` returns target, baseline, versioned policy, candidate eligibility and four default comparisons.
- `POST /api/investigations/{id}/simulate?as_of=...` accepts `snapshot_id`, `kind`, optional `employee_ids`, optional `agency_slots`/`agency_hourly_rate_usd`, and hypothetical `overtime_accepted`/`assume_agency_available` booleans.
- A changed snapshot or duplicate employee returns 409; schema/rate/slot violations return 422; unknown investigation returns 404. The UI must refresh after a changed investigation.
- Successful calculation saves a content-addressed simulation artifact and a separate captured input artifact. The response includes both identities. Inputs include operational employees, qualifications, assignments, requirements, absences and mappings; evaluation fixtures are excluded. `GET /api/artifacts/{digest}` retrieves the saved objects after a restart.

The simulator reads one consistent source snapshot and derives its investigation digest from those same records before calculating. Policy, request, result, source-input identity and original investigation identity are preserved. No source database or assignment is mutated.

## Verification and limits

Run the complete Python suite, frontend tests, production build and `python scripts/smoke_workspace.py` as documented in the workspace guide. Constraint tests cover qualifications, partial expiry, absences, overlap, exact rest boundaries, rolling hours, joint donor shortage, atomic rejection, duplicate IDs, agency lead time, rate changes, missing pay, cost scope, stale snapshots, evidence persistence and unchanged source files.

The live HTTP-to-React flow now calculates a hybrid scenario and follows its saved evidence in addition to the Stage 3 investigation path. Automated component checks cover exclusions, edited results, explicit assumptions, mismatched snapshots, failures and cancellation. Browser appearance and native interactions remain unverified because browser preview was blocked by URL security policy.

Simulation does not predict patient outcomes, safety improvement, actual agency availability or completed operational remediation. Approval, tasks and generated AI explanations remain separate stages.

Stage 4 verification: 83 Python tests, 15 frontend component tests and 2 live HTTP-to-React tests pass; strict TypeScript and the production build pass. A single local service sample measured 4.90 seconds to assemble all comparisons and 2.31 seconds to calculate/persist a hybrid proposal, excluding HTTP serialization. The proposed subsecond simulation target is not met. Both cost scopes contain ICU and Step-down with $57,600 scheduled base pay across the horizon.
