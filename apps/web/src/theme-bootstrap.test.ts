import source from '../public/assets/theme.js?raw';
import { expect, it } from 'vitest';
it.each([
  ['light', true, 'light'], ['dark', false, 'dark'], [null, true, 'dark'], [null, false, 'light'],
])('applies saved=%s systemDark=%s before React starts', (saved, systemDark, expected) => {
  const document = { documentElement: { dataset: {} as Record<string, string> }, querySelector: () => null };
  new Function('window', 'document', source)({ localStorage: { getItem: () => saved }, matchMedia: () => ({ matches: systemDark }) }, document);
  expect(document.documentElement.dataset.theme).toBe(expected);
});
it('initializes safely when storage access itself throws', () => {
  const document = { documentElement: { dataset: {} as Record<string, string> }, querySelector: () => null };
  new Function('window', 'document', source)({ get localStorage() { throw new Error('Blocked'); }, matchMedia: () => ({ matches: true }) }, document);
  expect(document.documentElement.dataset.theme).toBe('dark');
});
