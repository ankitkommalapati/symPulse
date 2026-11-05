# Release verification and reproducible demonstration

Run `python scripts/verify_release.py` after the application dependencies are installed and `python -m pulse prepare` has validated the source archive. This command runs Python regressions, frontend component tests, the production build, a live HTTP-to-React check, the 30 component fixtures and three isolated API rehearsals. It writes [recorded results](validation/release_report.md) and the complete [JSON report](validation/release_report.json).

Generated logs are under ignored `data/verification/logs`. Existing plans, source files and evidence are not reset. The scenario evaluation and rehearsals use a freshly generated seed-42 archive and separate temporary workflow/evidence stores. The live application check also uses isolated stores and disables external model calls. No paid inference is performed by verification.

`--reports-only` skips the regression/build/live React commands and explicitly records those checks as **not run**. It is useful for CI's independent scenario/rehearsal step; it is not an alternative claim that the complete release command passed.

## How fixture results are produced

The existing fixture suite contains 30 cases across drift, provider, access, simulation and quality. Their preassigned labels have two tuning and four holdout cases per family. The inputs and labels were available during development: this is not a blind or representative hospital study.

The evaluator accepts family and input only. Explicit adapters construct corresponding operational rows or time series; production engine functions make the decision. Expected labels are compared afterward. The evaluator never appears in operational source ingestion, model evidence or investigation calculations. A dedicated read-only `GET /api/evaluation` exposes the saved report separately and indicates whether its data/engine hash matches the selected operational snapshot.

Family confusion counts apply to their primary decision: finding, feasibility or unexplained reporting review. Precision/recall remain undefined when their denominators are zero. The simulation holdout has no feasible positive case, so its precision and recall are undefined. Cases with unsupported secondary fields remain **partial**, rather than becoming fully matched by ignoring those fields. Results are not pooled into one accuracy percentage.

## Known gaps remain visible

The observed run has 26 fully matched cases, three partial cases and one mismatch, with no adapter errors.

- Drift stale feed, Access stale status and Quality late reports contain a live-delivery or missing-delivery expectation the archive engine does not measure. They remain partial.
- Access late arrival also expects no visit finding when its approval is unavailable at the selected clock. The operational engine reports that required approval is not established. This remains a failed fixture pending data-contract/label adjudication. It is not silently relabeled.
- Against those supplied labels, Access holdout precision is 50% (one true positive and one false positive), with recall 100% on one labeled positive. These tiny denominators do not establish field performance. The proposed 85% per-family precision goal is not met for this family.
- Other fixture families' denominators and outcomes are recorded in the report. They do not justify a blanket “100% accurate” claim.

`validation/known_gaps.json` records the exact disclosed mismatch. Any additional adapter error or undisclosed discrepancy fails the verification command. The known exception remains a failed case and keeps the all-fixtures gate outstanding; it does not count as a passing detection. Thresholds were not changed to improve this run's score.

## API rehearsal and performance

Three independent application instances execute readiness, analysis, investigation/evidence, four staffing comparisons, a saved hybrid simulation, fallback brief/cache, draft creation, explicit approval, simulated implementation, monitoring, refusal to close unfinished work, five task outcomes, simulated closure and restart recovery. Their core arithmetic must match across all three runs. The source ICU gap must remain 36 RN-hours after demo closure.

Timing samples use FastAPI's in-process HTTP test client, including response serialization and evidence persistence where applicable. They exclude browser layout, network transit and human decision time. Report medians and ranges; do not treat three measurements as a latency guarantee. The one-second simulation target remains unmet. Warm analysis and cached-brief budgets are reported against the samples, not assumed.

At the selected source snapshot, six reason codes form two investigations. This is an observed grouping count, not measured alert-noise reduction or improved precision. No manual-investigation baseline, human time savings, safety improvement or realized ROI was measured.

Valid content-addressed evidence objects are now reused without rewriting an identical file; corrupted content is still detected and repaired. This preserves evidence semantics while avoiding unnecessary fsync work on matching briefs and investigations.

## Fresh presentation sessions

`python -m pulse demo --port 8800` opens a new workflow/evidence session against the existing read-only source archive. The demo knowledge clock is fixed to November 5, 2026, 08:00 America/Chicago. Each launch uses a distinct ignored session directory, so normal saved plans are preserved. This provides repeatable rehearsal without destructive reset.

Use the [four-minute runbook](DEMO_RUNBOOK.md) and [submission material](SUBMISSION.md). A human presentation rehearsal, visual review, native dialog/download checks and a backup recording remain necessary. Automated API rehearsals are not represented as a completed browser presentation.

## Release position

The implemented prototype is reviewable with recorded gaps. The release report does not call every gate complete: fixture adjudication, visual browser review, real-model verification and the subsecond simulation target remain outstanding. No live provider access was supplied, and the earlier browser URL policy block prevented visual automation. These limits are shown in the app's Demo evidence page and submission guidance.
