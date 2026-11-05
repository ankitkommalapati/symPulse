# Operational intelligence

Pulse assembles operational readiness investigations from the source records known at a selected time. The engine uses transparent rules and arithmetic. It does not call a language model, execute staffing changes or infer clinical outcomes.

## What the engine calculates

| Domain | Calculation | Interpretation |
|---|---|---|
| Workforce coverage | Required RN count minus distinct eligible assigned RNs, integrated over the next 72 hours | Upcoming gap or eligibility uncertainty |
| Workforce drift | Actual paid overtime share by unit, work date and day/night shift; weekday-adjusted EWMA | Sustained departure from a frozen baseline |
| Provider readiness | Scheduled service interval minus the union of valid grants for the same provider, facility and service | Uncovered physician-hours; pending renewal alone does not invalidate a grant |
| Vendor access | Required facility/policy approvals covering each scheduled visit | Visit readiness concern; does not imply equipment downtime |
| Quality reports | Known near-miss reports per 1,000 aggregate patient-days across complete comparison windows | Reporting trend requiring context; does not prove causation or true harm incidence |

Every source table is read in a consistent, read-only transaction. Availability filtering and version/tombstone selection happen before analysis. Evaluation labels, hero summaries and expected outcomes are never inputs to the engine.

## Time and eligibility

The default knowledge clock is November 5, 2026, 08:00 America/Chicago. The action window ends exactly 72 elapsed hours later. Intervals are half-open `[start, end)`. Known future assignments are included; records that arrive after the selected clock are excluded.

RN coverage checks employment, role, facility mapping, required license/competency validity, approved unavailability and conflicting assignments. Integration uses 15-minute boundaries plus exact change times so partial absences and mid-shift expiry do not become whole-shift approximations. Distinct employees are counted once. Missing qualification evidence makes the affected gap unverified rather than safe. Conflicting requirements or an incomplete requirement window are explicitly reported.

The reported uncovered total includes an explicitly separated `unverified_gap_rn_hours` portion. The difference is the minimum deficit established by the known plan. For example, removing all qualification evidence does not erase the three already known absences: those still establish 36 uncovered RN-hours, while the remaining uncertainty is labeled separately.

Provider grant validity is evaluated over the relevant assignment interval, clipped to the action window. Multiple contiguous active grants can cover one assignment. Expiry exactly at assignment end covers the assignment. A grant for another service or a verified different facility does not cover it; an unresolved facility identity produces a data issue instead of an asserted authorization failure.

Facility, unit and provider identities use effective-dated crosswalks. Names are never used to join entities. Ambiguous, missing or expired mappings appear in the result's data-quality information. Missing essential source populations prevent a reassuring “no current finding” state.

## Drift configuration

The default baseline begins August 7, 2026, with 56 completed dates. Monitoring extends to at most 90 completed dates from that anchor. A missing baseline date is not silently replaced by shifting the baseline forward or filling a zero.

Day and night shifts are monitored separately. Baseline weekday means remove the stable weekly pattern. Residual standard deviation has a 0.003 share floor; EWMA uses lambda 0.25 and the finite-time variance adjustment. A sustained drift requires three consecutive upper-limit breaches, each with at least a 0.015 absolute share increase. Individual unusual points are also marked in the series but are not automatically called sustained drift.

The first breach field is a **work date found within this replay**, not a measured real-world alert timestamp or evidence of earlier discovery than another product. The baseline is never fitted to the deteriorating monitoring tail.

These are versioned synthetic-demo parameters, not clinically calibrated thresholds. The packet records the engine version and complete rule configuration.

## Quality interpretation

The current 21-day comparison window excludes the two most recent local calendar dates to reduce known reporting-delay effects. The immediately preceding 21 dates form the baseline. This lag does not guarantee complete reporting; late records remain excluded until their actual availability time.

The initial review rule requires at least five reports in each window and a rate ratio of at least 1.25. Missing/zero denominators prevent a rate claim. Sparse counts produce an insufficient-volume status, not a hospital risk alert. Known reporting campaigns suppress the unexplained-rate interpretation and remain visible as reporting context. Rejected or void reports do not enter the numerator, and source revisions are deduplicated before counting.

A quality-only rate review is informational. Multiple related domain findings may support a higher-priority operational investigation; report counts are never interpreted as proof that staffing caused harm.

## Findings and priority

Pulse groups findings by canonical facility, unit and readiness family within the selected action window. Historical overtime and quality patterns supply context for that unit; future assignments and visits supply time-bounded dependencies. This is an explicit contextual join, not a causal discovery claim.

- High: a confirmed RN coverage deficit or physician eligibility exposure, plus another readiness concern.
- Medium: another actionable operational finding or sustained workforce drift.
- Informational: a quality-report rate review on its own.
- Review required: insufficient data prevents a complete assessment.
- No current finding: no configured rule fires; this does not assert that a department is safe.

The fixed archive cannot measure live source-delivery freshness. The API states `source_delivery_freshness: not_measured` rather than deriving a false freshness claim from the age of a valid unchanged record.

## Investigation API

| Route | Output |
|---|---|
| `GET /api/intelligence/units?as_of=...` | All unit summaries, horizon, engine version, input hash and data-quality information |
| `GET /api/investigations?as_of=...` | Summaries requiring attention or review |
| `GET /api/investigations/{id}?as_of=...` | Complete versioned packet, saved snapshot identity and artifact URL |
| `GET /api/artifacts/{digest}` | The exact saved source or investigation artifact |

The ICU investigation ID is `FAC-01:ICU:readiness`. Unknown IDs return 404; malformed or timezone-free clocks return 422. Source/storage failures return 503.

A packet includes computed metrics, observations, explicitly unconfirmed hypotheses, unknowns, suggested review owners, exact source revisions, record payload hashes, aggregate formulas, source membership and crosswalk paths. A full-input hash identifies the known operational snapshot. The evidence store persists the full packet so later changes do not rewrite earlier findings.

Repeated requests use a bounded cache keyed by normalized clock and source database/WAL generation. Changing source data or clock recomputes the analysis. No cache result is used as an evaluation label or source fact.

## Seed-42 findings

At the default clock:

- The ICU has **36 uncovered RN-hours**, all on November 6's day shift: eight required, five eligible and available, three known absences.
- Both ICU shift classes show sustained overtime drift. Comparison units do not show workforce drift or RN deficits.
- The highlighted physician assignment has **six uncovered physician-hours**. Across all overlapping assignments in the entire 72-hour window, the same expiring grant leaves **19 physician-hours** exposed. These are never added to nurse-hours.
- The second pending renewal retains valid assignment coverage.
- One ICU vendor visit has a required facility orientation approval pending review. Visit importance comes from the separate planning dependency.
- The ICU comparison uses **10 versus 17** known near-miss reports and **426 versus 423** patient-days, approximately **23.47 versus 40.19** reports per 1,000 patient-days. This is a reporting review, not an estimated increase in actual harm.
- Step-down also meets the configured quality-report rate review rule and is listed as informational; it has no detected workforce drift or RN deficit. The engine does not hide this background-data result to manufacture a single alert.

## Verification

Run `python -m unittest discover -s tests -v`, then `python scripts/smoke_api.py` after preparation. Tests exercise the hero integration case and independent analytical boundaries, including stable seasonality, zero variance, one-point spikes, missing baseline data, contiguous grants, wrong service, partial absences, mid-shift qualifications, reporting campaigns, missing denominators, mapping ambiguity, replay integrity and preserved evidence after source updates.

These checks establish deterministic behavior on synthetic inputs. They are not a measured real-world precision, clinical-risk or business-ROI study. Staffing intervention comparison, AI wording and approval execution belong to their separately authorized stages.

### Stage 2 verification results

| Check | Result |
|---|---|
| Complete regression suite | 63 tests passed, including the 27 foundation tests |
| Live HTTP flow | Investigation listing, computed ICU gap and saved investigation artifact passed |
| Evidence integrity | Every included observation group resolves to captured source revisions; record and aggregate input hashes reconcile |
| Source changes | Recalculation produces a new snapshot; the earlier stored investigation retains its original metrics |
| Default source analysis | One high-priority ICU investigation and one informational Step-down reporting review |
| Single-process timing sample | Approximately 0.97 seconds for cold analysis of all six units; cached analysis lookup approximately 0.0001 seconds |

The timing sample measures the analysis service, excluding HTTP serialization and evidence-file persistence. It is not an end-user latency guarantee or a hospital impact measurement.
