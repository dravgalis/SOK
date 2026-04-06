import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminLogin } from '../api';
import { setAdminToken } from '../auth';

export function LoginPage() {
  const navigate = useNavigate();
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const token = await adminLogin(login, password);
      setAdminToken(token);
      navigate('/admin', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка авторизации.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Admin Login</h1>
        <p className="subtitle">Введите логин и пароль администратора</p>

        <label className="field-label" htmlFor="login">
          Login
        </label>
        <input
          id="login"
          className="text-input"
          value={login}
          onChange={(event) => setLogin(event.target.value)}
          autoComplete="username"
          required
        />

        <label className="field-label" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          className="text-input"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          required
        />

        {error && <p className="error-text">{error}</p>}

        <button className="primary-button" type="submit" disabled={loading}>
          {loading ? 'Вход...' : 'Войти'}
        </button>
      </form>
    </div>
  );
}
