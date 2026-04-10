export type ThemeKey = 'default' | 'dark' | 'blue' | 'beige' | 'mint';

export function readTheme(): ThemeKey {
  const raw = window.localStorage.getItem('app_theme');
  if (raw === 'dark' || raw === 'blue' || raw === 'beige' || raw === 'default' || raw === 'mint') {
    return raw;
  }
  return 'default';
}

export function applyTheme(theme: ThemeKey): void {
  window.localStorage.setItem('app_theme', theme);
  document.body.classList.remove('theme-default', 'theme-dark', 'theme-blue', 'theme-beige', 'theme-mint');
  document.body.classList.add(`theme-${theme}`);
}
