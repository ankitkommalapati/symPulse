import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, FlaskConical, Info, Users } from 'lucide-react';
import type { Packet, Resource } from '../types';
import { fetchJson, withClock } from '../lib/api';
import { dateTime, number } from '../lib/format';
import { ErrorState, Loading } from './Common';

type Kind = 'reassignment' | 'overtime' | 'agency' | 'hybrid';
interface Candidate { employee_id: string; eligible: boolean; reasons: string[]; source_unit_id: string | null }
interface Plan {
 kind: Kind; status: string; actions: { employee_id: string; source_unit_id: string | null }[];
 reasons: string[]; dependencies?: string[]; rejected_candidates?: { employee_id: string; reasons: string[] }[];
 donor_checks?: { unit_id: string; uncovered_rn_hours: number }[]; agency_slots?: number;
 modeled_uncovered_rn_hours?: number; gap_under_selected_assumptions?: number; gap_without_unverified_capacity?: number;
 baseline_scheduled_cost_usd?: number | null; incremental_cost_usd?: number; modeled_total_cost_usd?: number | null;
 cost_scope_unit_ids?: string[]; unresolved?: string[];
}
interface Context { snapshot_id: string; target_shift: { shift_start: string; shift_end: string } | null;
 policy: { minimum_rest_hours: number; maximum_rolling_24h_hours: number; maximum_rolling_168h_hours: number; agency_onboarding_hours: number };
 plans: Plan[]; candidates: Partial<Record<Kind, Candidate[]>>; modeled_agency_cost_difference_usd: number | null }
interface Result { result: Plan; simulation_id: string; artifact_url: string; input_snapshot_id: string }
const labels: Record<Kind, string> = { reassignment: 'Move eligible staff', overtime: 'Voluntary overtime', agency: 'Agency staffing', hybrid: 'Reassignment + agency' };
const usd = (value: number | null | undefined = 0) => value === null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(value);

export default function Simulation({ packet, zone }: { packet: Packet; zone: string }) {
 const [context, setContext] = useState<Resource<Context>>({ status: 'loading' });
 const [revision, setRevision] = useState(0);
 const [kind, setKind] = useState<Kind>('hybrid');
 const [selected, setSelected] = useState<string[] | null>(null);
 const [slots, setSlots] = useState(1);
 const [rate, setRate] = useState('110');
 const [accepted, setAccepted] = useState(false);
 const [agencyAvailable, setAgencyAvailable] = useState(false);
 const [result, setResult] = useState<Result | null>(null);
 const [error, setError] = useState('');
 const [busy, setBusy] = useState(false);
 const [query, setQuery] = useState('');
 const [dirty, setDirty] = useState(false);
 const request = useRef<AbortController | null>(null);
 useEffect(() => {
  const controller = new AbortController();
  setContext({ status: 'loading' });
  fetchJson<Context>(withClock(`/api/investigations/${encodeURIComponent(packet.id)}/simulation`, packet.as_of), controller.signal)
   .then(data => { if (!controller.signal.aborted) setContext({ status: 'ready', data }); })
   .catch(err => { if (!controller.signal.aborted) setContext({ status: 'error', message: err.message }); });
  return () => { controller.abort(); request.current?.abort(); };
 }, [packet.id, packet.as_of, revision]);
 if (context.status === 'loading') return <Loading label="Checking staffing alternatives…" />;
 if (context.status === 'error') return <ErrorState message={context.message} retry={() => setRevision(value => value + 1)} />;
 const data = context.data;
 if (data.snapshot_id !== packet.snapshot_id) return <div role="alert" className="notice warning">The investigation snapshot changed. Refresh the workspace before comparing interventions.</div>;
 if (!data.target_shift) return <section className="panel"><h2>No complete future staffing gap to simulate</h2><p>This snapshot has no supported future shift deficit for comparison.</p></section>;
 const plan = result?.result || data.plans.find(value => value.kind === kind)!;
 const candidates = data.candidates[kind === 'overtime' ? 'overtime' : 'reassignment'] || [];
 const chosen = selected ?? data.plans.find(value => value.kind === kind)!.actions.map(action => action.employee_id);
 const visible = candidates.filter(candidate => `${candidate.employee_id} ${candidate.reasons.join(' ')}`.toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(chosen.includes(b.employee_id)) - Number(chosen.includes(a.employee_id)) || Number(b.eligible) - Number(a.eligible) || a.employee_id.localeCompare(b.employee_id));
 function edit() { setDirty(true); setError(''); }
 function choose(value: Kind) { setKind(value); setSelected(null); setSlots(data.plans.find(p => p.kind === value)?.agency_slots || 0); setResult(null); setDirty(false); setError(''); setAccepted(false); setAgencyAvailable(false); setRate('110'); }
 async function simulate() {
  const numericRate = Number(rate);
  if (rate.trim() === '' || !Number.isFinite(numericRate) || numericRate < 0 || numericRate > 1000) { setError('Enter an agency hourly rate from $0 to $1,000.'); return; }
  request.current?.abort(); const controller = new AbortController(); request.current = controller;
  setBusy(true); setError('');
  try {
   const response = await fetch(withClock(`/api/investigations/${encodeURIComponent(packet.id)}/simulate`, packet.as_of), {
    method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ snapshot_id: packet.snapshot_id, kind, employee_ids: kind === 'agency' ? [] : chosen,
     agency_slots: kind === 'agency' || kind === 'hybrid' ? slots : 0, agency_hourly_rate_usd: numericRate,
     overtime_accepted: accepted, assume_agency_available: agencyAvailable }),
   });
   const body = await response.json();
   if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The simulation request is invalid.');
   if (!controller.signal.aborted) { setResult(body); setDirty(false); }
  } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Simulation could not be completed.'); }
  finally { if (!controller.signal.aborted) setBusy(false); }
 }
 return <div className="simulation-workspace">
  <section className="panel simulation-intro"><div className="eyebrow">EXPLORE BEFORE ACTING</div><h2>What would close the staffing gap?</h2><p>Compare a proposed shift plan for {dateTime(data.target_shift.shift_start, zone)} – {dateTime(data.target_shift.shift_end, zone)}. All results are modeled; no schedule is changed.</p><div className="notice neutral"><Info size={17} /><span>Agency capacity and overtime acceptance are unverified. Scenario assumptions explore possibilities; they do not confirm real staffing.</span></div></section>
  <div className="simulation-options">{data.plans.map(option => <button key={option.kind} className={`panel simulation-option ${kind === option.kind ? 'selected' : ''}`} aria-pressed={kind === option.kind} onClick={() => choose(option.kind)} disabled={busy}><span className="eyebrow">{option.status}</span><h3>{labels[option.kind]}</h3><strong>{option.modeled_uncovered_rn_hours === undefined ? '—' : number(option.modeled_uncovered_rn_hours)}<small> RN-hours remain in modeled plan</small></strong><p>{usd(option.incremental_cost_usd)} incremental coverage cost</p><span>{option.actions.length} internal nurses · {option.agency_slots || 0} agency slots</span></button>)}</div>
  <div className="simulation-layout"><section className="panel"><div className="panel-heading"><div><span className="eyebrow">ADJUST THE PROPOSAL</span><h2>{labels[kind]}</h2></div><FlaskConical size={22} /></div>
   <fieldset disabled={busy} className="simulation-fields">
    {(kind === 'agency' || kind === 'hybrid') ? <><label>Agency slots<select value={slots} onChange={event => { setSlots(Number(event.target.value)); edit(); }}>{[0, 1, 2, 3].map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Agency hourly rate (USD)<input type="number" min="0" max="1000" step="1" value={rate} onChange={event => { setRate(event.target.value); edit(); }} /></label><label className="check-label"><input type="checkbox" checked={agencyAvailable} onChange={event => { setAgencyAvailable(event.target.checked); edit(); }} />Assume qualified agency staff are available and onboarded for this scenario</label></> : null}
    {kind === 'overtime' ? <label className="check-label"><input type="checkbox" checked={accepted} onChange={event => { setAccepted(event.target.checked); edit(); }} />Assume the selected nurses accept voluntary overtime for this scenario</label> : null}
    {kind !== 'agency' ? <><h3><Users size={16} />Internal candidates</h3><label>Search candidates<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Employee ID or exclusion reason" /></label><div className="candidate-list">{visible.slice(0, 24).map(candidate => <label key={candidate.employee_id} className="candidate-row"><input type="checkbox" checked={chosen.includes(candidate.employee_id)} disabled={!candidate.eligible} onChange={event => { setSelected(event.target.checked ? [...chosen, candidate.employee_id] : chosen.filter(value => value !== candidate.employee_id)); edit(); }} /><span><strong>{candidate.employee_id}</strong><small>{candidate.eligible ? candidate.source_unit_id ? `From ${candidate.source_unit_id} · joint capacity checked on simulation` : 'Eligible · acceptance still required' : candidate.reasons.join('; ')}</small></span>{candidate.eligible ? <Check size={15} /> : null}</label>)}</div><p className="small-text muted">Showing {Math.min(visible.length, 24)} of {visible.length} matching candidates. Search to inspect other records. {chosen.length} selected.</p></> : null}
   </fieldset>
   {error ? <div role="alert" className="notice warning">{error}</div> : null}
   <button className="button primary" disabled={busy} onClick={simulate}>{busy ? 'Checking all constraints…' : 'Calculate this scenario'}<ArrowRight size={16} /></button>
   <details className="simulation-policy"><summary>Illustrative staffing policy</summary><p>At least {data.policy.minimum_rest_hours} hours of rest; at most {data.policy.maximum_rolling_24h_hours} hours in any 24 hours and {data.policy.maximum_rolling_168h_hours} hours in any 168 hours. Agency onboarding requires {data.policy.agency_onboarding_hours} hours of lead time. These are demo assumptions.</p></details>
  </section><section className="panel simulation-result" aria-live="polite"><span className="eyebrow">{dirty ? 'LAST CALCULATION · INPUTS CHANGED' : `MODELED RESULT · ${plan.status}`}</span><h2>{labels[plan.kind]}</h2>{dirty ? <p className="notice warning">Calculate again to apply your edited inputs.</p> : null}
   <dl className="simulation-measurements"><div><dt>Original nursing gap · 72 hours</dt><dd>{number(packet.metrics.coverage.uncovered_rn_hours)} RN-hours</dd></div><div><dt>Residual gap if all proposed capacity materializes</dt><dd>{plan.modeled_uncovered_rn_hours === undefined ? 'Unavailable' : `${number(plan.modeled_uncovered_rn_hours)} RN-hours`}</dd></div><div><dt>Gap excluding unverified additional capacity</dt><dd>{plan.gap_without_unverified_capacity === undefined ? 'Unavailable' : `${number(plan.gap_without_unverified_capacity)} RN-hours`}</dd></div><div><dt>Gap under selected scenario assumptions</dt><dd>{plan.gap_under_selected_assumptions === undefined ? 'Unavailable' : `${number(plan.gap_under_selected_assumptions)} RN-hours`}</dd></div><div><dt>Incremental coverage cost</dt><dd>{usd(plan.incremental_cost_usd)}</dd></div><div><dt>Existing scheduled base-pay cost</dt><dd>{usd(plan.baseline_scheduled_cost_usd)}</dd></div><div><dt>Total modeled labor cost</dt><dd>{usd(plan.modeled_total_cost_usd)}</dd></div></dl>
   <p className="small-text muted">Cost scope: {(plan.cost_scope_unit_ids || []).join(' + ')} across 72 hours. Includes scheduled unavailable assignments; existing pay is retained when nurses move. This is an estimate, not payroll or realized savings.</p>
   {plan.donor_checks?.map(check => <p className="donor-check" key={check.unit_id}><Check size={16} />{check.unit_id}: {number(check.uncovered_rn_hours)} uncovered RN-hours after the joint plan</p>)}
   {plan.reasons?.map(reason => <p className="notice warning" key={reason}>{reason}</p>)}
   {plan.dependencies?.map(reason => <p className="notice neutral" key={reason}>{reason}</p>)}
   {plan.rejected_candidates?.length ? <details><summary>{plan.rejected_candidates.length} excluded candidates</summary>{plan.rejected_candidates.map(candidate => <p key={candidate.employee_id}>{candidate.employee_id}: {candidate.reasons.join('; ')}</p>)}</details> : null}
   {result && !dirty ? <p className="simulation-evidence"><a className="text-link" href={result.artifact_url} target="_blank" rel="noreferrer">Open saved simulation evidence<ArrowRight size={14} /></a><br /><a className="text-link" href={`/api/artifacts/${result.input_snapshot_id}`} target="_blank" rel="noreferrer">Inspect captured simulation inputs<ArrowRight size={14} /></a></p> : null}
   <div className="formula-panel"><strong>What remains unresolved</strong><p>Physician authorization, vendor access and quality review still require their own follow-up. A staffing proposal does not close the investigation.</p></div>
  </section></div>
  {data.modeled_agency_cost_difference_usd !== null ? <p className="principle-note">At the default assumptions, agency-only and hybrid plans differ by {usd(data.modeled_agency_cost_difference_usd)} in modeled incremental cost. This comparison assumes the proposed capacity materializes.</p> : null}
 </div>;
}
