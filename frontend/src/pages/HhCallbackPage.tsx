import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout';
import { APP_ROUTES, AUTH_ENDPOINTS } from '../config/api';
import { AuthStatus, HhCallbackResponse } from '../types/auth';

export function HhCallbackPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<AuthStatus>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const oauthError = searchParams.get('error');
  const oauthErrorDescription = searchParams.get('error_description');

  const readableError = useMemo(() => {
    if (oauthError) {
      return oauthErrorDescription
        ? `HeadHunter вернул ошибку: ${oauthErrorDescription}`
        : `HeadHunter вернул ошибку: ${oauthError}`;
    }

    return 'Не удалось завершить вход. Попробуйте снова.';
  }, [oauthError, oauthErrorDescription]);

  useEffect(() => {
    const completeAuth = async () => {
      if (oauthError) {
        setStatus('error');
        setErrorMessage(readableError);
        return;
      }

      if (!code || !state) {
        setStatus('error');
        setErrorMessage('Отсутствуют обязательные параметры авторизации (code/state).');
        return;
      }

      try {
        setStatus('loading');

        const response = await fetch(AUTH_ENDPOINTS.hhCallback, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({ code, state }),
        });

        const payload = (await response.json()) as HhCallbackResponse;

        if (!response.ok || !payload.success) {
          throw new Error(payload.message || 'Сервис временно недоступен.');
        }

        setStatus('success');
        const destination = payload.redirectTo || APP_ROUTES.app;

        setTimeout(() => {
          navigate(destination, { replace: true });
        }, 700);
      } catch (error) {
        const fallbackMessage =
          error instanceof Error
            ? error.message
            : 'Ошибка сети. Проверьте подключение и повторите попытку.';

        setStatus('error');
        setErrorMessage(fallbackMessage);
      }
    };

    void completeAuth();
  }, [code, navigate, oauthError, readableError, state]);

  return (
    <AuthLayout>
      <header className="auth-header">
        <h1>Авторизация HeadHunter</h1>
        <p>Проверяем доступ и завершаем вход в ваш HR-сервис.</p>
      </header>

      {status === 'idle' || status === 'loading' ? (
        <div className="status-block status-loading">
          <p>Выполняем вход...</p>
        </div>
      ) : null}

      {status === 'success' ? (
        <div className="status-block status-success">
          <p>Вход выполнен успешно. Перенаправляем в рабочее пространство...</p>
        </div>
      ) : null}

      {status === 'error' ? (
        <div className="status-block status-error">
          <p>{errorMessage}</p>
          <button
            type="button"
            className="secondary-button"
            onClick={() => navigate(APP_ROUTES.root, { replace: true })}
          >
            Попробовать снова
          </button>
        </div>
      ) : null}
    </AuthLayout>
  );
}
