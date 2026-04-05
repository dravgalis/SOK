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
  total?: number;
  count?: number;
  loaded_count?: number;
  hh_total?: number;
  page?: number;
  per_page?: number;
  pages?: number;
};

const DEFAULT_RESPONSES_PER_PAGE = 25;
const RESPONSES_PER_PAGE_OPTIONS = [10, 25, 50, 100, 200] as const;

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

function hasVisibleCandidateFields(response: VacancyResponse): boolean {
  return Boolean(
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
}

export function VacancyDetailsPage() {
  const { vacancyId } = useParams<{ vacancyId: string }>();
  const [vacancy, setVacancy] = useState<VacancyDetails | null>(null);
  const [responses, setResponses] = useState<VacancyResponse[]>([]);
  const [summaryByState, setSummaryByState] = useState<ResponsesSummaryItem[]>([]);
  const [responsesPage, setResponsesPage] = useState(1);
  const [responsesPages, setResponsesPages] = useState(1);
  const [responsesCount, setResponsesCount] = useState(0);
  const [hhTotalCount, setHhTotalCount] = useState<number | null>(null);
  const [responsesPerPage, setResponsesPerPage] = useState<number>(DEFAULT_RESPONSES_PER_PAGE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setResponsesPage(1);
  }, [vacancyId]);

  useEffect(() => {
    setResponsesPage(1);
  }, [responsesPerPage]);

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
          fetch(`${APP_ENDPOINTS.vacancyResponses(vacancyId)}?page=${responsesPage}&per_page=${responsesPerPage}`, {
            credentials: 'include',
          }),
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
        setResponses(Array.isArray(responsesPayload.items) ? responsesPayload.items : []);
        setSummaryByState(Array.isArray(responsesPayload.summary_by_state) ? responsesPayload.summary_by_state : []);
        const loadedResponses =
          typeof responsesPayload.loaded_count === 'number'
            ? responsesPayload.loaded_count
            : typeof responsesPayload.total === 'number'
              ? responsesPayload.total
              : typeof responsesPayload.count === 'number'
                ? responsesPayload.count
                : 0;

        const hhTotal =
          typeof responsesPayload.hh_total === 'number'
            ? responsesPayload.hh_total
            : typeof vacancyPayload.responses_count === 'number'
              ? vacancyPayload.responses_count
              : null;

        setResponsesCount(loadedResponses);
        setHhTotalCount(hhTotal);
        setResponsesPages(typeof responsesPayload.pages === 'number' ? responsesPayload.pages : 1);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки данных.');
      } finally {
        setLoading(false);
      }
    };

    void loadData();
  }, [vacancyId, responsesPage, responsesPerPage]);

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

  const visibleResponses = responses.filter(hasVisibleCandidateFields);

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
            <span>Отклики (доступно): {responsesCount}</span>
            {typeof hhTotalCount === 'number' ? <span>По счётчику HH: {hhTotalCount}</span> : null}
            {typeof hhTotalCount === 'number' && responsesCount < hhTotalCount ? (
              <span>Доступно меньше, чем в счётчике HH: {responsesCount} из {hhTotalCount}</span>
            ) : null}
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

          <div className="responses-controls">
            <label>
              Показывать по:{' '}
              <select value={responsesPerPage} onChange={(event) => setResponsesPerPage(Number(event.target.value))}>
                {RESPONSES_PER_PAGE_OPTIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>

            {responsesPages > 1 ? (
              <div className="responses-pagination">
                <button type="button" disabled={responsesPage <= 1} onClick={() => setResponsesPage((prev) => Math.max(prev - 1, 1))}>
                  Назад
                </button>
                <span>
                  {responsesPage} / {responsesPages}
                </span>
                <button
                  type="button"
                  disabled={responsesPage >= responsesPages}
                  onClick={() => setResponsesPage((prev) => Math.min(prev + 1, responsesPages))}
                >
                  Вперёд
                </button>
              </div>
            ) : null}
          </div>

          {visibleResponses.length > 0 ? (
            <ul className="responses-list">
              {visibleResponses.map((response, itemIndex) => {
                const displayIndex = (responsesPage - 1) * responsesPerPage + itemIndex + 1;

                return (
                  <li key={response.response_id} className="response-card">
                    <div className="response-row">
                      <strong>#{displayIndex}</strong>
                      <strong>{response.candidate_name ?? 'Кандидат без имени'}</strong>
                      {response.resume_title ? <span>Резюме: {response.resume_title}</span> : null}
                      {response.status ? <span>Статус: {response.status}</span> : null}
                    </div>
                    <div className="response-row">
                      {typeof response.age === 'number' ? <span>Возраст: {response.age}</span> : null}
                      {response.expected_salary ? <span>Зарплата: {response.expected_salary}</span> : null}
                      {response.location ? <span>Локация: {response.location}</span> : null}
                      {response.response_created_at ? <span>Дата отклика: {formatDate(response.response_created_at)}</span> : null}
                    </div>
                    <div className="response-row">
                      {response.resume_url ? (
                        <a href={response.resume_url} target="_blank" rel="noreferrer">
                          Открыть резюме
                        </a>
                      ) : null}
                      {response.phone ? <span>Телефон: {response.phone}</span> : null}
                      {response.email ? <span>Email: {response.email}</span> : null}
                    </div>
                    {response.cover_letter ? <p>Сопроводительное письмо: {response.cover_letter}</p> : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="vacancies-empty">
              <h3>Подробные данные кандидатов пока недоступны</h3>
              {summaryByState.length > 0 ? (
                <ul className="responses-list">
                  {summaryByState.map((summaryItem) => (
                    <li key={`${summaryItem.state}-${summaryItem.state_name ?? ''}`} className="response-card">
                      <strong>{summaryItem.state_name || summaryItem.state || '—'}</strong>
                      <span>Код стадии: {summaryItem.state || '—'}</span>
                      <span>Количество: {summaryItem.count}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Для этой вакансии пока не найдено откликов.</p>
              )}
            </div>
          )}

          {responsesPages > 1 ? (
            <div className="responses-pagination">
              <button type="button" disabled={responsesPage <= 1} onClick={() => setResponsesPage((prev) => Math.max(prev - 1, 1))}>
                Назад
              </button>
              <span>
                {responsesPage} / {responsesPages}
              </span>
              <button
                type="button"
                disabled={responsesPage >= responsesPages}
                onClick={() => setResponsesPage((prev) => Math.min(prev + 1, responsesPages))}
              >
                Вперёд
              </button>
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}
