import { lazy, Suspense, useState } from 'react';
import { Activity, ArrowLeft, ArrowUpRight, CalendarClock, Check, ChevronRight, Download, FileCheck2, Fingerprint, Info, Link2, ShieldCheck, Users } from 'lucide-react';
import type { Bundle, Packet } from '../types';
import { usePacket } from '../lib/api';
import { dateTime, day, groupNames, number, readable, unitNames } from '../lib/format';
import { Badge, ErrorState, EvidenceButton, Loading } from './Common';
import type { DrawerSelection } from './EvidenceDrawer';
import TrendChart from './TrendChart';
const Simulation = lazy(() => import('./Simulation'));

function Timeline({ packet, zone, open }: { packet: Packet; zone: string; open: (group: string, record?: string) => void }) {
  const start = new Date(packet.window.start).getTime(), end = new Date(packet.window.end).getTime();
  const rows = [
    { label: 'Nursing coverage', group: 'workforce_coverage', uncertain: packet.metrics.coverage.status === 'insufficient_data', color: 'amber', periods: packet.metrics.coverage.gap_segments.map(segment => ({ start: segment.start, end: segment.end, label: `${segment.gap_rns} RNs below requirement`, record: segment.requirement_record_id })) },
    { label: 'Physician authorization', group: 'provider_readiness', uncertain: packet.metrics.provider.data_issues.length > 0, color: 'blue', periods: packet.metrics.provider.findings.flatMap(finding => finding.uncovered_intervals.map(interval => ({ ...interval, label: 'Uncovered authorization', record: finding.assignment_record_id }))) },
    { label: 'Vendor access', group: 'access_readiness', uncertain: packet.metrics.access.data_issues.length > 0, color: 'purple', periods: packet.metrics.access.findings.map(finding => ({ start: finding.start, end: finding.end, label: 'Visit not ready', record: finding.visit_record_id })) },
  ];
  return <section className="panel timeline-panel"><div className="panel-heading"><div><h2>The upcoming window</h2><p>Related commitments, aligned to the same department and time.</p></div><span className="quiet-chip">72 hours</span></div>
    <div className="timeline"><div className="timeline-axis"><span />{[0, 1, 2, 3].map(index => <span key={index}>{dateTime(new Date(start + (end - start) * index / 3).toISOString(), zone)}</span>)}</div>
      {rows.map(row => <div className="timeline-row" key={row.group}><button onClick={() => open(row.group)}>{row.label}<ArrowUpRight size={12} /></button><div className="timeline-track">{row.periods.length ? row.periods.map((period, index) => { const left = Math.max(0, (new Date(period.start).getTime() - start) / (end - start) * 100); const right = Math.min(100, (new Date(period.end).getTime() - start) / (end - start) * 100); return <button key={index} className={`timeline-bar ${row.color}`} style={{ left: `${left}%`, width: `${Math.max(1.5, right - left)}%` }} aria-label={`${row.label}: ${period.label}, ${dateTime(period.start, zone)} to ${dateTime(period.end, zone)}`} title={`${period.label} · ${dateTime(period.start, zone)}`} onClick={() => open(row.group, period.record)} />; }) : <span className="timeline-clear">{row.uncertain ? 'Readiness requires further verification' : 'No exposure detected in the recorded plan'}</span>}</div></div>)}
    </div><p className="panel-footnote">Overtime and quality-report history provide context below; they are not predictions of future incidents.</p>
  </section>;
}

function download(packet: Packet) {
  const blob = new Blob([JSON.stringify(packet, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob); const link = document.createElement('a');
  link.href = url; link.download = `pulse-${packet.summary.unit_id.toLowerCase()}-${packet.snapshot_id.slice(0, 12)}.json`;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function InvestigationBody({ packet, bundle, openDrawer }: { packet: Packet; bundle: Bundle; openDrawer: (selection: DrawerSelection) => void }) {
  const [tab, setTab] = useState('findings');
  const [shift, setShift] = useState('DAY');
  const zone = bundle.meta.hospital_timezone;
  const { coverage, provider, access, quality, overtime } = packet.metrics;
  const open = (id: string, initialRecord?: string) => {
    const group = packet.evidence_groups[id];
    openDrawer({ title: groupNames[id] || readable(id), records: group.record_ids.map(key => packet.source_records[key]).filter(Boolean),
      group, clock: packet.as_of, initialRecord, hashes: packet.source_record_hashes });
  };
  const firstGap = coverage.gap_segments[0];
  const firstProvider = provider.findings[0];
  return <>
    <nav className="breadcrumbs" aria-label="Breadcrumb"><a href="#overview">Overview</a><ChevronRight size={13} /><a href="#investigations">Investigations</a><ChevronRight size={13} /><span>{packet.summary.unit_id}</span></nav>
    <div className="page-heading investigation-heading"><div><div className="title-with-badge"><h1>{packet.summary.unit_id} operational readiness</h1><Badge priority={packet.summary.priority} /></div><p>{unitNames[packet.summary.unit_id] || packet.summary.display_name} · {dateTime(packet.window.start, zone)} – {dateTime(packet.window.end, zone)}</p></div><button className="button secondary" onClick={() => download(packet)}><Download size={16} />Download evidence</button></div>
    <div className="case-summary"><span className="case-summary-icon"><Link2 size={22} /></span><div><h2>One investigation. {packet.summary.reason_codes.length} connected findings.</h2><p>Shared department and timing connect these signals. The records support a coordinated review; they do not establish that one issue caused another.</p></div><span className="review-chip"><FileCheck2 size={15} />Human review required</span></div>
    {packet.data_quality.completeness_limited || packet.summary.data_issues.length ? <div className="notice warning">The assessment has data limitations. Review the uncertainty section before drawing conclusions.</div> : null}
    <section className="case-metrics" aria-label="Investigation measurements">
      <button onClick={() => open('workforce_coverage')}><span className="metric-icon green"><Users size={19} /></span><span>Nursing coverage</span><strong>{number(coverage.uncovered_rn_hours)}<em>RN-hours</em></strong><small>{coverage.unverified_gap_rn_hours > 0 ? `${number(coverage.unverified_gap_rn_hours)} hours need eligibility verification` : firstGap ? `${firstGap.gap_rns} RNs short · ${day(firstGap.start)} shift` : 'No recorded coverage deficit'}</small><span className="metric-evidence">Inspect staffing records<ArrowUpRight size={13} /></span></button>
      <button onClick={() => open('provider_readiness')}><span className="metric-icon blue"><ShieldCheck size={19} /></span><span>Physician authorization</span><strong>{number(provider.uncovered_physician_hours)}<em>hours</em></strong><small>{firstProvider ? `${number(firstProvider.uncovered_physician_hours)} hours in the first affected assignment` : provider.data_issues.length ? 'Authorization requires verification' : 'No uncovered assignment found'}</small><span className="metric-evidence">Inspect grants & assignments<ArrowUpRight size={13} /></span></button>
      <button onClick={() => open('access_readiness')}><span className="metric-icon purple"><CalendarClock size={19} /></span><span>Vendor readiness</span><strong>{access.findings.length}<em>visits</em></strong><small>{access.findings.length ? 'With incomplete credential approval' : access.data_issues.length ? 'Visit requirements need verification' : 'No visit-readiness concern found'}</small><span className="metric-evidence">Inspect access requirements<ArrowUpRight size={13} /></span></button>
      <button onClick={() => open('quality_reports')}><span className="metric-icon amber"><Activity size={19} /></span><span>Near-miss reporting</span><strong>{quality.current_rate_per_1000 === null ? '—' : number(quality.current_rate_per_1000, 1)}<em>per 1,000</em></strong><small>{quality.baseline_rate_per_1000 === null ? 'Patient-day denominator unavailable' : `vs ${number(quality.baseline_rate_per_1000, 1)} in the prior window · patient-days`}</small><span className="metric-evidence">Inspect reporting context<ArrowUpRight size={13} /></span></button>
    </section>
    <div className="workspace-tabs" role="tablist" aria-label="Investigation sections">{[['findings', 'Findings & context'], ['evidence', 'Evidence library'], ['uncertainty', 'Limits & uncertainty'], ['simulation', 'Compare interventions']].map(([value, label], index, tabs) => <button key={value} role="tab" tabIndex={tab === value ? 0 : -1} aria-selected={tab === value} aria-controls={`panel-${value}`} id={`tab-${value}`} onClick={() => setTab(value)} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      setTab(tabs[next][0]);
      document.getElementById(`tab-${tabs[next][0]}`)?.focus();
    }}>{label}{value === 'evidence' ? <span>{Object.keys(packet.source_records).length}</span> : null}</button>)}</div>
    <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
      {tab === 'simulation' ? <Suspense fallback={<Loading label="Loading staffing comparisons…" />}><Simulation packet={packet} zone={zone} /></Suspense> : tab === 'findings' ? <>
        <Timeline packet={packet} zone={zone} open={open} />
        <div className="investigation-columns"><div className="main-column">
          <section className="panel"><div className="panel-heading"><div><span className="eyebrow">BEHAVIORAL DRIFT</span><h2>A gradual change, made visible.</h2><p>Overtime share against a fixed, weekday-adjusted baseline.</p></div><div className="segmented compact" aria-label="Choose shift">{['DAY', 'NIGHT'].map(value => <button key={value} className={shift === value ? 'selected' : ''} aria-pressed={shift === value} onClick={() => setShift(value)}>{value === 'DAY' ? 'Day shift' : 'Night shift'}</button>)}</div></div>
            <TrendChart key={shift} trend={overtime.shifts[shift]} /><div className="chart-callout"><Activity size={16} /><span>{overtime.shifts[shift].detected ? 'A sustained increase crossed the configured drift threshold.' : 'No sustained drift was detected in this shift series.'} {overtime.shifts[shift].first_breach_work_date ? `First qualifying work date: ${day(overtime.shifts[shift].first_breach_work_date!)}.` : ''}</span></div><EvidenceButton onClick={() => open('overtime_drift')}>View calculation & paid-time records</EvidenceButton>
          </section>
          <section className="panel"><div className="panel-heading"><div><span className="eyebrow">WHAT THE RECORDS SUPPORT</span><h2>Facts before explanations.</h2></div></div><div className="observation-list">{packet.observations.map((observation, index) => <div key={index}><span className="observation-number">{String(index + 1).padStart(2, '0')}</span><div><span className="eyebrow">{observation.domain}</span><h3>{observation.fact}</h3><EvidenceButton onClick={() => open(observation.evidence_group_ids[0])} /></div></div>)}</div>
            {packet.hypotheses.map((hypothesis, index) => <div className="hypothesis" key={index}><Info size={17} /><div><strong>Possible contributing context · unconfirmed</strong><p>{hypothesis.text}. This is a review hypothesis, not an established root cause.</p></div></div>)}
          </section>
        </div><aside className="side-column">
          <section className="panel review-panel"><div className="panel-heading"><div><span className="eyebrow">NEXT CONVERSATIONS</span><h2>Suggested reviews</h2></div></div>{packet.recommended_reviews.map((review, index) => <div className="review-item" key={review.id}><span>{index + 1}</span><div><strong>{review.owner_role}</strong><p>{review.task}.</p></div></div>)}<p className="muted small-text">These are review suggestions. No assignment, approval or source record has been changed.</p></section>
          <section className="panel renewal-panel"><span className="eyebrow">IMPORTANT DISTINCTION</span><h2>Pending does not mean expired.</h2>{provider.renewal_followups.map(followup => <div className="renewal-item" key={followup.renewal_record_id}><span className={followup.all_evaluated_assignments_covered ? 'renewal-good' : 'renewal-warning'}>{followup.all_evaluated_assignments_covered ? <Check size={15} /> : <Info size={15} />}</span><div><strong>{followup.provider_id}</strong><p>{followup.all_evaluated_assignments_covered ? 'Current grant covers all evaluated assignments.' : 'An upcoming assignment extends beyond recorded authorization.'}</p><EvidenceButton onClick={() => open('provider_readiness', followup.renewal_record_id)}>Inspect renewal</EvidenceButton></div></div>)}{provider.renewal_followups.length === 0 ? <p>No pending renewals are included in this investigation.</p> : null}</section>
          <section className="panel trust-panel"><Fingerprint size={22} /><h3>Evidence, preserved.</h3><p>This investigation is saved with the exact source revisions behind it.</p><span className="snapshot-id">{packet.snapshot_id.slice(0, 16)}</span><button className="text-button" onClick={() => setTab('evidence')}>Explore the evidence<ArrowUpRight size={14} /></button></section>
        </aside></div>
      </> : tab === 'evidence' ? <section className="panel evidence-library"><div className="panel-heading"><div><h2>Follow every finding to its source.</h2><p>These records are captured with this investigation, not re-queried from a later snapshot.</p></div></div><div className="evidence-group-grid">{Object.values(packet.evidence_groups).map(group => <button key={group.id} onClick={() => open(group.id)}><span className="unit-symbol"><FileCheck2 size={20} /></span><h3>{groupNames[group.id] || readable(group.id)}</h3><p>{number(group.record_ids.length)} supporting records</p><span className="text-link">Inspect evidence<ArrowUpRight size={14} /></span></button>)}</div></section>
        : <section className="panel uncertainty-panel"><span className="eyebrow">KEEP THE CONCLUSION HONEST</span><h2>What this investigation cannot establish</h2><ul>{packet.unknowns.map((unknown, index) => <li key={index}><Info size={17} />{unknown}</li>)}</ul><div className="formula-panel"><strong>Quality reporting context</strong><p>{quality.interpretation}.</p><p>Comparison windows: {day(quality.baseline_window.start)}–{day(quality.baseline_window.end_exclusive)} and {day(quality.current_window.start)}–{day(quality.current_window.end_exclusive)}, ending exclusively on the dates shown. The latest {quality.reporting_lag_days} local calendar dates are excluded.</p><p>Baseline: {quality.baseline_reports} reports / {quality.baseline_patient_days ?? 'unknown'} patient-days. Current: {quality.current_reports} reports / {quality.current_patient_days ?? 'unknown'} patient-days.</p>{quality.reporting_campaign ? <p>A reporting campaign is recorded in the current window.</p> : null}</div></section>}
    </div>
  </>;
}

export default function Investigation({ id, bundle, revision, retry, openDrawer }: { id: string; bundle: Bundle; revision: number; retry: () => void; openDrawer: (selection: DrawerSelection) => void }) {
  const resource = usePacket(id, bundle.analysis.as_of, revision);
  if (resource.status === 'loading') return <Loading label="Assembling the investigation…" />;
  if (resource.status === 'error') return <><a className="text-link" href="#investigations"><ArrowLeft size={15} />Back to investigations</a><ErrorState message={resource.message} retry={retry} /></>;
  return <InvestigationBody packet={resource.data} bundle={bundle} openDrawer={openDrawer} />;
}
