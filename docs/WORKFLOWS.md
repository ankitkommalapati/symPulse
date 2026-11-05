# Demo response plans and follow-through

A calculated staffing scenario can become a durable proposal with exact assignments, assumptions, owners, due times and an audit trail. The workflow records a demo decision. It does not reserve staff, submit real vendor/provider changes or modify the source schedule.

## Review flow

1. Calculate a feasible or explicitly conditional scenario in **Compare interventions** and select **Save draft plan**.
2. Review its exact internal assignments, hypothetical agency slots, modeled residual gap and original evidence in **Response plans**. Follow-up tasks are seeded from the actual investigation plus agency/overtime dependencies and any residual staffing gap.
3. Edit task owners and due times in draft. Owners are explicit demo roles; dates are entered in UTC and displayed in hospital time after submission. Initial staffing/provider/vendor deadlines use the relevant upcoming commitment; other review deadlines use the investigation horizon.
4. Submit for review. The proposal and task details become read-only.
5. Select **Approve demo plan** after explicitly acknowledging the demo action. Approval records the seeded reviewer, time, proposal hash, simulation and investigation snapshot. Tasks remain open.
6. Record simulated implementation, then start monitoring. Each step is explicit and separately audited.
7. Enter an outcome note, acknowledge the demo action and record each task's simulated completion. Every task receives a persisted, explicitly simulated outcome artifact.
8. Close only when all tasks have valid matching outcome evidence and the proposed plan has zero modeled residual staffing gap. Closure requires its own outcome note and acknowledgement. The screen says **Closed · simulated outcome**, and the source investigation remains unchanged.

A proposal with a residual gap cannot close by simply checking off its tasks. Calculate a revised scenario and create a new plan. Dismiss an unwanted proposal with a recorded reason of at least eight characters; dismissal does not complete tasks or resolve source findings. Closed/dismissed proposals cannot be reopened or edited. A stale proposal can be dismissed with a reason even when other changes are blocked.

## Lifecycle and identity

`draft → awaiting_approval → approved → simulated_implementation → monitoring → closed`

Open states can also transition to `dismissed`. Task completion is permitted only in monitoring; task owner/due edits only in draft. Invalid skips, repeated completion, missing acknowledgement, insufficient outcome notes, stale record versions and mismatched evidence are rejected.

The actor is the fixed **Demo house supervisor** persona. Task owners are house supervisor, staffing manager, medical staff coordinator, access coordinator and quality reviewer. This is a seeded demo identity model, not SSO, role-based enterprise authorization or separation of duties. Actor identity cannot be supplied in a client request.

A conditional staffing proposal preserves all agency/acceptance dependencies. Simulated task outcomes demonstrate follow-through; they do not turn hypothetical staff into verified source employees or validate clinical outcomes. Approval does not reserve staffing capacity across alternative plans. Coordination with an external scheduling system is outside this workflow.

## Storage and configuration

`PULSE_WORKFLOW_PATH` defaults to `data/workflow/pulse_workflow.sqlite`. It is a separate SQLite database, created automatically when first used or during readiness/preparation checks. No new package or database service is required. The application rejects using the source database path as workflow storage. Generated workflow data is ignored by version control.

The database contains versioned plan documents and append-only application audit events. A single transaction commits each state/task change and its event. Each event links to the preceding hash and includes actor, time, reason/details and before/after plan hashes. Reads validate plan and audit integrity inside a consistent transaction. This detects broken records and hash chains; it is not an externally signed or administrator-proof ledger.

Every mutation includes `expected_version`, so concurrent requests cannot silently overwrite a newer plan. A creation idempotency key prevents duplicate drafts after a retried save; reuse for different input is rejected. Data and evidence survive application restart. Workflow storage failure causes readiness to fail while liveness remains independent.

Before creation and each substantive change, the service rechecks the investigation digest against current source records at the plan's original knowledge clock. A changed source snapshot requires a new simulation and plan. Approval binds its original proposal and evidence; it never silently recomputes a different assignment plan. Source validation and workflow commit span separate databases, so this is a snapshot-bound demo workflow, not an atomic external resource reservation.

Task completion writes a content-addressed outcome artifact, then commits the task and audit change. A failure rolls back the SQLite change. An interrupted transaction can leave an unreferenced immutable artifact; no task is shown complete without a committed reference. Closure checks each outcome's kind, plan, task, snapshot and simulated marker.

## API

| Method and route | Behavior |
|---|---|
| `GET /api/workflow/meta` | Seeded actor, allowed owner roles and explicit demo mode |
| `GET /api/plans?investigation_id=...` | Saved plans for this investigation across evidence snapshots |
| `POST /api/plans?as_of=...` | Create draft from `simulation_id`, `snapshot_id`, `idempotency_key` |
| `GET /api/plans/{id}` | Plan, tasks and verified audit chain |
| `POST /api/plans/{id}/transition` | Explicit submit, approve, simulate implementation, monitor, close or dismiss |
| `PATCH /api/plans/{id}/tasks/{task_id}` | Draft-only owner/due edit |
| `POST /api/plans/{id}/tasks/{task_id}/complete` | Monitoring-only simulated completion with acknowledgement and outcome note |
| `GET /api/artifacts/{digest}` | Saved task outcome and existing investigation/simulation/explanation artifacts |

Mutation bodies include `expected_version`, `snapshot_id`, optional `note` and `acknowledge_demo`. Transition adds `transition`; task edit adds owner/due fields. Approval, simulated implementation and closure require acknowledgement. Completion additionally requires an outcome note. Body/schema errors return 422, missing records 404, lifecycle/version/evidence conflicts 409, and storage/integrity failures 503. No delete or external-write endpoint exists.

## Verification and limitations

Python tests cover restart persistence, idempotent draft creation, full lifecycle, incomplete/residual-gap closure rejection, explicit acknowledgement, draft-only edits, outcome notes, concurrent writers, stale approvals, dismissal, transactional rollback, mismatched completion evidence, audit corruption, source immutability and readiness failure. Component tests exercise explicit approval, blocked closure, snapshot mismatch and creation retries.

The live API-to-React check runs the entire demo workflow and still finds the original operational source investigation afterward. It uses isolated temporary workflow/evidence stores and disables live model calls to avoid changing saved user plans or relying on external inference. These checks run in jsdom; native browser interaction and visual appearance remain unverified following the existing browser URL policy block.

The prior live-model verification gap also remains: no provider endpoint/credentials were supplied. This workflow works with the labeled rule-based evidence brief. Final evaluation, demo rehearsal and broader visual polish remain Stage 7.

Stage 6 results: 119 Python tests, 23 component tests and 2 live HTTP-to-React tests pass, along with strict TypeScript and the production build. The live flow exercises proposal creation, explicit approval, simulated implementation, monitoring, per-task outcomes and simulated closure.
