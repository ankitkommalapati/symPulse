import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import type { Packet } from './types';
import Simulation from './components/Simulation';
const digest = 'a'.repeat(64);
const packet = { id: 'FAC-01:ICU:readiness', snapshot_id: digest, as_of: '2026-11-05T14:00:00Z', metrics: { coverage: { uncovered_rn_hours: 36 } } } as Packet;
const plan = { status: 'conditional', actions: [{ employee_id: 'SYN-RN-041', source_unit_id: 'STEPDOWN' }], reasons: [],
 dependencies: ['Agency capacity is hypothetical'], agency_slots: 1, modeled_uncovered_rn_hours: 0,
 gap_under_selected_assumptions: 12, gap_without_unverified_capacity: 12, incremental_cost_usd: 1320,
 baseline_scheduled_cost_usd: 10000, modeled_total_cost_usd: 11320, cost_scope_unit_ids: ['ICU', 'STEPDOWN'],
 donor_checks: [{ unit_id: 'STEPDOWN', uncovered_rn_hours: 0 }] };
const context = { snapshot_id: digest, target_shift: { shift_start: '2026-11-06T13:00:00Z', shift_end: '2026-11-07T01:00:00Z' },
 policy: { minimum_rest_hours: 12, maximum_rolling_24h_hours: 24, maximum_rolling_168h_hours: 60, agency_onboarding_hours: 12 },
 plans: ['reassignment', 'overtime', 'agency', 'hybrid'].map(kind => ({ ...plan, kind })),
 candidates: { reassignment: [{ employee_id: 'SYN-RN-041', eligible: true, reasons: [], source_unit_id: 'STEPDOWN' }, { employee_id: 'SYN-RN-043', eligible: false, reasons: ['ICU competency missing'], source_unit_id: 'STEPDOWN' }], overtime: [] }, modeled_agency_cost_difference_usd: 2640 };
function mock(data = context) {
 const fetch = vi.fn().mockImplementation((url: string) => Promise.resolve(new Response(JSON.stringify(url.includes('/explain') ? { status: 'fallback', fallback_reason: 'not_configured', question_text: 'What would this proposal change?', summary: { text: 'Verified proposal', evidence_group_ids: [] }, observations: [], hypotheses: [], unknowns: [], recommended_actions: [], remaining_risks: [], returned_model: null, prompt_version: 'test', artifact_url: '/api/artifacts/brief', generated_at: '2026-11-05', cache_hit: false } : data))));
 vi.stubGlobal('fetch', fetch); return fetch;
}
afterEach(() => vi.unstubAllGlobals());
it('distinguishes conditional capacity and prevents selecting an excluded nurse', async () => {
 mock(); render(<Simulation packet={packet} zone="America/Chicago" />);
 await screen.findByRole('button', { name: 'Calculate this scenario' });
 expect(screen.getByRole('checkbox', { name: /SYN-RN-043/ })).toBeDisabled();
 expect(screen.getAllByText('12 RN-hours')).toHaveLength(2);
 expect(screen.getByText(/differ by \$2,640/)).toBeVisible();
});
it('marks edited results as stale and submits explicit scenario assumptions', async () => {
 const fetch = mock(); const user = userEvent.setup(); render(<Simulation packet={packet} zone="America/Chicago" />);
 await screen.findByRole('button', { name: 'Calculate this scenario' });
 await user.click(screen.getByRole('checkbox', { name: /Assume qualified agency staff/ }));
 expect(screen.getByText('Calculate again to apply your edited inputs.')).toBeVisible();
 fetch.mockResolvedValueOnce(new Response(JSON.stringify({ result: { ...plan, kind: 'hybrid' }, simulation_id: 'b'.repeat(64), input_snapshot_id: 'c'.repeat(64), artifact_url: '/api/artifacts/test' })));
 await user.click(screen.getByRole('button', { name: 'Calculate this scenario' }));
 await screen.findByRole('link', { name: 'Open saved simulation evidence' });
 const options = fetch.mock.calls[1][1];
 expect(JSON.parse(options.body)).toMatchObject({ snapshot_id: digest, kind: 'hybrid', employee_ids: ['SYN-RN-041'], assume_agency_available: true, agency_slots: 1 });
 expect(screen.queryByText('Calculate again to apply your edited inputs.')).not.toBeInTheDocument();
});
it('blocks mismatched investigation snapshots', async () => {
 mock({ ...context, snapshot_id: 'b'.repeat(64) }); render(<Simulation packet={packet} zone="America/Chicago" />);
 expect(await screen.findByRole('alert')).toHaveTextContent('snapshot changed');
 expect(screen.queryByRole('button', { name: 'Calculate this scenario' })).not.toBeInTheDocument();
});
it('does not turn server rejection into a successful comparison', async () => {
 const fetch = mock(); const user = userEvent.setup(); render(<Simulation packet={packet} zone="America/Chicago" />);
 await screen.findByRole('button', { name: 'Calculate this scenario' });
 fetch.mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Snapshot changed. Refresh.' }), { status: 409 }));
 await user.click(screen.getByRole('button', { name: 'Calculate this scenario' }));
 expect(await screen.findByRole('alert')).toHaveTextContent('Snapshot changed. Refresh.');
 expect(screen.queryByRole('link', { name: 'Open saved simulation evidence' })).not.toBeInTheDocument();
});
it('cancels pending comparison reads when the investigation closes', async () => {
 const fetch = vi.fn().mockImplementation(() => new Promise(() => {})); vi.stubGlobal('fetch', fetch);
 const { unmount } = render(<Simulation packet={packet} zone="America/Chicago" />); unmount();
 await waitFor(() => expect(fetch.mock.calls[0][1].signal.aborted).toBe(true));
});
