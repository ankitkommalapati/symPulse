import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
vi.mock('./lib/api', async importOriginal => ({ ...await importOriginal<typeof import('./lib/api')>(), useBundle: () => ({ status: 'loading' }) }));
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); } });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); history.replaceState(null, '', '/'); });
it('collapses, retains accessible navigation, survives snapshot refresh and restores its saved choice', async () => {
  const user = userEvent.setup(); const view = render(<App />);
  expect(screen.queryByText('OPERATIONAL INTELLIGENCE')).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'symPulse home' })).toHaveTextContent('symPulse');
  await user.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toHaveAttribute('aria-expanded', 'false');
  expect(screen.getByRole('navigation')).toHaveAttribute('id', 'workspace-navigation');
  expect(screen.getByRole('link', { name: 'Data sources' })).toHaveAttribute('href', '#sources');
  expect(window.localStorage.getItem('sympulse.sidebar.v1')).toBe('collapsed');
  act(() => { location.hash = '#sources'; window.dispatchEvent(new HashChangeEvent('hashchange')); });
  expect(screen.getByRole('link', { name: 'Data sources' })).toHaveAttribute('aria-current', 'page');
  await user.click(screen.getByRole('button', { name: 'Refresh current snapshot' }));
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeVisible();
  view.unmount(); render(<App />);
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Expand sidebar' }));
  expect(screen.getByRole('button', { name: 'Collapse sidebar' })).toHaveAttribute('aria-expanded', 'true');
});
it('keeps the collapse control usable if saving preferences is blocked', async () => {
  vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => { throw new Error('Blocked'); });
  vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => { throw new Error('Blocked'); });
  const user = userEvent.setup(); render(<App />);
  await user.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
  expect(screen.getByRole('button', { name: 'Expand sidebar' })).toBeVisible();
});
