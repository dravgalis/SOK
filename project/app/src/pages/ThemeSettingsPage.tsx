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
  rarity: string;
};

const PREVIEW_CLASS: Record<ThemeKey, string> = {
  default: 'theme-preview-default',
  dark: 'theme-preview-dark',
  blue: 'theme-preview-blue',
  beige: 'theme-preview-beige',
  mint: 'theme-preview-mint',
  lavender: 'theme-preview-lavender',
  neon: 'theme-preview-neon',
};

export function ThemeSettingsPage() {
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

  const saveSelectedTheme = async (selectedTheme: ThemeKey) => {
    const response = await fetch(APP_ENDPOINTS.selectedTheme, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme_code: selectedTheme }),
    });
    if (!response.ok) {
      setError('Не удалось сохранить выбранную тему.');
    }
  };

  const handleSelectTheme = async (themeItem: ThemeItem) => {
    if (!themeItem.paid || themeItem.unlocked) {
      setPreviewTheme(themeItem.code);
      applyTheme(themeItem.code, true);
      void saveSelectedTheme(themeItem.code);
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

  return (
    <main className="page page-top">
      <section className="card dashboard-card">
        <div className="page-top-link-row">
          <Link to={APP_ROUTES.app} className="back-link-button">
            ← Назад в кабинет
          </Link>
        </div>
        <h2>Выбор темы</h2>
        <p>Нажмите на вариант темы:</p>
        {loading ? <p>Загрузка тем...</p> : null}
        {error ? <p className="status status-error">{error}</p> : null}
        <div className="theme-grid">
          {themes.map((themeOption) => (
            <div key={themeOption.code} className="theme-swatch-item">
              <button
                type="button"
                className={`theme-swatch ${previewTheme === themeOption.code ? 'theme-swatch-active' : ''}`}
                onClick={() => void handleSelectTheme(themeOption)}
                aria-label={themeOption.label}
                title={themeOption.label}
              >
                <span className={`theme-swatch-preview ${PREVIEW_CLASS[themeOption.code] || PREVIEW_CLASS.default}`} />
                <span className="theme-swatch-label">{themeOption.label}</span>
                <span className="theme-swatch-price">
                  {themeOption.rarity} {themeOption.paid ? `· ${themeOption.price} ₽` : '· бесплатно'}
                  {themeOption.paid && !themeOption.unlocked ? ' · Предпросмотр' : ''}
                </span>
              </button>
              {previewTheme === themeOption.code && themeOption.paid && !themeOption.unlocked ? (
                <div className="theme-paywall theme-paywall-inline">
                  <strong>Тема в режиме предпросмотра</strong>
                  <p>Чтобы пользоваться постоянно — приобретите её.</p>
                  <button
                    type="button"
                    className="settings-secondary-button"
                    onClick={() => void handlePurchaseTheme(themeOption.code)}
                  >
                    Приобрести тему за {themeOption.price} ₽
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
