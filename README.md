# symPulse

**From cross-product operational signals to an evidence-backed decision for the next 72 hours.**

Operational intelligence prototype for the **Mission: Impact** hackathon, November 5–6, 2026. Concept prototype; not an existing symplr product.

## Start here

1. [Product requirements](docs/PRD.md): scope, experience, algorithms, acceptance criteria, commercial direction.
2. [Product research](docs/RESEARCH.md): symplr portfolio, existing overlap, public workflow evidence, source register and access limitations.
3. [Synthetic data contract](docs/DATA_SPEC.md): source-shaped records, canonical relationships, timestamps, scenario design and validation.
4. [Two-day execution and demo](docs/BUILD_AND_DEMO.md): implementation order, cut lines, pitch and impact measurement.
5. [Implementation stages](docs/IMPLEMENTATION_STAGES.md): stage boundaries and review gates.
6. [Application foundation](docs/FOUNDATION.md): configuration, API and evidence persistence.
7. [Operational intelligence](docs/INTELLIGENCE.md): detection rules, findings, provenance and investigation API.
8. [Operational workspace](docs/WORKSPACE.md): application setup, review flow and verification.
9. [Staffing simulation](docs/SIMULATION.md): constrained interventions, modeled costs, assumptions and saved evidence.
10. [Evidence briefs](docs/EXPLANATIONS.md): bounded AI organization, focused questions, provider configuration and labeled fallback.
11. [Response workflows](docs/WORKFLOWS.md): saved proposals, demo approval, owners, simulated outcomes and audit history.
12. [Release verification](docs/VERIFICATION.md): recorded fixture outcomes, three API rehearsals, timings and remaining gates.
13. [Demo runbook](docs/DEMO_RUNBOOK.md) and [submission](docs/SUBMISSION.md): presentation steps and defensible claims.

## Run the application

From the project root with Python 3.9+ and Node.js 22.12+:

```text
python -m pip install -r requirements.lock
python -m pulse prepare
npm --prefix apps/web ci
npm --prefix apps/web run build
python -m pulse serve
```

Open the workspace at `http://127.0.0.1:8000`. The same process serves the API. Check `/health/ready`, inspect `/api/sources`, or open `/docs` for the API reference. Configuration defaults work without an environment file; `.env.example` lists the supported settings.

Run Python checks with `python -m unittest discover -s tests -v`, frontend checks with `npm --prefix apps/web test`, and the live API-to-workspace flow with `python scripts/smoke_workspace.py`. See the [workspace guide](docs/WORKSPACE.md) for verification limits.

For an isolated presentation session, run `python -m pulse demo --port 8800`. For the complete verification report, run `python scripts/verify_release.py`. The demo command preserves normal saved plans.

## Runnable synthetic-data starter

Requires Python 3.9+ with the project dependencies installed. Data generation uses no credentials or network access.

```bash
python3 scripts/generate_data.py
python3 scripts/validate_data.py
```

Creates JSONL source-shaped extracts, an application-readable SQLite database, a file manifest, a generated data dictionary, a computed hero scenario summary, and a separate evaluation fixture suite under `data/`. Generated artifacts are reproducible with seed 42. These schemas and distributions are **our prototype contracts**, informed by public workflows; they are not symplr's private schemas, real exports, or measured hospital distributions.

The service provides source access, persistent evidence snapshots and deterministic unit readiness investigations. Open `/api/investigations` for findings and `/api/investigations/FAC-01:ICU:readiness` for the complete ICU evidence packet. The [stage plan](docs/IMPLEMENTATION_STAGES.md) defines the application stages. Evaluation fixtures have labels and are excluded from operational analysis.

## Demo clock

Frozen at **November 5, 2026, 08:00 America/Chicago**, for a fictional US hospital; development schedule uses November 5–6 in India. Historical dates and future schedule dates are intentional. A future scheduled shift is known at the demo clock; a future worked shift is not.

## Scope

Four operational domains; five logical feeds because provider credentials and physician assignments have different owners. One ICU investigation within six departments; deterministic staffing comparisons; human-approved local action plans.

No production integrations, patient records, autonomous source-system changes, or validated clinical risk predictions.
