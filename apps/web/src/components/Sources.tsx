import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Database, FileText, Fingerprint, Search } from 'lucide-react';
import type { Bundle, Resource, SourceRecord } from '../types';
import { fetchJson, withClock } from '../lib/api';
import { number, readable } from '../lib/format';
import { ErrorState, Loading } from './Common';
import type { DrawerSelection } from './EvidenceDrawer';

const groups = [
  { name: 'Workforce', description: 'Schedules, qualifications, availability and paid time.', tables: ['employees', 'employee_qualifications', 'staffing_requirements', 'workforce_assignments', 'unavailability', 'paid_time'] },
  { name: 'Provider', description: 'Provider records, privilege grants and renewal cases.', tables: ['providers', 'privilege_grants', 'renewal_cases'] },
  { name: 'Physician Scheduling', description: 'Confirmed physician service assignments.', tables: ['physician_assignments'] },
  { name: 'Quality & Safety', description: 'Reported events and their known revisions.', tables: ['quality_events'] },
  { name: 'Access', description: 'Representatives, facility requirements and planned visits.', tables: ['vendors', 'vendor_representatives', 'vendor_credentials', 'access_policy_requirements', 'vendor_visits'] },
  { name: 'Planning context', description: 'Hospital context, source relationships and activity denominators.', tables: ['facilities', 'units', 'entity_crosswalk', 'unit_activity', 'service_dependencies'] },
];

function TableBrowser({ table, clock, total, openDrawer, zone }: { table: string; clock: string; total: number; openDrawer: (selection: DrawerSelection) => void; zone: string }) {
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState<Resource<SourceRecord[]>>({ status: 'loading' });
  const [revision, setRevision] = useState(0);
  const [recordError, setRecordError] = useState('');
  const [opening, setOpening] = useState('');
  const inspection = useRef<AbortController | null>(null);
  useEffect(() => () => inspection.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    fetchJson<{ items: SourceRecord[] }>(withClock(`/api/records/${table}?limit=20&offset=${offset}`, clock), controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ status: 'ready', data: data.items }); })
      .catch(error => { if (!controller.signal.aborted) setState({ status: 'error', message: error.message }); });
    return () => controller.abort();
  }, [table, clock, offset, revision]);
  async function inspect(record: SourceRecord) {
    inspection.current?.abort();
    const controller = new AbortController();
    inspection.current = controller;
    setOpening(record.record_id); setRecordError('');
    try {
      const saved = await fetchJson<{ record: SourceRecord; as_of: string }>(withClock(`/api/evidence/${encodeURIComponent(record.record_id)}`, clock), controller.signal);
      if (!controller.signal.aborted) openDrawer({ title: readable(table), records: [saved.record], clock: saved.as_of, initialRecord: saved.record.record_id });
    } catch (error) { if (!controller.signal.aborted) setRecordError(error instanceof Error ? error.message : 'The evidence could not be retrieved.'); }
    finally { if (!controller.signal.aborted) setOpening(''); }
  }
  return <section className="panel source-browser"><div className="panel-heading"><div><span className="eyebrow">SOURCE COLLECTION</span><h2>{readable(table)}</h2><p>{number(total)} records known at this snapshot · displayed in {zone}</p></div></div>
    {recordError ? <div role="alert" className="notice warning">{recordError}</div> : null}
    {state.status === 'loading' ? <Loading label="Retrieving source records…" /> : state.status === 'error' ? <ErrorState message={state.message} retry={() => setRevision(value => value + 1)} /> : <>
      <div className="record-list">{state.data.map(record => <button className="record-row" key={record.record_id} onClick={() => inspect(record)} disabled={!!opening}><FileText size={17} /><span><strong>{record.source_record_id}</strong><small>Revision {record.record_version} · {opening === record.record_id ? 'Saving evidence…' : 'Inspect source evidence'}</small></span><ArrowRight size={15} /></button>)}</div>
      {state.data.length === 0 ? <div className="empty-panel small"><p>No records from this collection were known at the selected time.</p></div> : null}
      <div className="pagination"><span>{total ? `${offset + 1}–${Math.min(offset + 20, total)} of ${number(total)}` : '0 records'}</span><div><button className="icon-button" aria-label="Previous source page" disabled={offset === 0} onClick={() => setOffset(value => value - 20)}><ArrowLeft size={16} /></button><button className="icon-button" aria-label="Next source page" disabled={offset + 20 >= total} onClick={() => setOffset(value => value + 20)}><ArrowRight size={16} /></button></div></div>
    </>}
  </section>;
}

export default function Sources({ bundle, openDrawer }: { bundle: Bundle; openDrawer: (selection: DrawerSelection) => void }) {
  const [table, setTable] = useState('');
  const [query, setQuery] = useState('');
  const counts = new Map(bundle.sources.map(source => [source.table, source.known_records]));
  return <>
    <div className="page-heading"><div><div className="eyebrow">TRUST STARTS AT THE SOURCE</div><h1>The evidence behind Pulse.</h1><p>Inspect the operational records included in this snapshot.</p></div><span className="quiet-chip"><Database size={14} />{number(bundle.sources.reduce((sum, source) => sum + source.known_records, 0))} known records</span></div>
    <div className="notice neutral"><Fingerprint size={17} /><span>These are synthetic operational records. Availability is preserved for replay; live source-delivery freshness is not measured.</span></div>
    <div className="sources-layout"><div><label className="search source-search"><Search size={16} /><input aria-label="Search source collections" placeholder="Find a collection" value={query} onChange={event => setQuery(event.target.value)} /></label>
      {groups.map(group => { const tables = group.tables.filter(name => `${group.name} ${name}`.toLowerCase().includes(query.toLowerCase())); return tables.length ? <section className="source-group" key={group.name}><div className="source-group-heading"><h2>{group.name}</h2><span>{number(group.tables.reduce((sum, name) => sum + (counts.get(name) || 0), 0))}</span></div><p>{group.description}</p>{tables.map(name => <button key={name} className={`source-table ${table === name ? 'active' : ''}`} onClick={() => setTable(name)}><span>{readable(name)}</span><small>{number(counts.get(name) || 0)}</small><ArrowRight size={14} /></button>)}</section> : null; })}
    </div><div>{table ? <TableBrowser key={`${table}:${bundle.analysis.as_of}`} table={table} clock={bundle.analysis.as_of} total={counts.get(table) || 0} zone={bundle.meta.hospital_timezone} openDrawer={openDrawer} /> : <div className="source-select-empty"><Database size={35} /><h2>Choose a collection</h2><p>Follow a source record from its original fields to the time it became available.</p></div>}</div></div>
  </>;
}
