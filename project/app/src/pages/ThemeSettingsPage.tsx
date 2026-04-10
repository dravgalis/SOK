import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ROUTES } from '../config';

type ThemeKey = 'default';

export function ThemeSettingsPage() {
  const [theme, setTheme] = useState<ThemeKey>(() => {
    const raw = window.localStorage.getItem('app_theme');
    return raw === 'default' ? 'default' : 'default';
  });

  useEffect(() => {
    window.localStorage.setItem('app_theme', theme);
    document.body.classList.remove('theme-default');
    document.body.classList.add(`theme-${theme}`);
  }, [theme]);

  return (
    <main className="page page-top">
      <section className="card dashboard-card">
        <h2>Выбор темы</h2>
        <p>Нажмите на вариант темы:</p>
        <button
          type="button"
          className={`theme-swatch ${theme === 'default' ? 'theme-swatch-active' : ''}`}
          onClick={() => setTheme('default')}
          aria-label="Белая тема"
          title="Белая тема"
        >
          <span className="theme-swatch-preview" />
        </button>
        <div style={{ marginTop: 16 }}>
          <Link to={APP_ROUTES.app}>← Назад в кабинет</Link>
        </div>
      </section>
    </main>
  );
}
