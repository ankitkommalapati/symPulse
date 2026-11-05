export const unitNames: Record<string, string> = {
  ICU: 'Intensive Care Unit', STEPDOWN: 'Step-down', ED: 'Emergency Department',
  MEDSURG: 'Medical / Surgical', SURGERY: 'Surgery', REHAB: 'Rehabilitation',
};
export const sourceNames: Record<string, string> = {
  workforce: 'Workforce', provider: 'Provider', physician_scheduling: 'Physician Scheduling',
  quality: 'Quality & Safety', access: 'Access', planning_context: 'Planning context',
};
export const groupNames: Record<string, string> = {
  workforce_coverage: 'Staffing coverage', overtime_drift: 'Overtime trend', provider_readiness: 'Physician authorization',
  access_readiness: 'Vendor access', quality_reports: 'Quality reporting', entity_relationships: 'Connected records',
};
export function number(value: number, digits = 0) {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
}
export function percent(value: number | null) { return value === null ? 'Unavailable' : `${number(value * 100, 1)}%`; }
export function dateTime(value: string, zone: string, options?: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat('en-US', { timeZone: zone, month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit', ...options }).format(new Date(value));
}
export function day(value: string) {
  return new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric' })
    .format(new Date(value.length === 10 ? `${value}T12:00:00Z` : value));
}
export function readable(value: string) { return value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()); }
export function routeHash(page: string, id?: string) { return id ? `#investigation/${encodeURIComponent(id)}` : `#${page}`; }
export function readRoute(): import('../types').Route {
  const hash = location.hash.slice(1);
  if (hash.startsWith('investigation/')) {
    try { return { page: 'investigation', id: decodeURIComponent(hash.slice(14)) }; }
    catch { return { page: 'investigations' }; }
  }
  return { page: hash === 'investigations' || hash === 'sources' || hash === 'verification' ? hash : 'overview' };
}
