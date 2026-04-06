import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type LoginStatus = 'idle' | 'loading';

export function AdminLoginPage() {
  const navigate = useNavigate();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [status, setStatus] = useState<LoginStatus>('idle');

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    try {
      setStatus('loading');
      setErrorMessage('');

      const response = await fetch(ADMIN_API.login, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          login,
          password,
        }),
      });

      if (!response.ok) {
        throw new Error('Invalid login or password.');
      }

      const payload = (await response.json()) as { success?: boolean };

      if (!payload.success) {
        throw new Error('Authentication failed.');
      }

      window.localStorage.setItem(ADMIN_STORAGE_KEY, 'true');
      navigate(ADMIN_ROUTES.dashboard, { replace: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Authentication failed.';
      setErrorMessage(message);
      window.localStorage.removeItem(ADMIN_STORAGE_KEY);
    } finally {
      setStatus('idle');
    }
  };

  return (
    <main className="page">
      <section className="card">
        <h1>Admin Login</h1>

        <form className="form" onSubmit={handleSubmit}>
          <label htmlFor="admin-login">Login</label>
          <input
            id="admin-login"
            type="text"
            value={login}
            onChange={(event) => setLogin(event.target.value)}
            required
            autoComplete="username"
          />

          <label htmlFor="admin-password">Password</label>
          <input
            id="admin-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoComplete="current-password"
          />

          {errorMessage ? <p className="error">{errorMessage}</p> : null}

          <button type="submit" disabled={status === 'loading'}>
            {status === 'loading' ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}
