import { useState } from 'react';
import { ArrowUpRight, Search, SlidersHorizontal } from 'lucide-react';
import type { Bundle } from '../types';
import { number, routeHash, unitNames } from '../lib/format';
import { Badge } from './Common';

export default function Investigations({ bundle }: { bundle: Bundle }) {
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const findings = bundle.analysis.units.filter(unit => unit.investigation_id);
  const visible = findings.filter(unit => (filter === 'all' || unit.priority === filter)
    && `${unit.unit_id} ${unitNames[unit.unit_id] || unit.display_name}`.toLowerCase().includes(query.toLowerCase()));
  return <>
    <div className="page-heading"><div><div className="eyebrow">FOLLOW THE SIGNALS</div><h1>Investigations</h1><p>A focused review of what matters in the next 72 hours.</p></div><span className="quiet-chip">{findings.length} investigations</span></div>
    <div className="list-toolbar"><div className="segmented" aria-label="Filter investigations">{[['all', 'All findings'], ['high', 'High priority'], ['informational', 'For review']].map(([value, label]) => <button key={value} className={filter === value ? 'selected' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
      <label className="search"><Search size={16} /><input aria-label="Search departments" placeholder="Search departments" value={query} onChange={event => setQuery(event.target.value)} /></label></div>
    <div className="investigation-list">{visible.map(unit => <a key={unit.investigation_id} className="investigation-row" href={routeHash('investigation', unit.investigation_id!)}>
      <div className={`case-marker ${unit.priority}`}><SlidersHorizontal size={22} /></div><div className="case-content"><div className="row-meta"><span>{unit.unit_id}</span><Badge priority={unit.priority} /></div><h2>{unitNames[unit.unit_id] || unit.display_name} operational readiness</h2>
        <p>{unit.reason_codes.length} related findings · {unit.uncovered_rn_hours > 0 ? `${number(unit.uncovered_rn_hours)} uncovered RN-hours` : 'Reporting context requires review'}</p><div className="case-tags">{unit.reason_codes.map(reason => <span key={reason}>{({ RN_COVERAGE_GAP: 'Staffing coverage', RN_COVERAGE_UNVERIFIED: 'Eligibility verification', OVERTIME_DRIFT: 'Overtime drift', PROVIDER_ASSIGNMENT_EXPOSURE: 'Physician authorization', VENDOR_VISIT_NOT_READY: 'Vendor access', QUALITY_REPORT_RATE_REVIEW: 'Quality reporting' } as Record<string, string>)[reason] || reason}</span>)}</div></div><ArrowUpRight size={21} className="row-arrow" /></a>)}</div>
    {visible.length === 0 ? <div className="empty-panel"><Search size={26} /><h2>No matching investigations</h2><p>Try another department or select all findings.</p></div> : null}
  </>;
}
