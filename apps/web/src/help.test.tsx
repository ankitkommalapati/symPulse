import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it } from 'vitest';
import InfoTip from './components/InfoTip';
import { DepartmentCard } from './components/Overview';
import type { UnitSummary } from './types';

it('shows hover help, keeps it available over the help itself, and dismisses on Escape', async () => {
  const user = userEvent.setup();
  render(<InfoTip label="Nursing hours">Three missing nurses for twelve hours is 36 RN-hours.</InfoTip>);
  const button = screen.getByRole('button', { name: 'About Nursing hours' });
  await user.hover(button);
  const help = screen.getByRole('tooltip');
  expect(button).toHaveAttribute('aria-describedby', help.id);
  await user.unhover(button); await user.hover(help);
  await new Promise(resolve => setTimeout(resolve, 200));
  expect(help).toBeVisible();
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
});
it('opens with keyboard focus, pins with Enter, and closes on outside interaction', async () => {
  const user = userEvent.setup(); render(<><InfoTip label="Vendor visits">Counts visits, not documents.</InfoTip><button>Elsewhere</button></>);
  await user.tab();
  expect(screen.getByRole('tooltip')).toHaveTextContent('Counts visits, not documents.');
  await user.keyboard('{Enter}');
  await user.unhover(screen.getByRole('button', { name: 'About Vendor visits' }));
  expect(screen.getByRole('button', { name: 'About Vendor visits' })).toHaveAttribute('aria-expanded', 'true');
  await user.click(screen.getByRole('button', { name: 'Elsewhere' }));
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
});
it('toggles click help and closes it when focus moves away', async () => {
  const user = userEvent.setup(); render(<><InfoTip label="Priority">An operational review priority.</InfoTip><button>Next control</button></>);
  const button = screen.getByRole('button', { name: 'About Priority' });
  await user.click(button); expect(screen.getByRole('tooltip')).toBeVisible();
  await user.click(button); expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  await user.tab(); await user.tab({ shift: true });
  expect(screen.getByRole('tooltip')).toBeVisible();
  await user.tab(); expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
});
const unit: UnitSummary = { unit_id: 'ED', display_name: 'Emergency Department', facility_id: 'FAC-01', investigation_id: null, priority: 'none', reason_codes: [], coverage_status: 'covered', uncovered_rn_hours: 0, provider_exposure_hours: 0, vendor_visits_not_ready: 0, overtime_drift: false, quality_report_review: false, data_issues: [], status: 'no_current_finding' };
it('explains a no-finding department without presenting an all-clear', async () => {
  const user = userEvent.setup(); render(<DepartmentCard unit={unit} />);
  expect(screen.getByText('No issues detected by current checks')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'About Emergency Department' }));
  expect(screen.getByRole('tooltip')).toHaveTextContent('does not guarantee the department is problem-free');
  expect(screen.getByRole('tooltip')).toHaveTextContent('selected snapshot');
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
});
it('keeps missing-data uncertainty separate from a no-finding department', async () => {
  const user = userEvent.setup(); render(<DepartmentCard unit={{ ...unit, status: 'insufficient_data', priority: 'review_required' }} />);
  expect(screen.getByText('Assessment needs more data')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'About Emergency Department' }));
  expect(within(screen.getByRole('tooltip')).getByText(/Some records or eligibility checks are incomplete/)).toBeVisible();
  expect(screen.queryByText('No issues detected by current checks')).not.toBeInTheDocument();
});
