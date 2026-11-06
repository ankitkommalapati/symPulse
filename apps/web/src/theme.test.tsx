import { act, cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import ThemeToggle from './components/ThemeToggle';

const key = 'sympulse.theme.v1';
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', { getItem: (name: string) => values.get(name) ?? null, setItem: (name: string, value: string) => { values.set(name, value); } });
});
afterEach(() => { cleanup(); delete document.documentElement.dataset.theme; vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function systemTheme(dark: boolean) {
  let listener: (() => void) | undefined;
  const query = { matches: dark, addEventListener: vi.fn((_event, callback) => { listener = callback; }), removeEventListener: vi.fn() };
  vi.stubGlobal('matchMedia', vi.fn(() => query));
  return { query, change(value: boolean) { act(() => { query.matches = value; listener?.(); }); } };
}
it('follows system changes until an explicit choice, persists the choice and restores it after remount', async () => {
  const system = systemTheme(false);
  const user = userEvent.setup();
  const view = render(<ThemeToggle />);
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  system.change(true);
  expect(screen.getByRole('button', { name: 'Switch to light mode' })).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Switch to light mode' }));
  expect(window.localStorage.getItem(key)).toBe('light');
  system.change(false); system.change(true);
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  view.unmount(); render(<ThemeToggle />);
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  expect(system.query.removeEventListener).toHaveBeenCalled();
});
it('toggles in both directions with the keyboard and synchronizes other tabs', async () => {
  systemTheme(false); const user = userEvent.setup(); render(<ThemeToggle />);
  screen.getByRole('button', { name: 'Switch to dark mode' }).focus();
  await user.keyboard('{Enter}');
  expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
  await user.keyboard(' ');
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
  act(() => { window.localStorage.setItem(key, 'dark'); window.dispatchEvent(new StorageEvent('storage', { key })); });
  expect(screen.getByRole('button', { name: 'Switch to light mode' })).toBeVisible();
});
it('works without browser storage and falls back from an invalid saved value', async () => {
  systemTheme(true); window.localStorage.setItem(key, 'invalid');
  vi.spyOn(window.localStorage, 'getItem').mockImplementation(() => { throw new Error('Storage blocked'); });
  vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => { throw new Error('Storage blocked'); });
  const user = userEvent.setup(); render(<ThemeToggle />);
  await user.click(screen.getByRole('button', { name: 'Switch to light mode' }));
  expect(document.documentElement).toHaveAttribute('data-theme', 'light');
});
