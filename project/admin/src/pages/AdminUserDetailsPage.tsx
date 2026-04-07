import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type VacancyRow = {
  id: string;
  name: string;
  status: 'active' | 'archived';
  responses_count: number;
};

type VacanciesResponse = {
  hh_id: string;
  vacancies: VacancyRow[];
};

export function AdminUserDetailsPage() {
  const { hhId } = useParams<{ hhId: string }>();
  const navigate = useNavigate();
  const [rows, setRows] = useState<VacancyRow[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }
    if (!hhId) {
      setError('Invalid user id.');
      return;
    }

    const loadRows = async () => {
      try {
        setError('');
        const response = await fetch(ADMIN_API.userVacancies(hhId), {
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
          throw new Error('Failed to load vacancies.');
        }

        const payload = (await response.json()) as VacanciesResponse;
        setRows(payload.vacancies);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load vacancies.');
      }
    };

    void loadRows();
    const intervalId = window.setInterval(() => {
      void loadRows();
    }, 10000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [hhId, navigate]);

  return (
    <main className="page">
      <section className="card">
        <h1>User account details</h1>
        <button type="button" onClick={() => navigate(ADMIN_ROUTES.dashboard)}>
          ← Back to dashboard
        </button>

        {error ? <p className="error">{error}</p> : null}

        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Vacancy</th>
                <th>Status</th>
                <th>Responses</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.status === 'active' ? 'Active' : 'Archived'}</td>
                  <td>{row.responses_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
