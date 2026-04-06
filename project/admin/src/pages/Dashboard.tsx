import { useEffect, useState } from 'react';
import { AdminUser, fetchAdminUsers } from '../api';
import { clearAdminToken, getAdminToken } from '../auth';

export function Dashboard() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      const token = getAdminToken();
      if (!token) {
        setError('Требуется авторизация администратора.');
        return;
      }

      try {
        const usersData = await fetchAdminUsers(token);
        setUsers(usersData);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Не удалось загрузить пользователей.';
        setError(message);

        if (message.includes('Сессия истекла')) {
          clearAdminToken();
        }
      }
    }

    void load();
  }, []);

  return (
    <section>
      <h1>Dashboard</h1>
      <p className="subtitle">Статистика входов пользователей через HH OAuth.</p>

      {error && <p className="error-text">{error}</p>}

      <div className="cards-grid">
        <article className="card">
          <h2>Пользователи</h2>
          <p>Всего: {users.length}</p>
        </article>

        <article className="card">
          <h2>Последний вход</h2>
          <p>{users[0]?.last_login ?? 'Нет данных'}</p>
        </article>
      </div>

      <article className="card section-gap">
        <h2>Последние пользователи</h2>
        <ul className="list">
          {users.slice(0, 10).map((user) => (
            <li key={user.hh_id}>
              <strong>{user.name}</strong>
              <span>{user.email ?? 'Email отсутствует'}</span>
              <span>HH ID: {user.hh_id}</span>
            </li>
          ))}
          {users.length === 0 && <li>Пока нет данных.</li>}
        </ul>
      </article>
    </section>
  );
}
