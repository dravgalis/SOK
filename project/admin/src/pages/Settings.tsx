import { ADMIN_ENDPOINTS } from '../api';

export function Settings() {
  return (
    <section>
      <h1>Settings</h1>
      <p className="subtitle">Текущие API endpoint'ы админ-панели.</p>

      <article className="card">
        <ul className="list">
          <li>{ADMIN_ENDPOINTS.login}</li>
          <li>{ADMIN_ENDPOINTS.users}</li>
        </ul>
      </article>
    </section>
  );
}
