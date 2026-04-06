import { useEffect, useState } from 'react';
import { fetchVacancies, Vacancy } from '../api';

export function Vacancies() {
  const [active, setActive] = useState<Vacancy[]>([]);
  const [archived, setArchived] = useState<Vacancy[]>([]);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchVacancies();
        setActive(data.active);
        setArchived(data.archived);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load vacancies.');
      }
    }

    void load();
  }, []);

  return (
    <section>
      <h1>Vacancies</h1>
      <p className="subtitle">List of active and archived vacancies from backend API.</p>
      {error && <p className="error-text">{error}</p>}

      <div className="cards-grid">
        <article className="card">
          <h2>Active</h2>
          <ul className="list">
            {active.map((vacancy) => (
              <li key={vacancy.id}>
                <strong>{vacancy.name}</strong>
                <span>{vacancy.responses_count} responses</span>
              </li>
            ))}
            {active.length === 0 && <li>No active vacancies.</li>}
          </ul>
        </article>

        <article className="card">
          <h2>Archived</h2>
          <ul className="list">
            {archived.map((vacancy) => (
              <li key={vacancy.id}>
                <strong>{vacancy.name}</strong>
                <span>{vacancy.responses_count} responses</span>
              </li>
            ))}
            {archived.length === 0 && <li>No archived vacancies.</li>}
          </ul>
        </article>
      </div>
    </section>
  );
}
