import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import Brief from './components/Brief';
import type { Packet } from './types';
const packet = { id: 'FAC-01:ICU:readiness', as_of: '2026-11-05T14:00:00Z', snapshot_id: 'a'.repeat(64) } as Packet;
const data = { status: 'fallback', fallback_reason: 'not_configured', question_text: 'What should I know?', summary: { text: 'Review the recorded plan.', evidence_group_ids: [] },
 observations: [{ id: 'staffing', text: 'The known plan leaves 36 RN-hours uncovered.', evidence_group_ids: ['workforce_coverage'] }], hypotheses: [], unknowns: [{ text: 'Causality is unconfirmed.', evidence_group_ids: [] }], recommended_actions: [], remaining_risks: [], returned_model: null, prompt_version: 'test', artifact_url: '/api/artifacts/saved', generated_at: '2026-11-05', cache_hit: false };
afterEach(() => vi.unstubAllGlobals());
it('labels fallback honestly and traces a statement to evidence', async () => {
 vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(data)))));
 const open = vi.fn(); const user = userEvent.setup(); render(<Brief packet={packet} openEvidence={open} />);
 expect(await screen.findByText('Rule-based evidence brief · fallback')).toBeVisible();
 await user.click(screen.getByRole('button', { name: 'Inspect supporting evidence' })); expect(open).toHaveBeenCalledWith('workforce_coverage');
 expect(screen.getByText('Causality is unconfirmed.')).toBeVisible();
});
it('uses bounded question IDs and the selected investigation snapshot', async () => {
 const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(data)))); vi.stubGlobal('fetch', fetch);
 const user = userEvent.setup(); render(<Brief packet={packet} />); await screen.findByText('Rule-based evidence brief · fallback');
 await user.click(screen.getByRole('button', { name: 'What can we not conclude?' }));
 await screen.findByText('Rule-based evidence brief · fallback');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ snapshot_id: packet.snapshot_id, question: 'limits', simulation_id: null });
});
it('distinguishes AI selection from calculating facts', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...data, status: 'model_selected', fallback_reason: null, returned_model: 'test-version' }))));
 render(<Brief packet={packet} />); expect(await screen.findByText('AI-organized evidence brief')).toBeVisible();
 expect(screen.getByText('The model arranged certified statements. It did not calculate measurements or establish causes.')).toBeVisible();
});
it('shows a failed read without retaining an unsupported brief', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Snapshot changed' }), { status: 409 })));
 render(<Brief packet={packet} />); expect(await screen.findByRole('alert')).toHaveTextContent('Snapshot changed');
 expect(screen.queryByText('36 RN-hours')).not.toBeInTheDocument();
});
