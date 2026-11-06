import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

const storageKey = 'sympulse.theme.v1';
type Theme = 'light' | 'dark';
function readPreference(): Theme | null {
  try {
    const value = window.localStorage.getItem(storageKey);
    return value === 'light' || value === 'dark' ? value : null;
  } catch { return null; }
}

export default function ThemeToggle() {
  const [preference, setPreference] = useState(readPreference);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);
  const theme = preference ?? (systemDark ? 'dark' : 'light');
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: dark)');
    const syncSystem = () => setSystemDark(query?.matches ?? false);
    const syncStorage = (event: StorageEvent) => {
      if (event.key === storageKey || event.key === null) setPreference(readPreference());
    };
    query?.addEventListener('change', syncSystem);
    window.addEventListener('storage', syncStorage);
    return () => { query?.removeEventListener('change', syncSystem); window.removeEventListener('storage', syncStorage); };
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'dark' ? '#131018' : '#6100DC');
  }, [theme]);
  const label = theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode';
  return <button type="button" className="icon-button theme-toggle" aria-label={label} title={label} onClick={() => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setPreference(next);
    try { window.localStorage.setItem(storageKey, next); } catch { /* The toggle still works when browser storage is unavailable. */ }
  }}>{theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}</button>;
}
