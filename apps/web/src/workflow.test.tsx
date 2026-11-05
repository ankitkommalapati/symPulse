import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import Workflow, { PlanCreator } from './components/Workflow';
import type { Packet } from './types';
const packet = { id: 'FAC-01:ICU:readiness', as_of: '2026-11-05T14:00:00Z', snapshot_id: 'a'.repeat(64), summary: { unit_id: 'ICU' } } as Packet;
const plan = { id: 'demo-plan', version: 2, state: 'awaiting_approval', snapshot_id: packet.snapshot_id, simulation_id: 'b'.repeat(64), title: 'Staffing response', updated_at: packet.as_of,
 proposal: { kind: 'hybrid', status: 'conditional', actions: [{ employee_id: 'SYN-RN-041', source_unit_id: 'STEPDOWN', start: packet.as_of, end: '2026-11-06T14:00:00Z' }], agency_slots: 1, modeled_uncovered_rn_hours: 0, gap_without_unverified_capacity: 12, incremental_cost_usd: 1320, dependencies: ['Agency availability is unverified'] },
 tasks: [{ id: 'review-staffing', title: 'Verify staffing', owner_role: 'staffing_manager', due_at: packet.as_of, status: 'open', completion_evidence_id: null }],
 audit: [{ version: 1, action: 'created', recorded_at: packet.as_of, actor: { name: 'Demo house supervisor' }, details: {}, event_hash: 'c'.repeat(64) }] };
function mock(value = plan) {
 const fetch = vi.fn().mockImplementation((url: string, options?: RequestInit) => {
  if (options?.method) return Promise.resolve(new Response(JSON.stringify({ detail: 'Plan changed. Reload before continuing.' }), { status: 409 }));
  return Promise.resolve(new Response(JSON.stringify(url === '/api/workflow/meta' ? { actor: { name: 'Demo house supervisor' }, owners: { staffing_manager: 'Staffing manager', house_supervisor: 'House supervisor' } } : url.startsWith('/api/plans?') ? { items: [value] } : value)));
 }); vi.stubGlobal('fetch', fetch); return fetch;
}
afterEach(() => vi.unstubAllGlobals());
it('requires explicit demo acknowledgement and submits the current version', async () => {
 const fetch = mock(); const user = userEvent.setup(); render(<Workflow packet={packet} zone="America/Chicago" />);
 const approve = await screen.findByRole('button', { name: 'Approve demo plan' }); expect(approve).toBeDisabled();
 expect(screen.getByText('SYN-RN-041')).toBeVisible();
 await user.click(screen.getByRole('checkbox', { name: /I acknowledge/ })); await user.click(approve);
 expect(await screen.findByRole('alert')).toHaveTextContent('Plan changed');
 const body = JSON.parse(fetch.mock.calls.find(call => call[1]?.method === 'POST')![1].body);
 expect(body).toMatchObject({ expected_version: 2, snapshot_id: packet.snapshot_id, transition: 'approve', acknowledge_demo: true });
});
it('does not allow closing while a task is open', async () => {
 mock({ ...plan, state: 'monitoring' }); const user = userEvent.setup(); render(<Workflow packet={packet} zone="America/Chicago" />);
 const close = await screen.findByRole('button', { name: 'Close with simulated outcomes' });
 await user.type(screen.getByRole('textbox', { name: 'Reason or simulated outcome note' }), 'Example simulated closure');
 await user.click(screen.getByRole('checkbox', { name: /I acknowledge/ })); expect(close).toBeDisabled();
});
it('disables mutations when viewing another investigation snapshot', async () => {
 mock({ ...plan, snapshot_id: 'd'.repeat(64) }); render(<Workflow packet={packet} zone="America/Chicago" />);
 await screen.findByText(/belongs to another evidence snapshot/);
 expect(screen.getByRole('button', { name: 'Approve demo plan' })).toBeDisabled();
});
it('reuses the draft creation key when retrying a failed save', async () => {
 const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ detail: 'Temporary failure' }), { status: 503 }))); vi.stubGlobal('fetch', fetch);
 const user = userEvent.setup(); render(<PlanCreator packet={packet} simulationId={'b'.repeat(64)} onCreated={vi.fn()} />);
 await user.click(screen.getByRole('button', { name: 'Save draft plan' })); await screen.findByRole('alert');
 await user.click(screen.getByRole('button', { name: 'Save draft plan' }));
 await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
 expect(JSON.parse(fetch.mock.calls[0][1].body).idempotency_key).toBe(JSON.parse(fetch.mock.calls[1][1].body).idempotency_key);
});
