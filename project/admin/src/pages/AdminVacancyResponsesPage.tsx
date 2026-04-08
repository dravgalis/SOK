import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type ResponseRow = {
  response_id: string;
  name: string;
  specialization: string;
  experience: string;
  matched_skills_count: number;
  score_points: number;
};

type ResponsesPayload = {
  responses: ResponseRow[];
};

export function AdminVacancyResponsesPage() {
  const { hhId, vacancyId } = useParams<{ hhId: string; vacancyId: string }>();
  const navigate = useNavigate();
  const [rows, setRows] = useState<ResponseRow[]>([]);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading'>('idle');

  const loadResponses = async (force = false) => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token || !hhId || !vacancyId) {
      return;
    }

    try {
      setStatus('loading');
      setError('');
      const response = await fetch(ADMIN_API.vacancyResponses(hhId, vacancyId, force), {
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
        throw new Error('Failed to load vacancy responses.');
      }

      const payload = (await response.json()) as ResponsesPayload;
      setRows(payload.responses);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load vacancy responses.');
    } finally {
      setStatus('idle');
    }
  };

  useEffect(() => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }
    void loadResponses();
  }, [hhId, vacancyId, navigate]);

  return (
    <main className="page">
      <section className="card">
        <h1>Vacancy responses</h1>
        <button type="button" onClick={() => navigate(ADMIN_ROUTES.userDetails(hhId ?? ''))}>
          ← Back to vacancy list
        </button>
        <button type="button" onClick={() => void loadResponses(true)} disabled={status === 'loading'}>
          {status === 'loading' ? 'Обновляю...' : 'Актуализировать'}
        </button>

        {error ? <p className="error">{error}</p> : null}

        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Имя</th>
                <th>Специализация</th>
                <th>Опыт</th>
                <th>Совпало навыков</th>
                <th>Баллы</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.response_id}>
                  <td>{row.name}</td>
                  <td>{row.specialization}</td>
                  <td>{row.experience}</td>
                  <td>{row.matched_skills_count}</td>
                  <td>{row.score_points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
