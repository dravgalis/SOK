import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type AdminUser = {
  hh_id: string;
  name: string;
  email: string | null;
  company_name: string | null;
  vacancies_count: number;
  responses_count: number;
  created_at: string;
  last_login: string;
};

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);

    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }

    const loadUsers = async () => {
      try {
        setError('');
        const response = await fetch(ADMIN_API.users, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          credentials: 'include',
        });

        if (response.status === 401) {
          window.localStorage.removeItem(ADMIN_STORAGE_KEY);
          navigate(ADMIN_ROUTES.login, { replace: true });
          return;
        }

        if (!response.ok) {
          throw new Error('Failed to load HH users data.');
        }

        const payload = (await response.json()) as AdminUser[];
        setUsers(payload);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load HH users data.');
      }
    };

    void loadUsers();
    const intervalId = window.setInterval(() => {
      void loadUsers();
    }, 10000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [navigate]);

  return (
    <main className="page">
      <section className="card">
        <h1>Admin Dashboard</h1>

        {error ? <p className="error">{error}</p> : null}

        <p>Users who logged in via HH: {users.length}</p>
        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Vacancies</th>
                <th>Responses</th>
                <th>User</th>
                <th>Last login</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.hh_id}>
                  <td>{user.company_name ?? '—'}</td>
                  <td>{user.vacancies_count}</td>
                  <td>{user.responses_count}</td>
                  <td>{user.name}</td>
                  <td>{new Date(user.last_login).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
