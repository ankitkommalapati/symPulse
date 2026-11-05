# symplr Pulse

**From cross-product operational signals to an evidence-backed decision for the next 72 hours.**

Operational intelligence prototype for the **Mission: Impact** hackathon, November 5–6, 2026. Concept prototype; not an existing symplr product.

## Start here

1. [Product requirements](docs/PRD.md): scope, experience, algorithms, acceptance criteria, commercial direction.
2. [Product research](docs/RESEARCH.md): symplr portfolio, existing overlap, public workflow evidence, source register and access limitations.
3. [Synthetic data contract](docs/DATA_SPEC.md): source-shaped records, canonical relationships, timestamps, scenario design and validation.
4. [Two-day execution and demo](docs/BUILD_AND_DEMO.md): implementation order, cut lines, pitch and impact measurement.
5. [Implementation stages](docs/IMPLEMENTATION_STAGES.md): stage boundaries and review gates.
6. [Application foundation](docs/FOUNDATION.md): configuration, API and evidence persistence.

## Run the service

From the project root in a Python 3.9+ environment:

```text
python -m pip install -r requirements.lock
python -m pulse prepare
python -m pulse serve
```

The API listens at `http://127.0.0.1:8000`. Check `/health/ready`, inspect `/api/sources`, or open `/docs` for the API reference. Configuration defaults work without an environment file; `.env.example` lists the supported settings.

Run the foundation checks with `python -m unittest discover -s tests -v`.

## Runnable synthetic-data starter

Requires Python 3.9+; no third-party packages, credentials or network access.

```bash
python3 scripts/generate_data.py
python3 scripts/validate_data.py
```

Creates JSONL source-shaped extracts, an application-readable SQLite database, a file manifest, a generated data dictionary, a computed hero scenario summary, and a separate evaluation fixture suite under `data/`. Generated artifacts are reproducible with seed 42. These schemas and distributions are **our prototype contracts**, informed by public workflows; they are not symplr's private schemas, real exports, or measured hospital distributions.

The service provides source access and persistent evidence snapshots. The [stage plan](docs/IMPLEMENTATION_STAGES.md) defines the remaining application capabilities. Evaluation fixtures have labels and are excluded from the operational API.

## Demo clock

Frozen at **November 5, 2026, 08:00 America/Chicago**, for a fictional US hospital; development schedule uses November 5–6 in India. Historical dates and future schedule dates are intentional. A future scheduled shift is known at the demo clock; a future worked shift is not.

## Scope

Four operational domains; five logical feeds because provider credentials and physician assignments have different owners. One ICU investigation within six departments; deterministic staffing comparisons; human-approved local action plans.

No production integrations, patient records, autonomous source-system changes, or validated clinical risk predictions.
