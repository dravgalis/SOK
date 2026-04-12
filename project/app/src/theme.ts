export type ThemeKey =
  | 'default'
  | 'dark'
  | 'blue'
  | 'beige'
  | 'mint'
  | 'lavender'
  | 'neon';

const THEME_KEYS: ThemeKey[] = [
  'default',
  'dark',
  'blue',
  'beige',
  'mint',
  'lavender',
  'neon',
];

export function isThemeKey(value: unknown): value is ThemeKey {
  return typeof value === 'string' && THEME_KEYS.includes(value as ThemeKey);
}

export function readTheme(): ThemeKey {
  const raw = window.localStorage.getItem('app_theme');
  if (isThemeKey(raw)) {
    return raw;
  }
  return 'default';
}

export function applyTheme(theme: ThemeKey, persist = true): void {
  if (persist) {
    window.localStorage.setItem('app_theme', theme);
  }
  document.body.classList.remove(
    'theme-default',
    'theme-dark',
    'theme-blue',
    'theme-beige',
    'theme-mint',
    'theme-lavender',
    'theme-neon',
  );
  document.body.classList.add(`theme-${theme}`);
}
