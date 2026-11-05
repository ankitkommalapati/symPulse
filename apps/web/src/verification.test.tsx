import { render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import Verification from './components/Verification';
const report = { generated_at: '2026-11-05', application_version: '0.7.0', status: 'review_ready_with_verification_gaps', checks: [],
 fixture_evaluation: { case_count: 30, status_counts: { passed: 26, partial: 3, failed: 1, error: 0 },
 families: [{ family: 'simulation', split: 'holdout', primary_decision: 'feasible', cases: 4, fully_matched: 4, partially_evaluated: 0, failed: 0, primary_scored: 4, true_positive: 0, false_positive: 0, false_negative: 0, true_negative: 4, precision: null, recall: null }],
 cases: [{ case_id: 'ACCESS-late_arrival', family: 'access', status: 'failed', mismatches: { finding: { expected: false, observed: true } }, unsupported_fields: {}, error: null }] },
 rehearsals: [{ repeat: 1, status: 'passed', step_count: 20, facts: { rn_gap: 36, reassignment_residual_rn_hours: 12, agency_incremental_cost_usd: 3960, hybrid_incremental_cost_usd: 1320, task_count: 5 }, atomic_reason_count: 6, investigation_count: 2 }],
 timings_seconds: Object.fromEntries(['analysis_cold', 'analysis_cached', 'simulation_context', 'simulate_hybrid', 'brief_fallback', 'brief_cached', 'approve', 'close'].map(key => [key, { samples: [0.1, 0.2, 0.3], min: 0.1, max: 0.3 }])), targets: { simulation_under_one_second: false }, claim_limits: ['Not a clinical study'],
 release_gates: { visual_browser_verified: false, live_model_verified: false, all_fixture_cases_fully_matched: false }, three_runs_identical_core_facts: true };
afterEach(() => vi.unstubAllGlobals());
it('shows known discrepancies and does not turn undefined scores into 100 percent', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ report, matches_selected_snapshot: true }))));
 render(<Verification clock="2026-11-05T14:00:00Z" />);
 await screen.findByRole('heading', { name: 'Evidence of the demonstration.' });
 expect(screen.getByText('ACCESS-late_arrival · failed')).toBeVisible();
 expect(screen.getAllByText('—')).toHaveLength(2);
 expect(screen.getAllByText('Outstanding')).toHaveLength(3);
 expect(screen.getByText('not met')).toBeVisible();
});
it('warns when recorded measurements use another operational snapshot', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ report, matches_selected_snapshot: false }))));
 render(<Verification clock="2026-11-05T10:00:00Z" />);
 expect(await screen.findByText(/report uses a different operational snapshot/)).toBeVisible();
});
it('provides a real failure state when no report is available', async () => {
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Demo verification report is unavailable' }), { status: 503 })));
 render(<Verification clock="2026-11-05T14:00:00Z" />);
 expect(await screen.findByRole('alert')).toHaveTextContent('Demo verification report is unavailable');
});
