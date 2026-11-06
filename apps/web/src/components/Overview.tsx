import { Activity, ArrowRight, ArrowUpRight, Building2, CalendarClock, CircleCheck, Layers3, ShieldCheck, Users } from 'lucide-react';
import type { Bundle, UnitSummary } from '../types';
import { number, routeHash, unitNames } from '../lib/format';
import { Badge } from './Common';
import InfoTip from './InfoTip';

export function DepartmentCard({ unit }: { unit: UnitSummary }) {
  const label = unitNames[unit.unit_id] || unit.display_name;
  const description = ({
    ICU: 'The Intensive Care Unit cares for patients who need intensive monitoring and specialist support.',
    STEPDOWN: 'Step-down provides closer monitoring than a general ward for patients who no longer need intensive care.',
    ED: 'The Emergency Department assesses urgent, unscheduled care needs.',
    MEDSURG: 'Medical / Surgical provides general inpatient care for medical conditions and recovery after surgery.',
    SURGERY: 'Surgery coordinates operating-room care and the staff and services needed for scheduled procedures.',
    REHAB: 'Rehabilitation supports recovery of function and independence after illness or injury.',
  } as Record<string, string>)[unit.unit_id] || 'This card summarizes the department’s recorded operational signals.';
  const status = unit.status === 'insufficient_data'
    ? 'Some records or eligibility checks are incomplete, so this department needs a data review.'
    : unit.investigation_id
      ? `${unit.reason_codes.length} operational findings or review signals are grouped for this department. Open the investigation for the evidence and limits.`
      : 'No issues were detected by the current staffing, overtime, physician authorization, vendor-access and quality-reporting checks. This does not guarantee the department is problem-free.';
  return <article className={`department-card ${unit.priority === 'high' ? 'department-alert' : ''}`}>
    <div className="department-top"><span className="unit-symbol"><Building2 size={18} /></span><Badge priority={unit.priority} /></div>
    <div className="department-title"><h3>{label}</h3><InfoTip label={label}>{`${description} ${status} Results use only the records known at the selected snapshot. Upcoming staffing, authorization and visits are checked over 72 hours; overtime and reporting use historical comparison windows.`}</InfoTip></div><p className="department-description">{unit.unit_id === 'ICU' ? 'Critical care' : 'Hospital operations'}</p>
    <div className="department-domains" aria-label="Detected concerns by domain">
      {[['Workforce', unit.uncovered_rn_hours > 0 || unit.overtime_drift], ['Provider', unit.provider_exposure_hours > 0],
        ['Quality', unit.quality_report_review], ['Access', unit.vendor_visits_not_ready > 0]].map(([name, active]) =>
        <span key={String(name)} className={active ? 'domain-concern' : ''}><i />{name}</span>)}
    </div>
    {unit.investigation_id ? <a className="card-link" href={routeHash('investigation', unit.investigation_id)}>Review {unit.priority === 'informational' ? 'reporting trend' : 'investigation'}<ArrowUpRight size={16} /></a>
      : <div className="card-note"><CircleCheck size={14} />{unit.status === 'insufficient_data' ? 'Assessment needs more data' : 'No issues detected by current checks'}</div>}
  </article>;
}

export default function Overview({ bundle }: { bundle: Bundle }) {
  const { units } = bundle.analysis;
  const investigations = units.filter(unit => unit.investigation_id);
  const high = investigations.filter(unit => unit.priority === 'high');
  const focus = high[0] || investigations[0];
  const total = (field: 'uncovered_rn_hours' | 'provider_exposure_hours' | 'vendor_visits_not_ready') => units.reduce((sum, unit) => sum + unit[field], 0);
  return <>
    <div className="page-heading"><div><div className="eyebrow">THE BIG PICTURE</div><h1>Your next 72 hours.</h1><p>Connected signals. Clear priorities. Evidence you can follow.</p></div><span className="quiet-chip"><Layers3 size={14} />{units.length} departments in view</span></div>
    {bundle.analysis.data_quality.completeness_limited ? <div className="notice warning">Some source relationships or inputs need review. These findings do not represent a complete assessment.</div> : null}
    <section className="metric-strip" aria-label="Operational summary">
      <div><span className="metric-icon amber"><Activity size={19} /></span><span className="metric-label">High-priority investigations<InfoTip label="High-priority investigations">Department investigations that need prompt operational review. A confirmed nursing shortage or physician authorization gap appears alongside another readiness concern. This is a review priority, not a prediction of patient harm.</InfoTip></span><strong>{high.length}</strong><small>Requiring an operational review</small></div>
      <div><span className="metric-icon green"><Users size={19} /></span><span className="metric-label">Uncovered nursing hours<InfoTip label="Uncovered nursing hours">The total nursing time not established as covered by eligible, available staff in the recorded plan for the next 72 hours. Three missing nurses for a 12-hour shift means 36 RN-hours. Unverified eligibility can also contribute; inspect the investigation to distinguish it from confirmed shortages.</InfoTip></span><strong>{number(total('uncovered_rn_hours'))}<em>RN-hours</em></strong><small>Against recorded staffing requirements</small></div>
      <div><span className="metric-icon blue"><ShieldCheck size={19} /></span><span className="metric-label">Physician authorization gaps<InfoTip label="Physician authorization gaps">Scheduled physician hours in the next 72 hours that are not covered by recorded, valid privileges for the relevant facility and service. A pending renewal alone does not create a gap if the existing privileges remain valid throughout the assignment.</InfoTip></span><strong>{number(total('provider_exposure_hours'))}<em>hours</em></strong><small>Across the upcoming 72-hour window</small></div>
      <div><span className="metric-icon purple"><CalendarClock size={19} /></span><span className="metric-label">Vendor visits not ready<InfoTip label="Vendor visits not ready">The number of upcoming visits with at least one required facility credential or approval not established as valid for the visit. It counts visits, not missing documents, and does not mean equipment has failed.</InfoTip></span><strong>{total('vendor_visits_not_ready')}<em>visits</em></strong><small>With incomplete credential approval</small></div>
    </section>
    {focus ? <section className="focus-card">
      <div className="focus-copy"><div className="focus-eyebrow"><span className="pulse-dot" />PRIORITY IN FOCUS<InfoTip label="Priority in focus">An investigation highlighted to guide your next review. A high-priority investigation is shown when available; otherwise another available investigation is shown. Pulse connects findings by department and review window; their overlap does not establish a common cause.</InfoTip></div><h2>{unitNames[focus.unit_id] || focus.display_name}<br />needs a closer look.</h2>
        <p>{focus.uncovered_rn_hours > 0 ? `${number(focus.uncovered_rn_hours)} RN-hours are not established as covered in the upcoming plan.` : 'Related operational findings warrant a coordinated review.'} Pulse has brought the supporting signals into one investigation.</p>
        <a className="button lime" href={routeHash('investigation', focus.investigation_id!)}>Open investigation<ArrowRight size={17} /></a><span className="focus-footnote">Evidence-backed · Human review required</span>
      </div>
      <div className="signal-map" aria-label="Operational signals joined by department and time">
        <div className="signal-node node-workforce"><Users size={17} /><span>Workforce<strong>{focus.overtime_drift ? 'Overtime drift' : 'Coverage review'}</strong></span><i className={focus.overtime_drift || focus.uncovered_rn_hours > 0 ? 'lit' : ''} /></div>
        <div className="signal-node node-provider"><ShieldCheck size={17} /><span>Provider<strong>{focus.provider_exposure_hours > 0 ? 'Authorization gap' : 'No exposure found'}</strong></span><i className={focus.provider_exposure_hours > 0 ? 'lit' : ''} /></div>
        <div className="signal-center"><Activity size={31} /><strong>{focus.unit_id}</strong><small>Shared context</small></div>
        <div className="signal-node node-quality"><Activity size={17} /><span>Quality & Safety<strong>{focus.quality_report_review ? 'Reporting trend' : 'Reporting context'}</strong></span><i className={focus.quality_report_review ? 'lit' : ''} /></div>
        <div className="signal-node node-access"><CalendarClock size={17} /><span>Access<strong>{focus.vendor_visits_not_ready > 0 ? 'Visit not ready' : 'No visit concern'}</strong></span><i className={focus.vendor_visits_not_ready > 0 ? 'lit' : ''} /></div>
        <span className="map-caption">One department. An overlapping operational window.</span>
      </div>
    </section> : <section className="empty-panel"><CircleCheck size={28} /><h2>No current investigation</h2><p>No issues were detected by the current checks at this snapshot. This is limited to the available records and checks; it is not an all-clear.</p></section>}
    <section className="section"><div className="section-heading"><div><h2>Across your departments</h2><p>Review detected concerns and the evidence behind them. No current finding means no issue was detected by these checks, not that a department is guaranteed problem-free.</p></div><a href="#investigations" className="text-link">All investigations<ArrowRight size={15} /></a></div>
      <div className="department-grid">{units.map(unit => <DepartmentCard key={`${unit.facility_id}:${unit.unit_id}`} unit={unit} />)}</div>
    </section>
    <div className="principle-note"><ShieldCheck size={16} /><span>Operational decision support. Every finding is grounded in the selected snapshot; no clinical risk or causal relationship is inferred.</span></div>
  </>;
}
