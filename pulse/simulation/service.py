"""Snapshot-bound simulation API models and service."""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from pulse.intelligence.engine import IntelligenceEngine, content_hash
from pulse.simulation.engine import Simulator


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    kind: Literal['reassignment', 'overtime', 'agency', 'hybrid']
    employee_ids: Optional[list[str]] = Field(default=None, max_length=12)
    agency_slots: Optional[int] = Field(default=None, ge=0, le=3, strict=True)
    agency_hourly_rate_usd: Optional[float] = Field(default=None, ge=0, le=1000)
    overtime_accepted: bool = False
    assume_agency_available: bool = False


class SimulationService:
    def __init__(self, repository, storage, timezone):
        self.repository, self.storage, self.timezone = repository, storage, timezone

    def prepare(self, investigation_id, as_of):
        tables = self.repository.snapshot(as_of)
        packet = IntelligenceEngine(tables, as_of, self.timezone).analyze()['investigations'].get(investigation_id)
        if packet is None:
            raise LookupError('Investigation not found at the selected clock')
        digest = self.storage.put_json(packet)
        return Simulator(tables, packet, self.timezone), digest

    def context(self, investigation_id, as_of):
        simulator, digest = self.prepare(investigation_id, as_of)
        return {**simulator.context(), 'snapshot_id': digest, 'as_of': simulator.packet['as_of'],
                'input_hash': simulator.packet['input_hash']}

    def simulate(self, investigation_id, as_of, request):
        simulator, digest = self.prepare(investigation_id, as_of)
        if request.snapshot_id != digest:
            raise ValueError('Investigation snapshot changed. Refresh the investigation before simulating.')
        if request.employee_ids is not None and len(request.employee_ids) != len(set(request.employee_ids)):
            raise ValueError('An employee cannot occupy more than one proposed slot')
        if request.kind == 'agency' and request.employee_ids:
            raise ValueError('Agency scenarios cannot include internal employee assignments')
        if request.kind in ('reassignment', 'overtime') and request.agency_slots:
            raise ValueError('This intervention does not include agency slots')
        values = request.model_dump(exclude={'snapshot_id', 'agency_hourly_rate_usd'})
        result = simulator.evaluate(**values, agency_rate=request.agency_hourly_rate_usd)
        input_tables = {key: value for key, value in simulator.tables.items() if key in {
            'employees', 'employee_qualifications', 'workforce_assignments', 'staffing_requirements',
            'unavailability', 'units', 'facilities', 'entity_crosswalk'}}
        input_snapshot_id = self.storage.put_json({'kind': 'simulation_inputs', 'schema_version': 1,
            'as_of': simulator.packet['as_of'], 'tables': input_tables})
        document = {'kind': 'simulation_evidence', 'schema_version': 1, 'synthetic': True,
                    'investigation_id': investigation_id, 'snapshot_id': digest, 'as_of': simulator.packet['as_of'],
                    'input_hash': simulator.packet['input_hash'], 'input_snapshot_id': input_snapshot_id, 'policy': simulator.context_policy(),
                    'request': request.model_dump(), 'result': result}
        evidence_id = self.storage.put_json(document)
        return {**document, 'simulation_id': evidence_id, 'artifact_url': '/api/artifacts/' + evidence_id}
