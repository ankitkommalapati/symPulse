export type Priority = 'high' | 'medium' | 'informational' | 'review_required' | 'none';
export interface UnitSummary {
  unit_id: string; facility_id: string; display_name: string; investigation_id: string | null;
  priority: Priority; reason_codes: string[]; coverage_status: string; uncovered_rn_hours: number;
  provider_exposure_hours: number; vendor_visits_not_ready: number; overtime_drift: boolean;
  quality_report_review: boolean; data_issues: string[]; status: string;
}
export interface DataQuality {
  relationship_issues: string[]; missing_input_tables: string[];
  source_delivery_freshness: string; completeness_limited: boolean;
}
export interface Analysis {
  as_of: string; engine_version: string; input_hash: string;
  window: { start: string; end: string }; units: UnitSummary[]; data_quality: DataQuality;
}
export interface Meta {
  application: string; version: string; synthetic: boolean; as_of: string; hospital_timezone: string;
}
export interface SourceInventory { table: string; known_records: number; archive_record_versions: number }
export interface Bundle { meta: Meta; analysis: Analysis; sources: SourceInventory[]; hospital: string }
export type SourceRecord = Record<string, unknown> & {
  record_id: string; source_record_id: string; source_system: string;
  record_version: number; available_at: string; source_updated_at: string;
};
export interface EvidenceGroup { id: string; formula: string; record_ids: string[]; input_hash: string }
export interface GapSegment {
  start: string; end: string; required_rns: number; eligible_rns: number; gap_rns: number;
  uncovered_rn_hours: number; eligibility_uncertain: boolean; requirement_record_id: string;
  excluded: { employee_id: string; reason: string; assignment_record_id: string }[];
}
export interface TrendPoint { date: string; share: number | null; overtime_hours: number; paid_hours: number }
export interface ShiftDrift {
  status: string; detected: boolean; first_breach_work_date: string | null; series: TrendPoint[];
  baseline: { start: string; end: string; mean_share: number; residual_sigma: number } | null;
}
export interface Packet {
  id: string; title: string; as_of: string; input_hash: string; snapshot_id: string; artifact_url: string;
  engine_version: string; summary: UnitSummary; window: Analysis['window']; data_quality: DataQuality;
  metrics: {
    coverage: { status: string; required_rn_hours: number; covered_rn_hours: number; uncovered_rn_hours: number;
      unverified_gap_rn_hours: number; gap_segments: GapSegment[]; data_issues: string[]; evidence_group_ids: string[] };
    overtime: { detected: boolean; shifts: Record<string, ShiftDrift>; data_complete: boolean; evidence_group_ids: string[] };
    provider: { uncovered_physician_hours: number; data_issues: string[]; evidence_group_ids: string[];
      findings: { assignment_record_id: string; provider_id: string; assignment_start: string; assignment_end: string;
        uncovered_physician_hours: number; uncovered_intervals: { start: string; end: string }[]; reason: string }[];
      renewal_followups: { renewal_record_id: string; provider_id: string; due_at: string;
        all_evaluated_assignments_covered: boolean; note: string }[] };
    access: { data_issues: string[]; evidence_group_ids: string[]; findings: { visit_record_id: string;
      representative_id: string; start: string; end: string; unapproved_requirements: string[];
      importance: string; reason: string; equipment_outage_asserted: boolean }[] };
    quality: { baseline_reports: number; current_reports: number; baseline_patient_days: number | null;
      current_patient_days: number | null; baseline_rate_per_1000: number | null; current_rate_per_1000: number | null;
      rate_ratio: number | null; review_required: boolean; status: string; interpretation: string;
      reporting_campaign: boolean; reporting_lag_days: number; evidence_group_ids: string[];
      baseline_window: { start: string; end_exclusive: string }; current_window: { start: string; end_exclusive: string } };
  };
  observations: { domain: string; fact: string; evidence_group_ids: string[] }[];
  hypotheses: { text: string; confirmed_cause: boolean; evidence_group_ids: string[] }[];
  unknowns: string[]; recommended_reviews: { id: string; owner_role: string; task: string }[];
  evidence_groups: Record<string, EvidenceGroup>; source_records: Record<string, SourceRecord>;
  source_record_hashes: Record<string, string>;
}
export type Resource<T> = { status: 'loading' } | { status: 'error'; message: string } | { status: 'ready'; data: T };
export type Route = { page: 'overview' } | { page: 'investigations' } | { page: 'sources' } | { page: 'verification' } | { page: 'investigation'; id: string };
