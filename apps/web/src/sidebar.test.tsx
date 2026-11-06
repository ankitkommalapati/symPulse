import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';
vi.mock('./lib/api', async importOriginal => ({ ...await importOriginal<typeof import('./lib/api')>(), useBundle: () => ({ status: 'loading' }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); history.replaceState(null, '', '/'); });
function pointer(fine: boolean) {
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({ matches: query === '(hover: hover) and (pointer: fine)' && fine, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
}
it('reveals navigation on hover and closes on leave without a desktop toggle', async () => {
  pointer(true); const user = userEvent.setup(); render(<App />);
  const sidebar = screen.getByRole('complementary', { name: 'Workspace sidebar' });
  expect(sidebar).toHaveAttribute('data-expanded', 'false');
  expect(screen.queryByRole('button', { name: /Open navigation|Expand sidebar|Collapse sidebar/ })).not.toBeInTheDocument();
  await user.hover(sidebar); expect(sidebar).toHaveAttribute('data-expanded', 'true');
  await user.unhover(sidebar); expect(sidebar).toHaveAttribute('data-expanded', 'false');
  expect(screen.getByRole('link', { name: 'Data sources' })).toHaveAttribute('href', '#sources');
  expect(screen.queryByText('OPERATIONAL INTELLIGENCE')).not.toBeInTheDocument();
});
it('expands for keyboard navigation and closes after focus leaves', async () => {
  pointer(true); const user = userEvent.setup(); render(<App />);
  const sidebar = screen.getByRole('complementary', { name: 'Workspace sidebar' });
  await user.tab(); await user.tab();
  expect(screen.getByRole('link', { name: 'symPulse home' })).toHaveFocus();
  expect(sidebar).toHaveAttribute('data-expanded', 'true');
  for (let i = 0; i < 5; i++) await user.tab();
  expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toHaveFocus();
  expect(sidebar).toHaveAttribute('data-expanded', 'false');
});
it('offers touch navigation without requiring hover', async () => {
  pointer(false); const user = userEvent.setup(); render(<App />);
  await user.click(screen.getByRole('button', { name: 'Open navigation' }));
  expect(screen.getByRole('button', { name: 'Close navigation' })).toHaveAttribute('aria-expanded', 'true');
  await user.click(screen.getByRole('button', { name: 'Close navigation' }));
  expect(screen.getByRole('complementary', { name: 'Workspace sidebar' })).toHaveAttribute('data-expanded', 'false');
});
