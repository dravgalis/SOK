import { useEffect, useState } from 'react';
import { APP_ENDPOINTS } from '../config';

type Me = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  name: string | null;
  avatar_url: string | null;
};

type Vacancy = {
  id: string;
  name: string;
  status: string | null;
  published_at: string | null;
};

export function AppPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [vacancies, setVacancies] = useState<Vacancy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError('');

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
        <section className="card dashboard-card status status-error">{error}</section>
      </main>
    );
  }

  const displayName = me?.name || [me?.first_name, me?.last_name].filter(Boolean).join(' ') || 'Работодатель';

  return (
    <main className="page">
      <section className="card dashboard-card">
        <div className="profile-header">
          {me?.avatar_url ? (
            <img src={me.avatar_url} alt={displayName} className="avatar" />
          ) : (
            <div className="avatar avatar-fallback">{displayName.slice(0, 1).toUpperCase()}</div>
          )}
          <h1>{displayName}</h1>
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
