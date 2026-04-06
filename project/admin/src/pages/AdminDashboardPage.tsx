import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type UsersCountResponse = {
  count: number;
};

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [count, setCount] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const isAuthenticated = window.localStorage.getItem(ADMIN_STORAGE_KEY) === 'true';

    if (!isAuthenticated) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }

    const loadUsersCount = async () => {
      try {
        setError('');
        const response = await fetch(ADMIN_API.usersCount, {
          method: 'GET',
          credentials: 'include',
        });

        if (response.status === 401) {
          window.localStorage.removeItem(ADMIN_STORAGE_KEY);
          navigate(ADMIN_ROUTES.login, { replace: true });
          return;
        }

        if (!response.ok) {
          throw new Error('Failed to load authorized users count.');
        }

        const payload = (await response.json()) as UsersCountResponse;
        setCount(payload.count);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load authorized users count.');
      }
    };

    void loadUsersCount();
  }, [navigate]);

  return (
    <main className="page">
      <section className="card">
        <h1>Admin Dashboard</h1>

        {error ? <p className="error">{error}</p> : null}

        <p>Authorized users count: {count ?? '...'}</p>
      </section>
    </main>
  );
}
