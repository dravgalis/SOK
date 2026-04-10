import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ROUTES } from '../config';
import { ThemeKey, applyTheme, readTheme } from '../theme';

const THEMES: { key: ThemeKey; label: string; className: string }[] = [
  { key: 'default', label: 'Светлая', className: 'theme-preview-default' },
  { key: 'dark', label: 'Черная', className: 'theme-preview-dark' },
  { key: 'blue', label: 'Синяя', className: 'theme-preview-blue' },
  { key: 'beige', label: 'Бежевая', className: 'theme-preview-beige' },
];

export function ThemeSettingsPage() {
  const [theme, setTheme] = useState<ThemeKey>(() => readTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return (
    <main className="page page-top">
      <section className="card dashboard-card">
        <h2>Выбор темы</h2>
        <p>Нажмите на вариант темы:</p>
        <div className="theme-grid">
          {THEMES.map((themeOption) => (
            <button
              key={themeOption.key}
              type="button"
              className={`theme-swatch ${theme === themeOption.key ? 'theme-swatch-active' : ''}`}
              onClick={() => setTheme(themeOption.key)}
              aria-label={themeOption.label}
              title={themeOption.label}
            >
              <span className={`theme-swatch-preview ${themeOption.className}`} />
              <span className="theme-swatch-label">{themeOption.label}</span>
            </button>
          ))}
        </div>
        <div style={{ marginTop: 16 }}>
          <Link to={APP_ROUTES.app}>← Назад в кабинет</Link>
        </div>
      </section>
    </main>
  );
}
