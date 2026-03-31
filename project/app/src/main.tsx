import React, { useEffect, useMemo, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { APP_ENDPOINTS, AUTH_ENDPOINTS } from './config';
import './styles.css';

type AuthStatus = 'idle' | 'loading';

type Me = {
  id: string;
  name: string;
  avatar: string | null;
  email: string | null;
};

type Vacancy = {
  id: string;
  name: string;
  status: string | null;
  published_at: string | null;
};

function LoginPage() {
  const [status, setStatus] = useState<AuthStatus>('idle');
  const [query] = useState(() => new URLSearchParams(window.location.search));

  const authResult = query.get('auth');
  const errorMessage = query.get('message');

  const handleLogin = () => {
    setStatus('loading');
    window.location.assign(AUTH_ENDPOINTS.hhLogin);
  };

  return (
    <main className="page">
      <section className="card">
        <h1>Вход в HR SaaS</h1>
        <p>Подключите аккаунт работодателя HeadHunter для работы с кандидатами.</p>

        {authResult === 'error' ? (
          <div className="status status-error">{errorMessage || 'Не удалось выполнить вход через HeadHunter.'}</div>
        ) : null}

        <button type="button" className="cta-button" onClick={handleLogin} disabled={status === 'loading'}>
          {status === 'loading' ? 'Переходим в HeadHunter...' : 'Войти через HeadHunter'}
        </button>
      </section>
    </main>
  );
}

function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [meResponse, vacanciesResponse] = await Promise.all([
          fetch(APP_ENDPOINTS.me, { credentials: 'include' }),
          fetch(APP_ENDPOINTS.vacancies, { credentials: 'include' }),
        ]);

        if (!meResponse.ok) {
          throw new Error('Не удалось загрузить профиль работодателя.');
        }

        if (!vacanciesResponse.ok) {
          throw new Error('Не удалось загрузить вакансии.');
        }

        const mePayload = (await meResponse.json()) as Me;
        const vacanciesPayload = (await vacanciesResponse.json()) as { items: Vacancy[] };

        setMe(mePayload);
        setVacancies(vacanciesPayload.items || []);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки данных.');
      } finally {
        setLoading(false);
      }
    };

    void loadData();
  }, []);

  if (loading) {
    return (
      <main className="page">
        <section className="card dashboard-card">
          <p>Загрузка данных...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="page">
        <section className="card dashboard-card status status-error">
          {error}
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="card dashboard-card">
        <div className="profile-header">
          {me?.avatar ? (
            <img src={me.avatar} alt={me.name} className="avatar" />
          ) : (
            <div className="avatar avatar-fallback">{(me?.name || '?').slice(0, 1).toUpperCase()}</div>
          )}
          <h1>{me?.name || 'Работодатель'}</h1>
          {me?.email ? <p>{me.email}</p> : null}
        </div>

        <div>
          <h2>Вакансии</h2>
          {vacancies.length === 0 ? (
            <p>Вакансий пока нет.</p>
          ) : (
            <ul className="vacancies-list">
              {vacancies.map((vacancy) => (
                <li key={vacancy.id} className="vacancy-item">
                  <strong>{vacancy.name}</strong>
                  <span>Статус: {vacancy.status || '—'}</span>
                  <span>Дата публикации: {vacancy.published_at || '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

function App() {
  const path = useMemo(() => window.location.pathname, []);
  return path === '/app' ? <DashboardPage /> : <LoginPage />;
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
