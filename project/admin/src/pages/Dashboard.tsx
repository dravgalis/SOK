import { useEffect, useState } from 'react';
import { fetchMe, fetchVacancies, MeResponse, VacanciesResponse } from '../api';

export function Dashboard() {
  const [profile, setProfile] = useState<MeResponse | null>(null);
  const [vacancies, setVacancies] = useState<VacanciesResponse | null>(null);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function load() {
      try {
        const [meData, vacanciesData] = await Promise.all([fetchMe(), fetchVacancies()]);
        setProfile(meData);
        setVacancies(vacanciesData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard data.');
      }
    }

    void load();
  }, []);

  return (
    <section>
      <h1>Dashboard</h1>
      <p className="subtitle">Overview of your account and vacancies.</p>

      {error && <p className="error-text">{error}</p>}

      <div className="cards-grid">
        <article className="card">
          <h2>Account</h2>
          <p>Name: {profile?.name ?? '-'}</p>
          <p>Company: {profile?.company_name ?? '-'}</p>
        </article>

        <article className="card">
          <h2>Vacancies</h2>
          <p>Active: {vacancies?.counts.active ?? 0}</p>
          <p>Archived: {vacancies?.counts.archived ?? 0}</p>
        </article>
      </div>
    </section>
  );
}
