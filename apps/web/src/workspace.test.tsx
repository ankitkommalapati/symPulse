import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import type { Bundle, SourceRecord } from './types';
import { fetchJson, useBundle, withClock } from './lib/api';
import { dateTime, readRoute } from './lib/format';
import Overview from './components/Overview';
import TrendChart from './components/TrendChart';
import EvidenceDrawer from './components/EvidenceDrawer';
import SnapshotDialog from './components/SnapshotDialog';
const clock = '2026-11-05T14:00:00Z';
const bundle: Bundle = {
 meta: { application: 'symPulse', version: '0.3.0', synthetic: true, as_of: clock, hospital_timezone: 'America/Chicago' }, hospital: 'St. Mary’s', sources: [],
 analysis: { as_of: clock, engine_version: 'test', input_hash: 'hash', window: { start: clock, end: '2026-11-08T14:00:00Z' },
 data_quality: { relationship_issues: [], missing_input_tables: [], source_delivery_freshness: 'not_measured', completeness_limited: false },
 units: [{ unit_id: 'ICU', facility_id: 'FAC-01', display_name: 'ICU', investigation_id: 'FAC-01:ICU:readiness', priority: 'high', reason_codes: ['coverage'], coverage_status: 'gap', uncovered_rn_hours: 36, provider_exposure_hours: 19, vendor_visits_not_ready: 1, overtime_drift: true, quality_report_review: true, data_issues: [], status: 'concern' }] },
};
afterEach(() => { vi.unstubAllGlobals(); history.replaceState(null, '', '/'); });
it('links actual measured concerns to a specific investigation', () => {
 render(<Overview bundle={bundle} />);
 expect(screen.getByRole('link', { name: 'Open investigation' })).toHaveAttribute('href', '#investigation/FAC-01%3AICU%3Areadiness');
 expect(screen.getByText(/36 RN-hours are not established/)).toBeVisible();
 expect(screen.getByText('Authorization gap')).toBeVisible();
});
it('retains data limitations in the overview', () => {
 render(<Overview bundle={{ ...bundle, analysis: { ...bundle.analysis, data_quality: { ...bundle.analysis.data_quality, completeness_limited: true } } }} />);
 expect(screen.getByText(/do not represent a complete assessment/)).toBeVisible();
});
it('handles encoded investigation links and malformed URL recovery', () => {
 location.hash = '#investigation/FAC-01%3AICU%3Areadiness'; expect(readRoute()).toEqual({ page: 'investigation', id: 'FAC-01:ICU:readiness' });
 location.hash = '#investigation/%ZZ'; expect(readRoute()).toEqual({ page: 'investigations' });
});
it('shows hospital time and preserves existing query parameters', () => {
 expect(dateTime(clock, 'America/Chicago')).toContain('8:00 AM');
 expect(withClock('/api/records/units?limit=20', clock)).toBe('/api/records/units?limit=20&as_of=2026-11-05T14%3A00%3A00Z');
});
it('surfaces failed API reads instead of treating absent data as zero', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Dataset unavailable' }), { status: 503 })));
 await expect(fetchJson('/api/intelligence/units')).rejects.toThrow('Dataset unavailable');
});
it('cancels old snapshot reads and rejects late stale responses', async () => {
 const pending: { resolve: (value: Response) => void; signal: AbortSignal }[] = [];
 vi.stubGlobal('fetch', vi.fn((_url, options) => new Promise<Response>(resolve => pending.push({ resolve, signal: options.signal }))));
 function Reader({ selected }: { selected: string }) { const result = useBundle(selected, 0); return <div>{result.status === 'ready' ? result.data.analysis.as_of : result.status}</div>; }
 const { rerender } = render(<Reader selected={clock} />); rerender(<Reader selected="2026-11-05T10:00:00Z" />);
 expect(pending.slice(0, 4).every(request => request.signal.aborted)).toBe(true);
 const response = (value: unknown) => new Response(JSON.stringify(value));
 pending[4].resolve(response(bundle.meta)); pending[5].resolve(response({ ...bundle.analysis, as_of: 'earlier' })); pending[6].resolve(response({ items: [] })); pending[7].resolve(response({ items: [{ name: 'Earlier hospital' }] }));
 await screen.findByText('earlier');
 pending[0].resolve(response(bundle.meta)); pending[1].resolve(response(bundle.analysis)); pending[2].resolve(response({ items: [] })); pending[3].resolve(response({ items: [] }));
 await waitFor(() => expect(screen.getByText('earlier')).toBeVisible());
});
it('supports keyboard inspection and does not connect missing chart data', async () => {
 const user = userEvent.setup();
 render(<TrendChart trend={{ status: 'complete', detected: true, first_breach_work_date: '2026-11-03', baseline: { start: '2026-08-07', end: '2026-10-01', mean_share: 0.04, residual_sigma: 0.003 }, series: [{ date: '2026-11-02', share: 0.04, overtime_hours: 4, paid_hours: 100 }, { date: '2026-11-03', share: null, overtime_hours: 0, paid_hours: 0 }, { date: '2026-11-04', share: 0.08, overtime_hours: 8, paid_hours: 100 }] }} />);
 screen.getByRole('group', { name: /Overtime trend chart/ }).focus(); await user.keyboard('{ArrowLeft}'); expect(screen.getByText('Unavailable overtime share')).toBeVisible();
 await user.keyboard('{ArrowLeft}'); expect(screen.getByText('4% overtime share')).toBeVisible(); expect(screen.getByRole('button', { name: 'Previous chart date' })).toBeDisabled();
});
it('paginates and searches saved evidence then inspects its captured revision', async () => {
 const user = userEvent.setup();
 const records = Array.from({ length: 22 }, (_, index) => ({ record_id: `workforce:employees:E${index}`, source_record_id: `E${index}`, source_system: 'workforce', record_version: index === 21 ? 2 : 1, available_at: clock, source_updated_at: clock, job_title: 'RN' } satisfies SourceRecord));
 render(<EvidenceDrawer selection={{ title: 'Staffing coverage', clock, records }} zone="America/Chicago" close={vi.fn()} />);
 expect(screen.getByText('1–20 of 22')).toBeVisible(); await user.click(screen.getByRole('button', { name: 'Next evidence page' })); expect(screen.getByText('21–22 of 22')).toBeVisible();
 await user.type(screen.getByRole('textbox', { name: 'Search evidence records' }), 'E21'); expect(screen.getByText('1–1 of 1')).toBeVisible();
 await user.click(screen.getByRole('button', { name: /E21.*revision 2/ })); expect(screen.getByRole('heading', { name: 'Source record' })).toBeVisible(); expect(screen.getByText('RN')).toBeVisible();
});
it('replays four hours earlier as an explicit UTC instant', async () => {
 const change = vi.fn(); const user = userEvent.setup(); render(<SnapshotDialog current={clock} defaultClock={clock} zone="America/Chicago" close={vi.fn()} change={change} />);
 await user.click(screen.getByRole('button', { name: /Four hours earlier/ })); expect(change).toHaveBeenCalledWith('2026-11-05T10:00:00.000Z');
});
it('interprets custom UTC input independently of viewer timezone', () => {
 const change = vi.fn(); render(<SnapshotDialog current={clock} defaultClock={clock} zone="America/Chicago" close={vi.fn()} change={change} />);
 fireEvent.change(screen.getByLabelText('Custom knowledge time (UTC)'), { target: { value: '2026-11-04T18:30' } });
 fireEvent.submit(screen.getByRole('button', { name: 'Review this snapshot' }).closest('form')!); expect(change).toHaveBeenCalledWith('2026-11-04T18:30:00.000Z');
});

it('supplies explanations for all summary metrics, focus and each department', async () => {
 const user = userEvent.setup(); render(<Overview bundle={bundle} />);
 for (const label of ['High-priority investigations', 'Uncovered nursing hours', 'Physician authorization gaps', 'Vendor visits not ready', 'Priority in focus', 'Intensive Care Unit']) {
  await user.click(screen.getByRole('button', { name: `About ${label}` }));
  expect(screen.getByRole('tooltip')).toBeVisible();
  await user.keyboard('{Escape}');
 }
});
