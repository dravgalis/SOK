import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ENDPOINTS, APP_ROUTES } from '../config';
import { ThemeKey, applyTheme, readTheme } from '../theme';

type ThemeItem = {
  code: ThemeKey;
  label: string;
  price: number;
  paid: boolean;
  unlocked: boolean;
};

const PREVIEW_CLASS: Record<ThemeKey, string> = {
  default: 'theme-preview-default',
  dark: 'theme-preview-dark',
  blue: 'theme-preview-blue',
  beige: 'theme-preview-beige',
  mint: 'theme-preview-mint',
};

export function ThemeSettingsPage() {
  const [theme, setTheme] = useState<ThemeKey>(() => readTheme());
  const [previewTheme, setPreviewTheme] = useState<ThemeKey>(() => readTheme());
  const [themes, setThemes] = useState<ThemeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    applyTheme(previewTheme, false);
  }, [previewTheme]);

  useEffect(() => {
    const loadThemes = async () => {
      try {
        setLoading(true);
        const response = await fetch(APP_ENDPOINTS.themes, { credentials: 'include' });
        if (!response.ok) throw new Error('Не удалось загрузить темы.');
        const payload = (await response.json()) as { themes: ThemeItem[] };
        setThemes(payload.themes || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить темы.');
      } finally {
        setLoading(false);
      }
    };
    void loadThemes();
  }, []);

  const handleSelectTheme = async (themeItem: ThemeItem) => {
    if (!themeItem.paid || themeItem.unlocked) {
      setTheme(themeItem.code);
      setPreviewTheme(themeItem.code);
      applyTheme(themeItem.code, true);
      return;
    }
    setPreviewTheme(themeItem.code);
  };

  const handlePurchaseTheme = async (themeCode: ThemeKey) => {
    const response = await fetch(APP_ENDPOINTS.createThemePayment, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme_code: themeCode }),
    });
    if (!response.ok) {
      setError('Не удалось создать оплату темы.');
      return;
    }
    const payload = (await response.json()) as { confirmation_url?: string };
    if (payload.confirmation_url) {
      window.location.href = payload.confirmation_url;
    }
  };

  const previewThemeItem = themes.find((item) => item.code === previewTheme);
  const previewLocked = Boolean(previewThemeItem?.paid && !previewThemeItem?.unlocked);

  return (
    <main className="page page-top">
      <section className="card dashboard-card">
        <h2>Выбор темы</h2>
        <p>Нажмите на вариант темы:</p>
        {loading ? <p>Загрузка тем...</p> : null}
        {error ? <p className="status status-error">{error}</p> : null}
        <div className="theme-grid">
          {themes.map((themeOption) => (
            <button
              key={themeOption.code}
              type="button"
              className={`theme-swatch ${theme === themeOption.code ? 'theme-swatch-active' : ''}`}
              onClick={() => void handleSelectTheme(themeOption)}
              aria-label={themeOption.label}
              title={themeOption.label}
            >
              <span className={`theme-swatch-preview ${PREVIEW_CLASS[themeOption.code] || PREVIEW_CLASS.default}`} />
              <span className="theme-swatch-label">{themeOption.label}</span>
              {themeOption.paid && !themeOption.unlocked ? (
                <span className="theme-swatch-price">Премиум · {themeOption.price} ₽ · Предпросмотр</span>
              ) : null}
            </button>
          ))}
        </div>
        {previewLocked ? (
          <div className="theme-paywall">
            <strong>Тема в режиме предпросмотра</strong>
            <p>После обновления страницы премиум-тема будет закрыта. Чтобы пользоваться постоянно — приобретите её.</p>
            <button
              type="button"
              className="settings-secondary-button"
              onClick={() => void handlePurchaseTheme(previewTheme)}
            >
              Приобрести тему за {previewThemeItem?.price ?? 50} ₽
            </button>
          </div>
        ) : null}
        <div style={{ marginTop: 16 }}>
          <Link to={APP_ROUTES.app}>← Назад в кабинет</Link>
        </div>
      </section>
    </main>
  );
}
