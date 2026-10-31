import { derived, get, writable } from 'svelte/store';

export type ThemeMode = 'dark' | 'light' | 'system';
export type ResolvedTheme = 'dark' | 'light';

const STORAGE_KEY = 'kochbuch-theme';

function systemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function storedMode(): ThemeMode {
  if (typeof window === 'undefined') return 'dark';
  const value = localStorage.getItem(STORAGE_KEY);
  return value === 'light' || value === 'system' || value === 'dark' ? value : 'dark';
}

export const themeMode = writable<ThemeMode>(storedMode());
export const resolvedTheme = writable<ResolvedTheme>('dark');

export function applyTheme(mode: ThemeMode): void {
  if (typeof document === 'undefined') return;
  const resolved = mode === 'system' ? systemTheme() : mode;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute('content', resolved === 'dark' ? '#12100e' : '#f5f0e8');
  resolvedTheme.set(resolved);
}

export function setTheme(mode: ThemeMode): void {
  themeMode.set(mode);
  if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, mode);
  applyTheme(mode);
}

export function cycleTheme(): ThemeMode {
  const current = get(themeMode);
  const next: ThemeMode = current === 'dark' ? 'light' : current === 'light' ? 'system' : 'dark';
  setTheme(next);
  return next;
}

export function initTheme(): void {
  const mode = storedMode();
  themeMode.set(mode);
  applyTheme(mode);
  if (typeof window === 'undefined') return;
  const media = window.matchMedia('(prefers-color-scheme: light)');
  const onChange = () => {
    if (get(themeMode) === 'system') applyTheme('system');
  };
  media.addEventListener('change', onChange);
}

export function setAccent(color: string): void {
  if (typeof document === 'undefined') return;
  document.documentElement.style.setProperty('--accent', color);
  if (typeof localStorage !== 'undefined') localStorage.setItem('kochbuch-accent', color);
}

export const themeLabel = derived(themeMode, ($mode) =>
  $mode === 'dark' ? 'Dunkel' : $mode === 'light' ? 'Hell' : 'System'
);
