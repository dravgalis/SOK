import { ADMIN_ENDPOINTS } from '../api';

export function Settings() {
  return (
    <section>
      <h1>Settings</h1>
      <p className="subtitle">Admin panel API configuration.</p>

      <article className="card">
        <p>This admin panel is independent from the main app and uses backend API endpoints:</p>
        <ul className="list">
          <li>{ADMIN_ENDPOINTS.me}</li>
          <li>{ADMIN_ENDPOINTS.vacancies}</li>
          <li>{ADMIN_ENDPOINTS.vacancyResponses(':vacancyId')}</li>
        </ul>
      </article>
    </section>
  );
}
