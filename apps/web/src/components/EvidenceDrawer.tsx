import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, ChevronLeft, FileText, Fingerprint, Search, X } from 'lucide-react';
import type { EvidenceGroup, SourceRecord } from '../types';
import { dateTime, groupNames, number, readable, sourceNames } from '../lib/format';

export interface DrawerSelection {
  title: string; records: SourceRecord[]; group?: EvidenceGroup; clock: string;
  initialRecord?: string; hashes?: Record<string, string>;
}
export default function EvidenceDrawer({ selection, zone, close }: { selection: DrawerSelection; zone: string; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [recordId, setRecordId] = useState(selection.initialRecord || '');
  const records = useMemo(() => selection.records.filter(row => `${row.record_id} ${JSON.stringify(row)}`.toLowerCase().includes(query.toLowerCase())), [selection.records, query]);
  const record = selection.records.find(row => row.record_id === recordId);
  useEffect(() => { const node = dialog.current; node?.showModal(); return () => { if (node?.open) node.close(); }; }, []);
  return <dialog ref={dialog} className="evidence-drawer" onCancel={event => { event.preventDefault(); close(); }} onClick={event => { if (event.target === dialog.current) { const box = dialog.current.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right) close(); } }} aria-labelledby="evidence-title">
    <div className="drawer-header"><div><span className="eyebrow">EVIDENCE WORKSPACE</span><h2 id="evidence-title">{record ? 'Source record' : selection.title}</h2></div><button className="icon-button" aria-label="Close evidence" onClick={close}><X size={21} /></button></div>
    <div className="drawer-body">
      <div className="snapshot-note"><Fingerprint size={16} /><span>Captured evidence · known by {dateTime(selection.clock, zone)} ({zone})</span></div>
      {record ? <>
        <button className="text-button back-records" onClick={() => setRecordId('')}><ChevronLeft size={15} />Back to records</button>
        <div className="record-heading"><span className="unit-symbol"><FileText size={20} /></span><div><span>{sourceNames[record.source_system] || readable(record.source_system)}</span><h3>{record.source_record_id}</h3></div></div>
        <dl className="record-meta"><div><dt>Record revision</dt><dd>{record.record_version}</dd></div><div><dt>Available to Pulse</dt><dd>{dateTime(record.available_at, zone)}</dd></div><div><dt>Source updated</dt><dd>{dateTime(record.source_updated_at, zone)}</dd></div><div><dt>Source collection</dt><dd>{readable(record.record_id.split(':')[1] || '')}</dd></div></dl>
        <h3 className="drawer-section-title">What the source says</h3><dl className="payload-fields">{Object.entries(record).filter(([key]) => !['record_id', 'source_record_id', 'source_system', 'record_version', 'source_updated_at', 'available_at', 'synthetic', 'is_deleted'].includes(key)).map(([key, value]) => <div key={key}><dt>{readable(key)}</dt><dd>{value === null ? 'Not recorded' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl>
        <details className="verification-details"><summary>Verification details</summary><p className="mono">{record.record_id}</p>{selection.hashes?.[record.record_id] ? <><span>Captured record SHA-256</span><p className="mono">{selection.hashes[record.record_id]}</p></> : null}<pre>{JSON.stringify(record, null, 2)}</pre></details>
      </> : <>
        {selection.group ? <div className="formula-panel"><span className="eyebrow">HOW THIS FINDING WAS CALCULATED</span><p>{selection.group.formula}</p></div> : null}
        <div className="records-toolbar"><strong>{number(selection.records.length)} supporting records</strong><label className="search"><Search size={15} /><input aria-label="Search evidence records" placeholder="Search evidence" value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} /></label></div>
        <div className="record-list">{records.slice(page * 20, (page + 1) * 20).map(row => <button className="record-row" key={row.record_id} onClick={() => setRecordId(row.record_id)}><FileText size={17} /><span><strong>{row.source_record_id}</strong><small>{sourceNames[row.source_system] || row.source_system} · {readable(row.record_id.split(':')[1])} · revision {row.record_version}</small></span><ArrowRight size={15} /></button>)}</div>
        {records.length === 0 ? <div className="empty-panel small"><p>No supporting records match this search.</p></div> : null}
        <div className="pagination"><span>{records.length ? `${page * 20 + 1}–${Math.min((page + 1) * 20, records.length)} of ${number(records.length)}` : '0 records'}</span><div><button className="icon-button" aria-label="Previous evidence page" disabled={page === 0} onClick={() => setPage(value => value - 1)}><ArrowLeft size={16} /></button><button className="icon-button" aria-label="Next evidence page" disabled={(page + 1) * 20 >= records.length} onClick={() => setPage(value => value + 1)}><ArrowRight size={16} /></button></div></div>
        {selection.group ? <details className="verification-details"><summary>Aggregate verification</summary><p>{groupNames[selection.group.id] || selection.group.id}</p><span>Input SHA-256</span><p className="mono">{selection.group.input_hash}</p></details> : null}
      </>}
    </div>
  </dialog>;
}
