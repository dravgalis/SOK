import React, { useMemo, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { AUTH_ENDPOINTS } from './config';
import './styles.css';

type AuthStatus = 'idle' | 'loading' | 'success' | 'error';

function LoginPage() {
  const [status, setStatus] = useState<AuthStatus>('idle');

  const query = useMemo(() => new URLSearchParams(window.location.search), []);
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

        {authResult === 'success' ? (
          <div className="status status-success">Авторизация через HeadHunter выполнена успешно.</div>
        ) : null}

        {authResult === 'error' ? (
          <div className="status status-error">
            {errorMessage || 'Не удалось выполнить вход через HeadHunter.'}
          </div>
        ) : null}

        <button type="button" className="cta-button" onClick={handleLogin} disabled={status === 'loading'}>
          {status === 'loading' ? 'Переходим в HeadHunter...' : 'Войти через HeadHunter'}
        </button>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <LoginPage />
  </React.StrictMode>
);
