# Four-minute demonstration

## Preparation

From the project root, use the dependency versions in the lockfiles:

```text
python -m pip install -r requirements.lock
npm --prefix apps/web ci
npm --prefix apps/web run build
python -m pulse prepare
python scripts/verify_release.py
python -m pulse demo --port 8800
```

Open `http://127.0.0.1:8800`. The demo command creates a fresh workflow/evidence session on each launch while preserving existing plans and the generated source archive. It prints the session identity. Stop the listener with the terminal interrupt command; launch the same command again for a clean rehearsal. Old demo sessions remain under the ignored `data/demo_sessions` directory. Nothing is deleted automatically.

The source snapshot is November 5, 2026, 08:00 America/Chicago. Confirm the header before presenting. Default seed 42 yields the high-priority ICU investigation and an informational Step-down reporting review. Do not describe the source products as missing obvious individual warnings: Pulse's demonstration is the assembled cross-product decision.

The current explanation mode is visibly labeled rule-based fallback. Live model inference, native browser behavior and actual visual appearance have not been verified. The completed automated rehearsals use API/React tests, not a recorded browser presentation. A human should inspect layout, keyboard/dialog behavior and downloads before presenting; no backup video is included.

## Script and clicks

| Time | Show | Say |
|---|---|---|
| 0:00–0:25 | Overview, synthetic label, ICU focus card | “Each system sees a piece. Pulse assembles the next decision. At this snapshot, the ICU needs eight nurses for an upcoming shift; three are unavailable.” |
| 0:25–1:05 | Open ICU investigation; 36 RN-hours, 19 physician-hours, vendor visit and timeline | “Pulse connects staffing, provider authorization, access and reporting context in one department and review window. These are different units of impact; we do not add physician-hours to nurse-hours.” |
| 1:05–1:40 | Click nursing metric; search `ABS-HERO-0`; inspect saved record; close drawer. Point to pending-valid renewal panel | “Every finding has a source revision and availability time. A pending renewal is not automatically an invalid grant. The first affected physician assignment has six uncovered hours; the full window has nineteen.” |
| 1:40–2:45 | Compare interventions; select Move eligible staff; show 12-hour residual, zero donor gap. Search `SYN-RN-043` for missing competency. Compare agency and hybrid | “Two eligible internal moves cover 24 of the 36 hours and preserve Step-down coverage. We keep the remaining 12 hours visible. Three hypothetical agency shifts cost $3,960; two moves plus one hypothetical agency shift cost $1,320 under these assumptions.” |
| 2:45–3:25 | Select hybrid, Calculate this scenario, Save draft plan. Review assignments/tasks. Submit, explicitly acknowledge, Approve demo plan | “That is a modeled $2,640 difference in incremental coverage cost, not realized savings. Approval records a decision; it does not clear provider privileges, verify agency staff or finish quality follow-up.” |
| 3:25–4:00 | Show open tasks and audit. Open Demo evidence | “The API rehearsal completed this workflow three times with identical core arithmetic. The evaluation report also shows partial cases and a fixture disagreement. Mission: Impact means a traceable decision and a feasible proposed response before the shift.” |

Allow several seconds for calculations. Use that time to explain the distinction between modeled capacity and verified capacity. Do not claim the subsecond simulation target has been met.

## Optional trust demonstrations

- Select **Four hours earlier** in the knowledge snapshot selector. The three absence notices were not yet available, so the nursing gap changes. Restore the demonstration snapshot before proceeding.
- Select **Evidence brief → What can we not conclude?** Show caveats rather than claiming a discovered root cause.
- In the scenario, toggle hypothetical agency availability. It changes the assumption-dependent gap; the gap excluding unverified capacity remains visible.
- For a deeper workflow review, record simulated implementation, start monitoring, and explicitly complete each task with an outcome note and demo acknowledgement. Close with a final simulated outcome note. The underlying ICU source investigation remains open. A reassignment-only proposal with twelve residual hours cannot close.

## Failure and recovery

| Situation | Recovery |
|---|---|
| Data is missing | Run `python -m pulse prepare`; partial archives fail explicitly rather than being overwritten |
| Workspace unavailable | Run `npm --prefix apps/web run build`, then restart the listener |
| Source snapshot changed | Refresh, recalculate a scenario and create a new plan; do not try to approve stale assignments |
| A workflow is midway through rehearsal | Stop the listener and start a new demo session; existing work remains saved |
| Model unavailable | Use the labeled rule-based brief; do not call it live-generated AI |
| Time is short | Stop at approval with open follow-ups; show the recorded full-flow rehearsal report |
| Verification report is missing | Run `python scripts/verify_release.py`; it creates the saved report after actual checks |

## What not to claim

No actual symplr exports, production connectors, staff notifications, clinical predictions, causal discovery, confirmed agency availability, real schedule changes, realized savings or hospital-level precision were demonstrated. The source schemas are workflow-informed prototype contracts. The model interface organizes certified statements and does not own eligibility or cost arithmetic.

The report's small “holdout” labels were visible during development. The simulation holdout has no feasible positive example. Three rehearsals demonstrate repeatability of this synthetic scenario; they do not measure user time saved.
