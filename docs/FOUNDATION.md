# Application foundation

The service uses SQLite for source records and a filesystem object store for evidence. Both are configured through paths; no separate database service is required.

## Setup and execution

Use a Python 3.9+ environment. From the project root, install the pinned dependency set, prepare the data and run the service:

```text
python -m pip install -r requirements.lock
python -m pulse prepare
python -m pulse serve
```

`prepare` generates seed 42 only when both the manifest and database are absent, validates the dataset, checks source/storage readiness and persists the dataset manifest as an evidence object. Existing data is validated rather than overwritten. A partial or damaged dataset fails explicitly; generate into a new data directory to create a fresh archive.

Run `python -m pulse check` for an independent database/storage readiness check. Stop the server with the terminal's interrupt command. The default listener is `127.0.0.1:8000`.

## Configuration

Copy `.env.example` to `.env` if defaults need to change. Process environment values override `.env`. Paths are resolved relative to the project root, independently of the shell's current directory. Secrets and generated data are excluded from source control.

| Setting | Default | Meaning |
|---|---|---|
| `PULSE_DATA_DIR` | `data/generated` | Dataset archive, manifest and validation outputs |
| `PULSE_DATABASE_PATH` | `<data directory>/pulse_demo.sqlite` | Source database; defaults automatically follow `PULSE_DATA_DIR` |
| `PULSE_EVIDENCE_DIR` | `data/evidence` | Persistent content-addressed JSON objects |
| `PULSE_AS_OF` | `2026-11-05T14:00:00Z` | Frozen knowledge clock; timezone offset required |
| `PULSE_TIMEZONE` | `America/Chicago` | Hospital display timezone |
| `PULSE_HOST` | `127.0.0.1` | Listener address |
| `PULSE_PORT` | `8000` | Listener port, 1–65535 |

A separately configured database must already exist for preparation. The generator owns the standard database within the data directory. `prepare` validates the configured database against the archive's counts and record integrity checks.

## HTTP contract

| Route | Behavior |
|---|---|
| `GET /health/live` | Process liveness, independent of storage readiness |
| `GET /health/ready` | Source schema/integrity and evidence write/read checks; 503 on failure |
| `GET /api/meta` | Version, synthetic label, knowledge clock and timezone; no filesystem paths |
| `GET /api/sources?as_of=...` | Known record counts and total archived version counts across 21 operational tables |
| `GET /api/units?as_of=...` | Units known at the selected clock |
| `GET /api/records/{table}?as_of=...&limit=100&offset=0` | Stable record-ID pagination, maximum 500 per request |
| `GET /api/evidence/{record_id}?as_of=...` | Source record known at clock, durable snapshot digest and artifact URL |
| `GET /api/artifacts/{digest}` | Integrity-checked saved evidence snapshot, including its original clock |
| `GET /openapi.json` | Machine-readable API schema |
| `GET /docs` | Interactive API reference; the documentation viewer loads its standard assets externally |

All `as_of` parameters are optional and default to the configured clock. Supply an explicit offset, for example `2026-11-05T08:00:00-06:00`; timestamps are normalized to UTC. Known future assignments remain visible. Late reports and future corrections remain invisible until their availability time.

For each record identity, the repository first filters by availability, then selects the highest known version, then removes tombstones. Reads use a read-only connection and bound values. Table names come from a fixed operational allowlist. Evaluation labels and fixture names are never exposed through this API.

The evidence endpoint saves a snapshot containing the selected source revision and knowledge clock. Canonical UTF-8 JSON produces a SHA-256 identity; object writes are atomic and reads verify the content against the identity. An artifact URL always retrieves that saved snapshot, not a newly queried record. Reusing a snapshot under a different investigation clock requires an explicit source read for that clock.

No endpoint accepts an arbitrary file path or SQL query. The default service is a synthetic demonstration API on a loopback listener; enterprise authorization is outside this stage.

## Verification

```text
python -m unittest discover -s tests -v
python -m pulse prepare
python -m pulse check
python scripts/smoke_api.py
```

The foundation suite covers configuration precedence, timezone validation, exact subsecond availability, future revisions, tombstones, read-only access, table allowlisting, pagination, evidence persistence and corruption detection, missing-dependency readiness, and the working HTTP contract. Dataset preparation also executes the existing source-data integrity and hero arithmetic validator.

These checks validate the foundation. They do not constitute detector, LLM, simulation or clinical-outcome evaluation.

### Stage 1 verification results

| Check | Result |
|---|---|
| Foundation suite | 27 tests passed |
| Clean preparation | Generated and validated the complete archive in an empty directory |
| Repeat preparation | Preserved the existing database without rewriting it |
| Dataset validation | 30,316 source record versions across 21 tables; SQLite payloads match source JSONL |
| Dependency consistency | No broken requirements |
| Live HTTP flow | Readiness, source inventory, six units and persisted evidence round trip passed |

The HTTP smoke check starts an isolated loopback listener and stops it on completion. No background service is required to review these results.
