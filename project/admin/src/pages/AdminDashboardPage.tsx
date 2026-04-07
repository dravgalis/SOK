import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type AdminUser = {
  hh_id: string;
  name: string;
  email: string | null;
  company_name: string | null;
  subscription_status: string | null;
  subscription_expires_at: string | null;
  selected_interface: string | null;
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
                <th>User</th>
                <th>Last login</th>
                <th>Subscription status</th>
                <th>Subscription ends</th>
                <th>Selected interface</th>
                <th>Account</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.hh_id}>
                  <td>{user.company_name ?? '—'}</td>
                  <td>{user.name}</td>
                  <td>{new Date(user.last_login).toLocaleString()}</td>
                  <td>{user.subscription_status ?? '—'}</td>
                  <td>
                    {user.subscription_expires_at ? new Date(user.subscription_expires_at).toLocaleDateString() : '—'}
                  </td>
                  <td>{user.selected_interface ?? '—'}</td>
                  <td>
                    <button type="button" onClick={() => navigate(ADMIN_ROUTES.userDetails(user.hh_id))}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
