import { useEffect, useRef, useState } from 'react';
import { ArrowRight, FileCheck2, Sparkles } from 'lucide-react';
import type { Packet, Resource } from '../types';
import { withClock } from '../lib/api';
import { ErrorState, Loading } from './Common';
interface Statement { id?: string; text: string; owner_role?: string; evidence_group_ids: string[]; simulation_id?: string }
interface BriefData { status: 'model_selected' | 'fallback'; fallback_reason: string | null; question_text: string;
 summary: Statement; observations: Statement[]; hypotheses: Statement[]; unknowns: Statement[];
 recommended_actions: Statement[]; remaining_risks: Statement[]; returned_model: string | null;
 prompt_version: string; artifact_url: string; generated_at: string; cache_hit: boolean }
const questions = [['overview', 'What should I know?'], ['staffing', 'What supports the staffing concern?'], ['connections', 'Why are these signals together?'], ['limits', 'What can we not conclude?'], ['remaining', 'What still needs attention?']];
export default function Brief({ packet, openEvidence, simulationId }: { packet: Packet; openEvidence?: (group: string) => void; simulationId?: string }) {
 const [question, setQuestion] = useState(simulationId ? 'simulation' : 'overview');
 const [resource, setResource] = useState<Resource<BriefData>>({ status: 'loading' });
 const [revision, setRevision] = useState(0);
 const generation = useRef(0);
 useEffect(() => {
  const controller = new AbortController(); const current = ++generation.current;
  setResource({ status: 'loading' });
  fetch(withClock(`/api/investigations/${encodeURIComponent(packet.id)}/explain`, packet.as_of), {
   method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' },
   body: JSON.stringify({ snapshot_id: packet.snapshot_id, question, simulation_id: simulationId || null }),
  }).then(async response => { const body = await response.json(); if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'The explanation could not be loaded.'); return body as BriefData; })
   .then(data => { if (!controller.signal.aborted && current === generation.current) setResource({ status: 'ready', data }); })
   .catch(error => { if (!controller.signal.aborted) setResource({ status: 'error', message: error.message }); });
  return () => controller.abort();
 }, [packet.id, packet.snapshot_id, packet.as_of, question, simulationId, revision]);
 function statements(items: Statement[], hypothesis = false) { return <ul className="brief-statements">{items.map((item, index) => <li key={item.id || index}>{hypothesis ? <strong>Unconfirmed hypothesis · </strong> : null}{item.owner_role ? <strong>{item.owner_role} · </strong> : null}{item.text}{item.simulation_id ? <a className="text-link" href={`/api/artifacts/${item.simulation_id}`} target="_blank" rel="noreferrer">Inspect saved simulation<ArrowRight size={13} /></a> : null}{item.evidence_group_ids.map(group => openEvidence ? <button key={group} className="text-button" onClick={() => openEvidence(group)}>Inspect supporting evidence<ArrowRight size={13} /></button> : null)}</li>)}</ul>; }
 return <section className="panel brief-panel"><div className="panel-heading"><div><span className="eyebrow">UNDERSTAND THE EVIDENCE</span><h2><Sparkles size={19} />Investigation brief</h2><p>Explanations use verified statements. Measurements and constraints come from the operational engine.</p></div></div>
  {!simulationId ? <div className="brief-questions" aria-label="Investigation questions">{questions.map(([id, label]) => <button key={id} aria-pressed={id === question} onClick={() => setQuestion(id)}>{label}</button>)}</div> : null}
  {resource.status === 'loading' ? <Loading label="Preparing the evidence brief…" /> : resource.status === 'error' ? <ErrorState message={resource.message} retry={() => setRevision(value => value + 1)} /> : <>
   <div className="brief-label"><FileCheck2 size={15} /><strong>{resource.data.status === 'model_selected' ? 'AI-organized evidence brief' : 'Rule-based evidence brief · fallback'}</strong></div>
   {resource.data.status === 'fallback' ? <p className="small-text muted">{resource.data.fallback_reason === 'not_configured' ? 'No language model is configured. This brief is composed directly from verified findings.' : 'Model output was unavailable or failed validation. Verified findings are shown instead.'}</p> : <p className="small-text muted">The model arranged certified statements. It did not calculate measurements or establish causes.</p>}
   <h3 className="brief-question">{resource.data.question_text}</h3><p className="brief-summary">{resource.data.summary.text}</p>
   {resource.data.observations.length ? <><h3>What the records establish</h3>{statements(resource.data.observations)}</> : null}
   {resource.data.hypotheses.length ? <><h3>Possible contributing context</h3>{statements(resource.data.hypotheses, true)}</> : null}
   <h3>Limits and unknowns</h3>{statements(resource.data.unknowns)}
   {resource.data.recommended_actions.length ? <><h3>Suggested reviews</h3>{statements(resource.data.recommended_actions)}</> : null}
   <h3>What remains open</h3>{statements(resource.data.remaining_risks)}
   <details className="brief-provenance"><summary>Explanation provenance</summary><p>{resource.data.returned_model ? `Returned model: ${resource.data.returned_model}. ` : ''}Prompt contract: {resource.data.prompt_version}. Generated: {resource.data.generated_at}. {resource.data.cache_hit ? 'Reused the matching saved brief.' : 'Saved with this investigation snapshot.'}</p><a className="text-link" href={resource.data.artifact_url} target="_blank" rel="noreferrer">Open saved explanation evidence<ArrowRight size={14} /></a></details>
  </>}
 </section>;
}
