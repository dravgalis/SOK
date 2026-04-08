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
  source?: 'cache' | 'hh';
  cached_at?: string;
};

export function AdminUserDetailsPage() {
  const { hhId } = useParams<{ hhId: string }>();
  const navigate = useNavigate();
  const [rows, setRows] = useState<VacancyRow[]>([]);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading'>('idle');
  const [source, setSource] = useState<'cache' | 'hh' | null>(null);

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

    const loadRows = async (force = false) => {
      try {
        setStatus('loading');
        setError('');
        const response = await fetch(ADMIN_API.userVacancies(hhId, force), {
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
        setSource(payload.source ?? null);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load vacancies.');
      } finally {
        setStatus('idle');
      }
    };

    void loadRows();
    return undefined;
  }, [hhId, navigate]);

  const handleRefresh = async () => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token || !hhId) {
      return;
    }

    try {
      setStatus('loading');
      setError('');
      const response = await fetch(ADMIN_API.userVacancies(hhId, true), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to refresh vacancies.');
      }

      const payload = (await response.json()) as VacanciesResponse;
      setRows(payload.vacancies);
      setSource(payload.source ?? null);
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : 'Failed to refresh vacancies.');
    } finally {
      setStatus('idle');
    }
  };

  return (
    <main className="page">
      <section className="card">
        <h1>User account details</h1>
        <button type="button" onClick={() => navigate(ADMIN_ROUTES.dashboard)}>
          ← Back to dashboard
        </button>
        <button type="button" onClick={handleRefresh} disabled={status === 'loading'}>
          {status === 'loading' ? 'Обновляю...' : 'Актуализировать'}
        </button>
        {source ? <p>Источник данных: {source === 'cache' ? 'кэш' : 'HH API'}</p> : null}

        {error ? <p className="error">{error}</p> : null}

        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Vacancy</th>
                <th>Status</th>
                <th>Responses</th>
                <th>Отклики</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>{row.status === 'active' ? 'Active' : 'Archived'}</td>
                  <td>{row.responses_count}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => navigate(ADMIN_ROUTES.vacancyResponses(hhId ?? '', row.id))}
                    >
                      Открыть
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
