import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, ClipboardCheck, RefreshCw } from 'lucide-react';
import type { Packet, Resource } from '../types';
import { fetchJson, withClock } from '../lib/api';
import { dateTime, number, readable } from '../lib/format';
import { ErrorState, Loading } from './Common';
interface Task { id: string; title: string; owner_role: string; due_at: string; status: string; completion_evidence_id: string | null }
interface Plan { id: string; version: number; state: string; snapshot_id: string; simulation_id: string; title: string; updated_at: string;
 proposal: { kind: string; status: string; actions: { employee_id: string; source_unit_id: string | null; start: string; end: string }[]; agency_slots: number; modeled_uncovered_rn_hours: number; gap_without_unverified_capacity: number; incremental_cost_usd: number; dependencies: string[] };
 tasks: Task[]; closure?: { note: string }; audit?: { version: number; action: string; recorded_at: string; actor: { name: string }; details: { note?: string; task_id?: string }; event_hash: string }[] }
interface Meta { actor: { name: string }; owners: Record<string, string> }
async function write<T>(url: string, method: string, body: unknown, signal?: AbortSignal): Promise<T> {
 const response = await fetch(url, { method, signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
 const data = await response.json(); if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The workflow request is invalid.'); return data;
}
export function PlanCreator({ packet, simulationId, onCreated }: { packet: Packet; simulationId: string; onCreated: () => void }) {
 const [busy, setBusy] = useState(false); const [error, setError] = useState('');
 const key = useRef(crypto.randomUUID()); const controller = useRef<AbortController | null>(null);
 useEffect(() => () => controller.current?.abort(), []);
 async function create() {
  const pending = new AbortController(); controller.current = pending; setBusy(true); setError('');
  try { await write(withClock('/api/plans', packet.as_of), 'POST', { simulation_id: simulationId, snapshot_id: packet.snapshot_id, idempotency_key: key.current }, pending.signal); if (!pending.signal.aborted) onCreated(); }
  catch (error) { if (!pending.signal.aborted) setError(error instanceof Error ? error.message : 'The plan could not be saved.'); }
  finally { if (!pending.signal.aborted) setBusy(false); }
 }
 return <section className="panel plan-create"><ClipboardCheck size={22} /><div><h2>Turn this scenario into a reviewable proposal.</h2><p>Save the exact assignments, assumptions and follow-up tasks as a draft. Approval comes next.</p>{error ? <p role="alert">{error}</p> : null}</div><button className="button primary" disabled={busy} onClick={create}>{busy ? 'Saving draft…' : 'Save draft plan'}<ArrowRight size={16} /></button></section>;
}
function TaskRow({ task, plan, meta, zone, busy, complete, edit }: { task: Task; plan: Plan; meta: Meta; zone: string; busy: boolean; complete: (id: string) => void; edit: (id: string, body: unknown) => void }) {
 const [owner, setOwner] = useState(task.owner_role); const [due, setDue] = useState(new Date(task.due_at).toISOString().slice(0, 16));
 const editable = plan.state === 'draft';
 return <article className="workflow-task"><div className="workflow-task-title"><span className={`task-state ${task.status}`}>{task.status === 'completed' ? <Check size={16} /> : <ClipboardCheck size={16} />}</span><h3>{task.title}</h3><span className="quiet-chip">{task.status === 'completed' ? 'Simulated completion' : 'Open'}</span></div>
  {editable ? <div className="task-edit"><label>Task owner<select aria-label={`Owner for ${task.id}`} value={owner} disabled={busy} onChange={event => setOwner(event.target.value)}>{Object.entries(meta.owners).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>Due time (UTC)<input aria-label={`Due time for ${task.id}`} type="datetime-local" value={due} disabled={busy} onChange={event => setDue(event.target.value)} /></label><button className="button secondary" disabled={busy || !due || (owner === task.owner_role && due === new Date(task.due_at).toISOString().slice(0, 16))} onClick={() => edit(task.id, { owner_role: owner, due_at: `${due}:00Z` })}>Save task details</button></div>
  : <p>{meta.owners[task.owner_role]} · Due {dateTime(task.due_at, zone)}</p>}
  {plan.state === 'monitoring' && task.status === 'open' ? <button className="text-button" disabled={busy} onClick={() => complete(task.id)}>Record simulated task completion<ArrowRight size={14} /></button> : null}
  {task.completion_evidence_id ? <a className="text-link" href={`/api/artifacts/${task.completion_evidence_id}`} target="_blank" rel="noreferrer">Inspect simulated outcome<ArrowRight size={14} /></a> : null}
 </article>;
}
const next: Record<string, [string, string]> = { draft: ['submit', 'Submit for review'], awaiting_approval: ['approve', 'Approve demo plan'], approved: ['simulate_implementation', 'Record simulated implementation'], simulated_implementation: ['monitor', 'Start monitoring'], monitoring: ['close', 'Close with simulated outcomes'] };
export default function Workflow({ packet, zone }: { packet: Packet; zone: string }) {
 const [resource, setResource] = useState<Resource<{ plans: Plan[]; meta: Meta }>>({ status: 'loading' });
 const [selected, setSelected] = useState(''); const [detail, setDetail] = useState<Resource<Plan>>({ status: 'loading' });
 const [revision, setRevision] = useState(0); const [busy, setBusy] = useState(false); const [note, setNote] = useState(''); const [ack, setAck] = useState(false); const [error, setError] = useState('');
 const operation = useRef<AbortController | null>(null);
 useEffect(() => { const controller = new AbortController(); setResource({ status: 'loading' });
  Promise.all([fetchJson<{ items: Plan[] }>(`/api/plans?investigation_id=${encodeURIComponent(packet.id)}`, controller.signal), fetchJson<Meta>('/api/workflow/meta', controller.signal)])
   .then(([plans, meta]) => { if (!controller.signal.aborted) { setResource({ status: 'ready', data: { plans: plans.items, meta } }); setSelected(value => plans.items.some(p => p.id === value) ? value : plans.items[0]?.id || ''); } })
   .catch(error => { if (!controller.signal.aborted) setResource({ status: 'error', message: error.message }); });
  return () => { controller.abort(); operation.current?.abort(); };
 }, [packet.id, revision]);
 useEffect(() => { if (!selected) return; const controller = new AbortController(); setDetail({ status: 'loading' }); setError(''); setAck(false); setNote('');
  fetchJson<Plan>(`/api/plans/${selected}`, controller.signal).then(data => { if (!controller.signal.aborted) setDetail({ status: 'ready', data }); }).catch(error => { if (!controller.signal.aborted) setDetail({ status: 'error', message: error.message }); });
  return () => { controller.abort(); operation.current?.abort(); };
 }, [selected, revision]);
 if (resource.status === 'loading') return <Loading label="Loading saved response plans…" />;
 if (resource.status === 'error') return <ErrorState message={resource.message} retry={() => setRevision(v => v + 1)} />;
 const { plans, meta } = resource.data;
 if (!plans.length) return <section className="panel empty-panel"><ClipboardCheck size={28} /><h2>No saved response plans</h2><p>Calculate a staffing scenario in Compare interventions, then save it as a draft for review.</p></section>;
 const plan = detail.status === 'ready' ? detail.data : undefined;
 const stale = plan?.snapshot_id !== packet.snapshot_id;
 async function mutate(path: string, method: string, extras: object) {
  if (!plan) return; const controller = new AbortController(); operation.current = controller; setBusy(true); setError('');
  try { await write(path, method, { expected_version: plan.version, snapshot_id: ('transition' in extras && extras.transition === 'dismiss') ? plan.snapshot_id : packet.snapshot_id, note, acknowledge_demo: ack, ...extras }, controller.signal); if (!controller.signal.aborted) setRevision(v => v + 1); }
  catch (error) { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : 'The plan could not be updated.'); }
  finally { if (!controller.signal.aborted) setBusy(false); }
 }
 const action = plan ? next[plan.state] : undefined;
 const cannotClose = !!plan && (plan.proposal.modeled_uncovered_rn_hours > 0 || plan.tasks.some(t => t.status !== 'completed'));
 return <div className="workflow-workspace"><section className="panel"><div className="panel-heading"><div><span className="eyebrow">FOLLOW THROUGH, WITH A RECORD</span><h2>Response plans</h2><p>Demo reviewer: {meta.actor.name}. Approval records a local decision; external schedules and source findings stay unchanged.</p></div><button className="icon-button" aria-label="Reload plans" disabled={busy} onClick={() => setRevision(v => v + 1)}><RefreshCw size={17} /></button></div><label className="plan-picker">Saved proposal<select aria-label="Saved response plan" value={selected} disabled={busy} onChange={event => setSelected(event.target.value)}>{plans.map(p => <option key={p.id} value={p.id}>{readable(p.proposal.kind)} · {readable(p.state)} · {p.id.slice(0, 8)}</option>)}</select></label></section>
  {detail.status === 'loading' ? <Loading /> : detail.status === 'error' ? <ErrorState message={detail.message} retry={() => setRevision(v => v + 1)} /> : plan ? <>
   {stale ? <div className="notice warning">This plan belongs to another evidence snapshot. Select its original snapshot to review it; edits and approval are disabled here. Dismissal with a reason is still available.</div> : null}
   <section className="panel"><div className="panel-heading"><div><span className="eyebrow">VERSION {plan.version}</span><h2>{readable(plan.proposal.kind)} proposal</h2></div><span className="quiet-chip">{plan.state === 'closed' ? 'Closed · simulated outcome' : readable(plan.state)}</span></div>
    <div className="plan-lifecycle" aria-label="Plan lifecycle">{['draft', 'awaiting_approval', 'approved', 'simulated_implementation', 'monitoring', 'closed'].map(state => <span key={state} className={plan.state === state ? 'active' : ''}>{readable(state)}</span>)}</div>
    <div className="notice neutral">Modeled residual gap: {number(plan.proposal.modeled_uncovered_rn_hours)} RN-hours. Excluding unverified additional capacity: {number(plan.proposal.gap_without_unverified_capacity)} RN-hours. Staffing assumptions remain attached to this proposal.</div>
    <h3>Exact proposed staffing changes</h3><ul className="plan-assignments">{plan.proposal.actions.map(action => <li key={action.employee_id}><strong>{action.employee_id}</strong> · {action.source_unit_id || 'Additional voluntary shift'} → {packet.summary.unit_id}<small>{dateTime(action.start, zone)} – {dateTime(action.end, zone)}</small></li>)}{plan.proposal.agency_slots ? <li>{plan.proposal.agency_slots} hypothetical agency slots · availability, eligibility and onboarding require verification</li> : null}</ul>
    {plan.proposal.dependencies?.map(dependency => <p className="small-text muted" key={dependency}>{dependency}</p>)}
    <a className="text-link" href={`/api/artifacts/${plan.simulation_id}`} target="_blank" rel="noreferrer">Inspect original simulation evidence<ArrowRight size={14} /></a>
   </section>
   <section className="panel"><div className="panel-heading"><div><h2>Follow-up tasks</h2><p>Owner and due times are editable in draft. During monitoring, enter an outcome note and acknowledge the demo action below before recording a task completion.</p></div></div>{plan.tasks.map(task => <TaskRow key={`${task.id}:${plan.version}`} task={task} plan={plan} meta={meta} zone={zone} busy={busy || stale || (plan.state === 'monitoring' && (!ack || note.trim().length < 8))} edit={(id, body) => mutate(`/api/plans/${plan.id}/tasks/${id}`, 'PATCH', body as object)} complete={id => mutate(`/api/plans/${plan.id}/tasks/${id}/complete`, 'POST', {})} />)}</section>
   {!['closed', 'dismissed'].includes(plan.state) ? <section className="panel workflow-controls"><h2>Record the next demo step</h2><label>Reason or simulated outcome note<textarea value={note} disabled={busy} onChange={event => setNote(event.target.value)} maxLength={1000} placeholder="Describe the decision or the simulated follow-up outcome" /></label><label className="check-label"><input type="checkbox" checked={ack} disabled={busy || stale} onChange={event => setAck(event.target.checked)} />I acknowledge this records a demo decision or simulated outcome, with no external changes.</label>
    {error ? <p role="alert" className="notice warning">{error}</p> : null}
    <div className="workflow-buttons">{action ? <button className="button primary" disabled={busy || stale || (['approve', 'simulate_implementation', 'close'].includes(action[0]) && !ack) || (action[0] === 'close' && (cannotClose || note.trim().length < 8))} onClick={() => mutate(`/api/plans/${plan.id}/transition`, 'POST', { transition: action[0] })}>{busy ? 'Saving…' : action[1]}<ArrowRight size={15} /></button> : null}<button className="button secondary" disabled={busy || note.trim().length < 8} onClick={() => mutate(`/api/plans/${plan.id}/transition`, 'POST', { transition: 'dismiss' })}>Dismiss proposal with reason</button></div>
    {plan.state === 'monitoring' && cannotClose ? <p className="small-text muted">This plan stays open while follow-ups are unfinished or its modeled staffing gap remains. A residual gap requires a revised simulation and a new proposal.</p> : null}
   </section> : <section className="panel"><h2>{plan.state === 'closed' ? 'Closed as a simulated workflow outcome' : 'Proposal dismissed'}</h2><p>The operational source investigation remains unchanged.</p></section>}
   <section className="panel"><h2>Audit history</h2><ol className="workflow-audit">{plan.audit?.map(event => <li key={event.version}><div><strong>{readable(event.action)}</strong><span>v{event.version} · {dateTime(event.recorded_at, zone)} · {event.actor.name}</span></div>{event.details.note ? <p>{event.details.note}</p> : null}{event.details.task_id ? <small>Task: {event.details.task_id}</small> : null}<details><summary>Audit identity</summary><code>{event.event_hash}</code></details></li>)}</ol><a className="text-link" href={`/api/plans/${plan.id}`} target="_blank" rel="noreferrer">Open complete plan and audit record<ArrowRight size={14} /></a></section>
  </> : null}
 </div>;
}
