"""Certified statement catalog: model selection never becomes new operational facts."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timezone
from time import monotonic
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pulse.explanations.provider import ChatProvider, ProviderFailure
from pulse.intelligence.engine import content_hash

PROMPT_VERSION = 'pulse-evidence-selection-1'
Question = Literal['overview', 'staffing', 'connections', 'limits', 'remaining', 'simulation']
QUESTIONS = {'overview': 'What should I know?', 'staffing': 'What supports the staffing concern?',
             'connections': 'Why are these signals together?', 'limits': 'What can we not conclude?',
             'remaining': 'What still needs attention?', 'simulation': 'What would this staffing proposal change?'}


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    question: Question = 'overview'
    simulation_id: Optional[str] = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    summary_id: str
    observation_ids: list[str] = Field(max_length=256)
    hypothesis_ids: list[str] = Field(max_length=64)
    unknown_ids: list[str] = Field(max_length=256)
    recommended_action_ids: list[str] = Field(max_length=256)
    remaining_risk_ids: list[str] = Field(max_length=256)


def catalog_for(packet, question, simulation=None):
    groups = packet['evidence_groups']
    def statement(text, ids=()):
        return {'text': text, 'evidence_group_ids': [key for key in ids if key in groups]}
    metrics = packet['metrics']
    observations = {f'fact-{i}': statement(o['fact'] + '.', o['evidence_group_ids']) for i, o in enumerate(packet['observations'])}
    coverage = metrics['coverage']
    observations['staffing-hours'] = statement(f"The known plan leaves {coverage['uncovered_rn_hours']:g} RN-hours unestablished as covered across the investigation window; {coverage['unverified_gap_rn_hours']:g} RN-hours require eligibility verification.", ['workforce_coverage'])
    observations['physician-hours'] = statement(f"Recorded physician assignments include {metrics['provider']['uncovered_physician_hours']:g} hours outside established authorization coverage.", ['provider_readiness'])
    observations['vendor-visits'] = statement(f"{len(metrics['access']['findings'])} planned vendor visits have incomplete credential readiness.", ['access_readiness'])
    q = metrics['quality']
    observations['quality-context'] = statement(f"The completed comparison windows contain {q['baseline_reports']} and {q['current_reports']} known near-miss reports. Interpretation depends on patient-day denominators and reporting context.", ['quality_reports'])
    observations['connections'] = statement('Verified department mappings and an overlapping review period connect these findings; this is contextual association, not proof of causation.', ['entity_relationships'])
    for i, renewal in enumerate(metrics['provider']['renewal_followups']):
        observations[f'renewal-{i}'] = statement(f"Provider {renewal['provider_id']}: a pending renewal retains coverage for all evaluated assignments." if renewal['all_evaluated_assignments_covered'] else 'A pending renewal needs review because recorded authorization does not cover every evaluated assignment.', ['provider_readiness'])
    hypotheses = {f'hypothesis-{i}': statement(h['text'] + '. This remains unconfirmed.', h['evidence_group_ids']) for i, h in enumerate(packet['hypotheses'])}
    unknowns = {f'unknown-{i}': statement(text) for i, text in enumerate(packet['unknowns'])}
    unknowns['operational-only'] = statement('This is operational decision support, not a validated clinical risk assessment or an established root-cause finding.')
    unknowns['completeness'] = statement('All conclusions depend on records known at this snapshot; missing data and later arrivals can change the assessment.')
    actions = {r['id']: {'text': r['task'] + '.', 'owner_role': r['owner_role'], 'evidence_group_ids': []} for r in packet['recommended_reviews']}
    remaining = {'separate-reviews': statement('A staffing proposal does not complete physician authorization, vendor verification or quality review; follow up on the findings actually present.')}
    if simulation:
        r = simulation['result']
        observations['simulation-result'] = {**statement(f"The {r['kind']} proposal is {r['status']}. Its modeled residual gap is {r.get('modeled_uncovered_rn_hours', coverage['uncovered_rn_hours']):g} RN-hours, with ${r.get('incremental_cost_usd', 0):,.2f} modeled incremental coverage cost."), 'simulation_id': simulation['simulation_id']}
        remaining['simulation-capacity'] = {**statement(f"Excluding unverified additional capacity, {r.get('gap_without_unverified_capacity', coverage['uncovered_rn_hours']):g} RN-hours remain. Source schedules have not changed."), 'simulation_id': simulation['simulation_id']}
        for i, dependency in enumerate(r.get('dependencies', []) + r.get('reasons', [])):
            unknowns[f'simulation-limit-{i}'] = statement(dependency)
    if question == 'staffing':
        observations = {k: v for k, v in observations.items() if k == 'staffing-hours' or 'workforce_coverage' in v['evidence_group_ids'] or 'overtime_drift' in v['evidence_group_ids']}
        actions = {k: v for k, v in actions.items() if k == 'review-staffing'}
    elif question == 'connections':
        observations = {'connections': observations['connections']}
    elif question == 'limits':
        observations = {}
        hypotheses = {}
    elif question == 'simulation':
        observations = {'simulation-result': observations['simulation-result']}
    summaries = {'review': statement('The selected evidence supports a coordinated operational review. Use the measurements and source records below to decide the next steps.')}
    summaries['evidence_first'] = statement('Separate established observations, unconfirmed context and unknowns before choosing an operational response. Every statement below belongs to the selected evidence snapshot.')
    sections = {'summaries': summaries, 'observations': observations, 'hypotheses': hypotheses, 'unknowns': unknowns,
                'recommended_actions': actions, 'remaining_risks': remaining}
    sections['required_ids'] = {key: list(value) for key, value in sections.items() if key != 'summaries'}
    return sections


FIELDS = {'observation_ids': 'observations', 'hypothesis_ids': 'hypotheses', 'unknown_ids': 'unknowns',
          'recommended_action_ids': 'recommended_actions', 'remaining_risk_ids': 'remaining_risks'}


def validate_selection(raw, catalog):
    choice = Selection.model_validate(raw)
    if choice.summary_id not in catalog['summaries']:
        raise ValueError('Unknown summary')
    for field, section in FIELDS.items():
        ids = getattr(choice, field)
        if len(ids) != len(set(ids)) or set(ids) != set(catalog['required_ids'][section]):
            raise ValueError('Unsupported, omitted or duplicated statement')
    return choice


def fallback_selection(catalog):
    return Selection(summary_id='review', **{field: list(catalog[section]) for field, section in FIELDS.items()})


class ExplanationService:
    def __init__(self, intelligence, storage, config, provider=None):
        self.intelligence, self.storage, self.config = intelligence, storage, config
        self.provider = provider or ChatProvider(config)
        self.cache = OrderedDict()
        self.locks = {}
        self.expiry = {}

    async def explain(self, investigation_id, as_of, request):
        from starlette.concurrency import run_in_threadpool
        packet = await run_in_threadpool(self.intelligence.packet, investigation_id, as_of)
        if packet is None:
            raise LookupError('Investigation not found at the selected clock')
        if packet['snapshot_id'] != request.snapshot_id:
            raise ValueError('Investigation snapshot changed. Refresh before requesting a brief.')
        simulation = None
        if request.simulation_id:
            try:
                simulation = self.storage.get_json(request.simulation_id)
            except (FileNotFoundError, ValueError):
                raise LookupError('Saved simulation evidence was not found') from None
            if simulation.get('kind') != 'simulation_evidence' or simulation.get('snapshot_id') != request.snapshot_id or simulation.get('investigation_id') != investigation_id:
                raise ValueError('Simulation does not belong to this investigation snapshot')
            simulation = {**simulation, 'simulation_id': request.simulation_id}
        if request.question == 'simulation' and simulation is None:
            raise ValueError('Select saved simulation evidence for this question')
        catalog = catalog_for(packet, request.question, simulation)
        key = content_hash({'snapshot': request.snapshot_id, 'simulation': request.simulation_id, 'question': request.question,
                            'prompt': PROMPT_VERSION, 'catalog': catalog, 'model': self.config.model, 'endpoint': self.config.endpoint})
        lock = self.locks.setdefault(key, asyncio.Lock())
        async with lock:
            if key in self.cache and self.expiry[key] > monotonic():
                self.cache.move_to_end(key)
                return {**self.cache[key], 'cache_hit': True}
            status, reason, model = 'fallback', 'not_configured', None
            choice = fallback_selection(catalog)
            if self.config.endpoint:
                try:
                    raw, model = await asyncio.wait_for(self.provider.generate(catalog, QUESTIONS[request.question]), self.config.timeout_seconds * 2 + 0.5)
                    choice = validate_selection(raw, catalog)
                    status, reason = 'model_selected', None
                except (ValidationError, ValueError):
                    reason = 'validation_failed'
                except (ProviderFailure, asyncio.TimeoutError):
                    reason = 'provider_unavailable'
            body = {'kind': 'explanation_evidence', 'schema_version': 1, 'synthetic': True,
                    'snapshot_id': request.snapshot_id, 'investigation_id': investigation_id, 'simulation_id': request.simulation_id,
                    'question': request.question, 'question_text': QUESTIONS[request.question], 'prompt_version': PROMPT_VERSION,
                    'catalog_hash': content_hash(catalog), 'status': status, 'fallback_reason': reason,
                    'requested_model': self.config.model or None, 'returned_model': model,
                    'validation': 'passed' if status == 'model_selected' else 'certified_fallback',
                    'generated_at': datetime.now(timezone.utc).isoformat(), 'selection': choice.model_dump(),
                    'summary': catalog['summaries'][choice.summary_id],
                    **{section: [{'id': key, **catalog[section][key]} for key in getattr(choice, field)] for field, section in FIELDS.items()}}
            digest = await run_in_threadpool(self.storage.put_json, body)
            result = {**body, 'explanation_id': digest, 'artifact_url': '/api/artifacts/' + digest, 'cache_hit': False}
            self.cache[key] = result
            self.expiry[key] = float('inf') if status == 'model_selected' or reason == 'not_configured' else monotonic() + 15
            while len(self.cache) > 32:
                oldest, _ = self.cache.popitem(last=False)
                self.expiry.pop(oldest, None)
                self.locks.pop(oldest, None)
            return result
