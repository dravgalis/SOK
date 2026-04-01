import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { APP_ENDPOINTS } from '../config';

type VacancyDetails = {
  id: string;
  name: string;
  status?: string | null;
  normalized_status?: string | null;
  archived?: boolean;
  published_at?: string | null;
  archived_at?: string | null;
  responses_count?: number;
  description?: string | null;
};

type VacancyResponse = {
  response_id: string;
  candidate_name?: string | null;
  age?: number | null;
  resume_title?: string | null;
  expected_salary?: string | null;
  location?: string | null;
  response_created_at?: string | null;
  cover_letter?: string | null;
  status?: string | null;
  resume_url?: string | null;
  phone?: string | null;
  email?: string | null;
};

type ResponsesSummaryItem = {
  state: string;
  state_name?: string | null;
  count: number;
};

type VacancyResponsesPayload = {
  items: VacancyResponse[];
  summary_by_state?: ResponsesSummaryItem[];
  count?: number;
};

function formatDate(value?: string | null): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function VacancyDetailsPage() {
  const { vacancyId } = useParams<{ vacancyId: string }>();
  const [vacancy, setVacancy] = useState<VacancyDetails | null>(null);
  const [responses, setResponses] = useState<VacancyResponse[]>([]);
  const [summaryByState, setSummaryByState] = useState<ResponsesSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      if (!vacancyId) {
        setError('Некорректный идентификатор вакансии.');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError('');

        const [vacancyResponse, responsesResponse] = await Promise.all([
          fetch(APP_ENDPOINTS.vacancyById(vacancyId), { credentials: 'include' }),
          fetch(APP_ENDPOINTS.vacancyResponses(vacancyId), { credentials: 'include' }),
        ]);

        if (!vacancyResponse.ok) {
          throw new Error('Не удалось загрузить детали вакансии.');
        }

        if (!responsesResponse.ok) {
          throw new Error('Не удалось загрузить отклики вакансии.');
        }

        const vacancyPayload = (await vacancyResponse.json()) as VacancyDetails;
        const responsesPayload = (await responsesResponse.json()) as VacancyResponsesPayload;

        setVacancy(vacancyPayload);
        setResponses(responsesPayload.items || []);
        setSummaryByState(responsesPayload.summary_by_state || []);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки данных.');
      } finally {
        setLoading(false);
      }
    };

    void loadData();
  }, [vacancyId]);

  const vacancyStatus = useMemo(() => {
    if (!vacancy) return '—';
    if (vacancy.normalized_status) return vacancy.normalized_status;
    if (typeof vacancy.archived === 'boolean') return vacancy.archived ? 'Архивная' : 'Активная';
    return vacancy.status || '—';
  }, [vacancy]);

  if (loading) {
    return (
      <main className="page page-top">
        <section className="card dashboard-card dashboard-wide">
          <p>Загрузка вакансии...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="page page-top">
        <section className="card dashboard-card dashboard-wide">
          <div className="status status-error">{error}</div>
          <Link to="/app" className="back-link">
            ← Назад к вакансиям
          </Link>
        </section>
      </main>
    );
  }

  if (!vacancy) {
    return (
      <main className="page page-top">
        <section className="card dashboard-card dashboard-wide">
          <div className="vacancies-empty">
            <h3>Вакансия не найдена</h3>
            <p>Проверьте корректность ссылки или вернитесь к списку вакансий.</p>
          </div>
          <Link to="/app" className="back-link">
            ← Назад к вакансиям
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="page page-top">
      <section className="card dashboard-card dashboard-wide vacancy-details-layout">
        <Link to="/app" className="back-link">
          ← Назад к вакансиям
        </Link>

        <header className="vacancy-details-header">
          <h1>{vacancy.name}</h1>
          <div className="vacancy-details-meta">
            <span>Статус: {vacancyStatus}</span>
            <span>Дата публикации: {formatDate(vacancy.published_at)}</span>
            <span>Дата архивирования: {formatDate(vacancy.archived_at)}</span>
            <span>Отклики: {vacancy.responses_count ?? responses.length}</span>
          </div>
        </header>

        {vacancy.description ? (
          <section className="vacancy-description">
            <h2>Описание</h2>
            <p>{vacancy.description}</p>
          </section>
        ) : null}

        <section className="responses-section">
          <h2>Отклики</h2>

          {responses.length === 0 ? (
            <div className="vacancies-empty">
              <h3>Подробные данные кандидатов пока недоступны</h3>
              {summaryByState.length > 0 ? (
                <ul className="responses-list">
                  {summaryByState.map((summaryItem) => (
                    <li key={`${summaryItem.state}-${summaryItem.state_name}`} className="response-card">
                      <strong>{summaryItem.state_name || summaryItem.state || '—'}</strong>
                      <span>Код стадии: {summaryItem.state || '—'}</span>
                      <span>Количество: {summaryItem.count ?? 0}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Для этой вакансии пока не найдено откликов.</p>
              )}
            </div>
          ) : (
            <ul className="responses-list">
              {responses.map((response) => (
                <li key={response.response_id} className="response-card">
                  {(() => {
                    const hasVisibleData = Boolean(
                      response.candidate_name ||
                        response.resume_title ||
                        typeof response.age === 'number' ||
                        response.expected_salary ||
                        response.location ||
                        response.response_created_at ||
                        response.status ||
                        response.resume_url ||
                        response.phone ||
                        response.email ||
                        response.cover_letter
                    );

                    if (!hasVisibleData) return null;

                    return (
                      <>
                        {response.candidate_name ? <strong>{response.candidate_name}</strong> : null}
                        {response.resume_title ? <span>Резюме: {response.resume_title}</span> : null}
                        {typeof response.age === 'number' ? <span>Возраст: {response.age}</span> : null}
                        {response.expected_salary ? <span>Зарплатные ожидания: {response.expected_salary}</span> : null}
                        {response.location ? <span>Локация: {response.location}</span> : null}
                        {response.response_created_at ? <span>Дата отклика: {formatDate(response.response_created_at)}</span> : null}
                        {response.status ? <span>Статус: {response.status}</span> : null}
                        {response.resume_url ? (
                          <a href={response.resume_url} target="_blank" rel="noreferrer">
                            Открыть резюме
                          </a>
                        ) : null}
                        {response.phone ? <span>Телефон: {response.phone}</span> : null}
                        {response.email ? <span>Email: {response.email}</span> : null}
                        {response.cover_letter ? <p>Сопроводительное письмо: {response.cover_letter}</p> : null}
                      </>
                    );
                  })()}
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}
