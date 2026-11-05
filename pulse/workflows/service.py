"""Demo-only approval lifecycle; source schedules and external workflows remain read-only."""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pulse.config import utc_timestamp
from pulse.intelligence.engine import content_hash
from pulse.intelligence.rules import instant
from pulse.workflows.store import WorkflowConflict, now

ACTOR = {'id': 'demo-house-supervisor', 'name': 'Demo house supervisor', 'role': 'house_supervisor'}
OWNERS = {'house_supervisor': 'House supervisor', 'staffing_manager': 'Staffing manager',
          'medical_staff_coordinator': 'Medical staff coordinator', 'access_coordinator': 'Access coordinator',
          'quality_reviewer': 'Quality reviewer'}
Owner = Literal['house_supervisor', 'staffing_manager', 'medical_staff_coordinator', 'access_coordinator', 'quality_reviewer']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CreatePlan(Contract):
    simulation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    idempotency_key: str = Field(pattern=r'^[a-zA-Z0-9-]{16,80}$')


class Change(Contract):
    expected_version: int = Field(ge=1, strict=True)
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    note: str = Field(default='', max_length=1000)
    acknowledge_demo: bool = False


class Transition(Change):
    transition: Literal['submit', 'approve', 'simulate_implementation', 'monitor', 'close', 'dismiss']


class TaskEdit(Change):
    owner_role: Optional[Owner] = None
    due_at: Optional[str] = None

    @field_validator('due_at')
    @classmethod
    def date_valid(cls, value):
        return utc_timestamp(value) if value is not None else None


class WorkflowService:
    def __init__(self, store, intelligence, evidence):
        self.store, self.intelligence, self.evidence = store, intelligence, evidence

    def artifact(self, digest, kind):
        try:
            value = self.evidence.get_json(digest)
        except (FileNotFoundError, ValueError):
            raise LookupError('Saved evidence not found') from None
        if value.get('kind') != kind:
            raise WorkflowConflict('Saved evidence has the wrong type')
        return value

    def fresh(self, plan, snapshot_id):
        if plan['snapshot_id'] != snapshot_id:
            raise WorkflowConflict('Plan belongs to a different investigation snapshot')
        current = self.intelligence.packet(plan['investigation_id'], plan['as_of'])
        if current is None or current['snapshot_id'] != snapshot_id:
            raise WorkflowConflict('Source evidence changed. Create a new simulation and plan.')
        return current

    def create(self, request, as_of):
        simulation = self.artifact(request.simulation_id, 'simulation_evidence')
        if simulation['snapshot_id'] != request.snapshot_id or utc_timestamp(simulation['as_of']) != utc_timestamp(as_of):
            raise WorkflowConflict('Simulation belongs to a different investigation snapshot')
        result = simulation['result']
        if result['status'] not in ('feasible', 'conditional') or not (result.get('actions') or result.get('agency_slots')):
            raise WorkflowConflict('Only a feasible or explicitly conditional staffing proposal can become a plan')
        plan = {'investigation_id': simulation['investigation_id'], 'snapshot_id': request.snapshot_id,
                'simulation_id': request.simulation_id, 'as_of': simulation['as_of'],
                'title': 'Staffing response proposal', 'actor_mode': 'seeded_demo_persona',
                'proposal': result, 'simulation_request': simulation['request'], 'tasks': [],
                'source_records_changed': False, 'resolution_scope': 'demo_workflow_only'}
        packet = self.fresh(plan, request.snapshot_id)
        task_titles = [('staffing-plan', 'Verify eligible staffing changes and donor coverage', 'staffing_manager')]
        if result.get('agency_slots'):
            task_titles.append(('agency-verification', 'Verify agency availability, qualifications and onboarding', 'staffing_manager'))
        if simulation['request']['kind'] == 'overtime':
            task_titles.append(('overtime-acceptance', 'Confirm voluntary overtime acceptance', 'staffing_manager'))
        if result.get('modeled_uncovered_rn_hours', 0) > 0:
            task_titles.append(('residual-gap', 'Review remaining nursing coverage gap', 'staffing_manager'))
        for review in packet['recommended_reviews']:
            if review['id'] == 'review-staffing':
                continue
            role = next((key for key, label in OWNERS.items() if label == review['owner_role']), 'house_supervisor')
            task_titles.append((review['id'], review['task'], role))
        default_due = packet['window']['end']
        staffing_due = min([r['start'] for r in result.get('actions', [])] + [g['start'] for g in packet['metrics']['coverage']['gap_segments']] or [default_due], key=instant)
        due_by_role = {'staffing_manager': staffing_due,
                       'medical_staff_coordinator': min([r['assignment_start'] for r in packet['metrics']['provider']['findings']] or [default_due], key=instant),
                       'access_coordinator': min([r['start'] for r in packet['metrics']['access']['findings']] or [default_due], key=instant)}
        plan['tasks'] = [{'id': key, 'title': title, 'owner_role': role, 'due_at': utc_timestamp(due_by_role.get(role, default_due)),
                          'status': 'open', 'completion_evidence_id': None} for key, title, role in task_titles]
        plan['created_by'] = ACTOR
        return self.store.create(plan, request.idempotency_key, content_hash(request.model_dump(exclude={'idempotency_key'})), ACTOR)

    def change(self, plan_id, request):
        plan = self.store.get(plan_id)
        if request.transition != 'dismiss':
            self.fresh(plan, request.snapshot_id)
        elif request.snapshot_id != plan['snapshot_id']:
            raise WorkflowConflict('Plan belongs to a different investigation snapshot')
        allowed = {'submit': ('draft', 'awaiting_approval'), 'approve': ('awaiting_approval', 'approved'),
                   'simulate_implementation': ('approved', 'simulated_implementation'),
                   'monitor': ('simulated_implementation', 'monitoring'), 'close': ('monitoring', 'closed')}
        def update(body):
            action = request.transition
            if action == 'dismiss':
                if body['state'] in ('closed', 'dismissed') or len(request.note) < 8:
                    raise WorkflowConflict('Dismissal requires an open plan and a reason of at least 8 characters')
                body.update(state='dismissed', dismissal_reason=request.note)
            else:
                source, destination = allowed[action]
                if body['state'] != source:
                    raise WorkflowConflict('This transition is not allowed from the current plan state')
                if action in ('approve', 'simulate_implementation', 'close') and not request.acknowledge_demo:
                    raise WorkflowConflict('Explicit acknowledgement of this demo action is required')
                if action == 'approve':
                    body['approval'] = {'actor': ACTOR, 'at': now(), 'snapshot_id': body['snapshot_id'],
                                        'simulation_id': body['simulation_id'], 'proposal_hash': content_hash(body['proposal'])}
                if action == 'close':
                    if any(t['status'] != 'completed' for t in body['tasks']) or body['proposal'].get('modeled_uncovered_rn_hours', 1) > 0:
                        raise WorkflowConflict('Residual staffing gap or unfinished follow-up tasks prevent closure')
                    if len(request.note) < 8:
                        raise WorkflowConflict('Describe the simulated closure outcome in at least 8 characters')
                    for task in body['tasks']:
                        outcome = self.artifact(task['completion_evidence_id'], 'workflow_task_outcome')
                        if outcome['plan_id'] != plan_id or outcome['task_id'] != task['id'] or outcome.get('snapshot_id') != body['snapshot_id'] or outcome.get('simulated') is not True:
                            raise WorkflowConflict('Task outcome evidence does not match this plan')
                    body['closure'] = {'simulated': True, 'note': request.note, 'actor': ACTOR, 'at': now()}
                body['state'] = destination
            return {'note': request.note, 'simulated': True, 'snapshot_id': body['snapshot_id']}
        return self.store.mutate(plan_id, request.expected_version, ACTOR, request.transition, update)

    def task(self, plan_id, task_id, request, complete=False):
        plan = self.store.get(plan_id)
        self.fresh(plan, request.snapshot_id)
        def update(body):
            task = next((t for t in body['tasks'] if t['id'] == task_id), None)
            if task is None:
                raise LookupError('Task not found')
            if complete:
                if body['state'] != 'monitoring' or task['status'] != 'open' or not request.acknowledge_demo or len(request.note) < 8:
                    raise WorkflowConflict('Simulated completion requires monitoring, an open task, acknowledgement and an outcome note')
                outcome = {'kind': 'workflow_task_outcome', 'schema_version': 1, 'simulated': True,
                           'plan_id': plan_id, 'task_id': task_id, 'snapshot_id': body['snapshot_id'],
                           'actor': ACTOR, 'at': now(), 'note': request.note, 'source_records_changed': False}
                digest = self.evidence.put_json(outcome)
                task.update(status='completed', completion_evidence_id=digest)
                return {'task_id': task_id, 'outcome_evidence_id': digest, 'simulated': True}
            if body['state'] != 'draft' or (request.owner_role is None and request.due_at is None):
                raise WorkflowConflict('Task owner/due edits require a draft plan and at least one change')
            if request.owner_role:
                task['owner_role'] = request.owner_role
            if request.due_at:
                task['due_at'] = request.due_at
            return {'task_id': task_id, 'owner_role': task['owner_role'], 'due_at': task['due_at']}
        return self.store.mutate(plan_id, request.expected_version, ACTOR, 'task_completed' if complete else 'task_updated', update)
