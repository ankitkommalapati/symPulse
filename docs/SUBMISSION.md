# symPulse — Mission: Impact

## Submission abstract

Healthcare operations teams make decisions across staffing, provider privileges, vendor access and quality reporting. Each system provides useful signals, but assembling the next operational decision still requires context across domains.

symPulse is a concept prototype that turns workflow-informed synthetic records into one evidence-backed readiness investigation. Transparent rules identify gradual overtime drift, upcoming coverage gaps and time-bounded dependencies. Leaders inspect source evidence, compare constrained staffing responses and save a reviewable proposal with owners, deadlines and an audit trail.

The demonstration starts with a 36 nursing-hour ICU gap. Two eligible internal moves cover 24 hours while preserving donor coverage. A hybrid proposal models the remaining capacity through one hypothetical agency shift. Under explicit rates, that proposal differs from agency-only staffing by $2,640 in incremental coverage cost. The assumptions and residual risks remain visible.

Pulse completes the decision loop through explicit demo approval, tracked follow-ups and simulated completion evidence. A configurable language-model adapter can organize certified statements; the demonstrated default is an honestly labeled rule-based brief. No production integration, patient outcome or realized financial benefit is claimed.

## One sentence

**Each system sees a piece. Pulse assembles the next decision—and the evidence to act on it.**

## Demonstrated impact

- A proposed reassignment reduces the recorded ICU gap from 36 to 12 RN-hours without under-covering Step-down.
- A conditional hybrid scenario models zero residual nursing gap, with unverified capacity explicitly separated.
- Cross-domain source records, identities, dates and formulas are available from the investigation.
- Approval and follow-through have durable owners, deadlines, evidence and an audit history.
- The recorded API rehearsals and component fixture results are inspectable in **Demo evidence** and the saved validation report, including their failures and limits.

## Product direction

A potential intelligence application above connected healthcare operations products, focused on decisions that require more than one domain. Commercial discovery would validate data contracts, connector permissions, source freshness, policy fit, enterprise identity and review workflows with authorized users. It complements existing operational products rather than asserting that their individual warnings are absent.

## Judge questions

| Question | Supported answer |
|---|---|
| Why is this more than a dashboard? | It joins an investigation to captured evidence, constrained interventions and a reviewable follow-up plan. Demonstrate that path. |
| What is the AI doing? | Statistics and rules detect/validate the operational facts. The optional model organizes certified statements; it cannot invent counts, causes or actions. The demonstrated default is fallback. |
| Is the staffing plan optimal? | It is a deterministic bounded comparison, not global hospital optimization. Constraints and residual gaps are explicit. |
| What did you save? | Only a modeled incremental cost difference under stated hypothetical capacity/rates. Real savings and investigation-time reduction need a user study. |
| How accurate is it? | Show family-level synthetic counts and denominators. Do not pool unlike tasks into a hospital accuracy claim. |
| Why is one fixture mismatched? | Late approval is not known at the selected clock. The engine flags lack of established visit readiness; the old fixture expects suppression. The disagreement remains failed pending label/data-contract review. |
| Can the plan change a hospital schedule? | No. This is a local demo decision workflow with explicitly simulated outcomes. |
| Is it production ready? | No. Live data contracts, delivery freshness, authorization, policy calibration, external execution and user validation remain necessary. |
