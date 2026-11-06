"""Foundation HTTP API. Operational records are always selected as of a clock."""
import logging
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pulse import __version__
from pulse.config import ROOT, Settings, utc_timestamp
from pulse.repository import DatasetUnavailable, SourceRepository
from pulse.storage import EvidenceStore
from pulse.intelligence.service import IntelligenceService
from pulse.simulation.service import SimulationRequest, SimulationService
from pulse.explanations.provider import ModelConfig
from pulse.explanations.service import ExplainRequest, ExplanationService
from pulse.workflows.store import WorkflowStore, WorkflowUnavailable
from pulse.workflows.service import ACTOR, OWNERS, Change, CreatePlan, TaskEdit, Transition, WorkflowService

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None):
    settings = settings or Settings.load()
    if settings.workflow_path.resolve() == settings.database_path.resolve():
        raise ValueError('Workflow and source databases must have different paths')
    repository = SourceRepository(settings.database_path)
    storage = EvidenceStore(settings.evidence_dir)
    intelligence = IntelligenceService(repository, storage, settings.hospital_timezone)
    app = FastAPI(title="symPulse", version=__version__,
                  description="Synthetic operational evidence API. All source reads use an explicit availability clock.")
    app.state.settings = settings
    app.state.repository = repository
    app.state.storage = storage
    app.state.intelligence = intelligence
    explanations = ExplanationService(intelligence, storage, ModelConfig.load(ROOT))
    app.state.explanations = explanations
    simulations = SimulationService(repository, storage, settings.hospital_timezone)
    workflow_store = WorkflowStore(settings.workflow_path)
    workflows = WorkflowService(workflow_store, intelligence, storage)
    app.state.workflows = workflows
    verification_report_path = ROOT / 'docs' / 'validation' / 'release_report.json'
    web_root = ROOT / "apps" / "web" / "dist"
    if (web_root / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(web_root / "assets")), name="workspace-assets")

    @app.get("/", include_in_schema=False)
    def workspace():
        index = web_root / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=503, detail="Workspace is unavailable. Follow the application setup instructions.")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    @app.get("/pulse.svg", include_in_schema=False)
    def workspace_icon():
        icon = web_root / "pulse.svg"
        if not icon.is_file():
            raise HTTPException(status_code=404, detail="Icon not found")
        return FileResponse(icon, media_type="image/svg+xml")

    def clock(value):
        try:
            return utc_timestamp(value or settings.as_of)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.exception_handler(DatasetUnavailable)
    async def unavailable_handler(request: Request, exc: DatasetUnavailable):
        logger.warning("Dataset unavailable: %s", exc)
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(WorkflowUnavailable)
    async def workflow_unavailable(request: Request, exc: WorkflowUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "alive", "version": __version__}

    @app.get("/health/ready", tags=["health"])
    def ready():
        repository.check()
        workflow_store.check()
        try:
            storage.check()
        except (OSError, ValueError) as exc:
            logger.warning("Evidence storage readiness failed: %s", exc)
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable") from exc
        return {"status": "ready", "checks": {"source_database": "passed", "evidence_storage": "passed", "workflow_storage": "passed"}}

    @app.get("/api/meta", tags=["configuration"])
    def meta():
        return {"application": "symPulse", "version": __version__, "synthetic": True,
                "as_of": settings.as_of, "hospital_timezone": settings.hospital_timezone,
                "source_access": "read_only", "clock_semantics": "available_at_then_latest_version"}

    @app.get("/api/sources", tags=["sources"])
    def sources(as_of: Optional[str] = None):
        selected_clock = clock(as_of)
        return {"as_of": selected_clock, "items": repository.inventory(selected_clock)}

    @app.get("/api/intelligence/units", tags=["intelligence"])
    def unit_intelligence(as_of: Optional[str] = None):
        analysis = intelligence.analysis(clock(as_of))
        return {key: value for key, value in analysis.items() if key != "investigations"}

    @app.get("/api/investigations", tags=["intelligence"])
    def investigations(as_of: Optional[str] = None):
        analysis = intelligence.analysis(clock(as_of))
        return {"as_of": analysis["as_of"], "window": analysis["window"], "input_hash": analysis["input_hash"],
                "engine_version": analysis["engine_version"], "data_quality": analysis["data_quality"],
                "items": [r for r in analysis["units"] if r["investigation_id"] is not None]}

    @app.get("/api/investigations/{investigation_id}", tags=["intelligence"])
    def investigation(investigation_id: str, as_of: Optional[str] = None):
        try:
            packet = intelligence.packet(investigation_id, clock(as_of))
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Investigation evidence storage is unavailable") from exc
        if packet is None:
            raise HTTPException(status_code=404, detail="Investigation not found at the selected clock")
        return packet

    @app.get("/api/investigations/{investigation_id}/simulation", tags=["simulation"])
    def simulation_context(investigation_id: str, as_of: Optional[str] = None):
        try:
            return simulations.context(investigation_id, clock(as_of))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Simulation evidence storage is unavailable") from exc

    @app.post("/api/investigations/{investigation_id}/simulate", tags=["simulation"])
    def simulate(investigation_id: str, request: SimulationRequest, as_of: Optional[str] = None):
        try:
            return simulations.simulate(investigation_id, clock(as_of), request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Simulation evidence storage is unavailable") from exc

    @app.post("/api/investigations/{investigation_id}/explain", tags=["explanations"])
    async def explain(investigation_id: str, request: ExplainRequest, as_of: Optional[str] = None):
        try:
            return await explanations.explain(investigation_id, clock(as_of), request)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Explanation evidence storage is unavailable") from exc

    def workflow_call(call):
        try:
            return call()
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Workflow evidence storage is unavailable") from exc

    @app.get("/api/evaluation", tags=["verification"])
    def evaluation_report(as_of: Optional[str] = None):
        try:
            report = json.loads(verification_report_path.read_text())
            if report.get('schema_version') != 1 or 'dataset' not in report:
                raise ValueError('Invalid report')
        except (OSError, ValueError):
            raise HTTPException(status_code=503, detail="Demo verification report is unavailable") from None
        analysis = intelligence.analysis(clock(as_of))
        return {"report": report, "matches_selected_snapshot": report['dataset']['input_hash'] == analysis['input_hash']
                and report['dataset']['engine_version'] == analysis['engine_version']}

    @app.get("/api/workflow/meta", tags=["workflow"])
    def workflow_meta():
        return {"actor": ACTOR, "owners": OWNERS, "mode": "seeded_demo_persona", "source_writes": False}

    @app.get("/api/plans", tags=["workflow"])
    def plans(investigation_id: str):
        return {"items": workflow_call(lambda: workflow_store.list(investigation_id))}

    @app.post("/api/plans", tags=["workflow"], status_code=201)
    def create_plan(request: CreatePlan, as_of: Optional[str] = None):
        return workflow_call(lambda: workflows.create(request, clock(as_of)))

    @app.get("/api/plans/{plan_id}", tags=["workflow"])
    def plan(plan_id: str):
        return workflow_call(lambda: workflow_store.get(plan_id))

    @app.post("/api/plans/{plan_id}/transition", tags=["workflow"])
    def transition_plan(plan_id: str, request: Transition):
        return workflow_call(lambda: workflows.change(plan_id, request))

    @app.patch("/api/plans/{plan_id}/tasks/{task_id}", tags=["workflow"])
    def edit_task(plan_id: str, task_id: str, request: TaskEdit):
        return workflow_call(lambda: workflows.task(plan_id, task_id, request))

    @app.post("/api/plans/{plan_id}/tasks/{task_id}/complete", tags=["workflow"])
    def complete_task(plan_id: str, task_id: str, request: Change):
        return workflow_call(lambda: workflows.task(plan_id, task_id, request, complete=True))

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
        if document.get("kind") not in ("source_evidence", "investigation_evidence", "simulation_evidence", "simulation_inputs", "explanation_evidence", "workflow_task_outcome"):
            raise HTTPException(status_code=404, detail="Evidence artifact not found")
        return {"evidence_id": digest, **document}

    return app
