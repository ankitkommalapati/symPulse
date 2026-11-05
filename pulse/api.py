"""Foundation HTTP API. Operational records are always selected as of a clock."""
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from pulse import __version__
from pulse.config import Settings, utc_timestamp
from pulse.repository import DatasetUnavailable, SourceRepository
from pulse.storage import EvidenceStore

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None):
    settings = settings or Settings.load()
    repository = SourceRepository(settings.database_path)
    storage = EvidenceStore(settings.evidence_dir)
    app = FastAPI(title="symplr Pulse", version=__version__,
                  description="Synthetic operational evidence API. All source reads use an explicit availability clock.")
    app.state.settings = settings
    app.state.repository = repository
    app.state.storage = storage

    def clock(value):
        try:
            return utc_timestamp(value or settings.as_of)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.exception_handler(DatasetUnavailable)
    async def unavailable_handler(request: Request, exc: DatasetUnavailable):
        logger.warning("Dataset unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "alive", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    def ready():
        repository.check()
        try:
            storage.check()
        except (OSError, ValueError) as exc:
            logger.warning("Evidence storage readiness failed: %s", exc)
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable") from exc
        return {"status": "ready", "checks": {"source_database": "passed", "evidence_storage": "passed"}}

    @app.get("/api/meta", tags=["configuration"])
    def meta():
        return {"application": "symplr Pulse", "version": __version__, "synthetic": True,
                "as_of": settings.as_of, "hospital_timezone": settings.hospital_timezone,
                "source_access": "read_only", "clock_semantics": "available_at_then_latest_version"}

    @app.get("/api/sources", tags=["sources"])
    def sources(as_of: Optional[str] = None):
        selected_clock = clock(as_of)
        return {"as_of": selected_clock, "items": repository.inventory(selected_clock)}

    @app.get("/api/units", tags=["sources"])
    def units(as_of: Optional[str] = None):
        selected_clock = clock(as_of)
        return {"as_of": selected_clock, "items": repository.records("units", selected_clock)}

    @app.get("/api/records/{table}", tags=["sources"])
    def records(table: str, as_of: Optional[str] = None,
                limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)):
        selected_clock = clock(as_of)
        try:
            items = repository.records(table, selected_clock, limit, offset)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"as_of": selected_clock, "table": table, "limit": limit, "offset": offset, "items": items}

    @app.get("/api/evidence/{record_id}", tags=["evidence"])
    def evidence(record_id: str, as_of: Optional[str] = None):
        selected_clock = clock(as_of)
        try:
            record = repository.record(record_id, selected_clock)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Evidence record not found") from exc
        if record is None:
            raise HTTPException(status_code=404, detail="Evidence record not known at the selected clock")
        document = {"kind": "source_evidence", "schema_version": 1,
                    "as_of": selected_clock, "record": record}
        try:
            digest = storage.put_json(document)
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable") from exc
        return {"evidence_id": digest, "artifact_url": "/api/artifacts/" + digest, **document}

    @app.get("/api/artifacts/{digest}", tags=["evidence"])
    def artifact(digest: str):
        try:
            document = storage.get_json(digest)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Evidence artifact not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Evidence artifact is invalid") from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable") from exc
        if document.get("kind") != "source_evidence":
            raise HTTPException(status_code=404, detail="Evidence artifact not found")
        return {"evidence_id": digest, **document}

    return app
