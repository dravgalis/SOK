export type ThemeKey =
  | 'default'
  | 'dark'
  | 'blue'
  | 'beige'
  | 'mint'
  | 'lavender'
  | 'sunset'
  | 'aurora'
  | 'neon'
  | 'golden-sakura'
  | 'mythic-pop';

export function readTheme(): ThemeKey {
  const raw = window.localStorage.getItem('app_theme');
  if (
    raw === 'dark' ||
    raw === 'blue' ||
    raw === 'beige' ||
    raw === 'default' ||
    raw === 'mint' ||
    raw === 'lavender' ||
    raw === 'sunset' ||
    raw === 'aurora' ||
    raw === 'neon' ||
    raw === 'golden-sakura' ||
    raw === 'mythic-pop'
  ) {
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
    'theme-sunset',
    'theme-aurora',
    'theme-neon',
    'theme-golden-sakura',
    'theme-mythic-pop'
  );
  document.body.classList.add(`theme-${theme}`);
}
