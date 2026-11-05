# Implementation stages

Each stage is implemented, verified and submitted as a separate pull request. Work stops after submission. Starting the next stage requires explicit authorization; review approval does not automatically authorize further implementation.

| Stage | Deliverable | Acceptance gate |
|---|---|---|
| 1 — Foundation | Configuration, reproducible setup, read-only source repository, persistent evidence objects, foundation API | Clean preparation succeeds; as-of revisions are correct; storage and API checks pass |
| 2 — Intelligence | Drift metrics, temporal eligibility, cross-domain investigation and evidence packet | Hero facts reconcile; late data excluded; pending-valid renewal is handled correctly |
| 3 — Workspace | Overview, investigation timeline, source drawers and freshness states | A user can trace each displayed fact to supporting evidence |
| 4 — Simulation | Reassignment, overtime and agency comparisons with explicit constraints | Invalid candidates rejected; donor coverage preserved; residual gap and modeled costs reconcile |
| 5 — AI explanations | Grounded structured briefs, bounded questions, validation and deterministic fallback | Unsupported references rejected; timeouts complete with a labeled fallback |
| 6 — Action workflow | Approval, owners, tasks, persistence and audit history | Approved changes are explicit; unresolved issues remain open; restart preserves state |
| 7 — Verification and demo | Complete-flow checks, evaluation, measured timings, polish and rehearsal | Repeatable end-to-end demonstration and reviewable validation results |

Stage 1 supplies data access and evidence persistence. It does not expose investigation, simulation or approval endpoints. These appear only when their behavior has been implemented in the authorized stage.
