import { useEffect, useMemo, useRef, useState } from 'react';
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
  score?: number | null;
  score_breakdown?: Array<{
    criterion: string;
    importance: string;
    weight: number;
    points: number;
    max_points: number;
    matched: boolean;
    reason: string;
  }>;
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
  page?: number;
  per_page?: number;
  pages?: number;
};

const DEFAULT_RESPONSES_PER_PAGE = 25;
const RESPONSES_PER_PAGE_OPTIONS = [10, 25, 50, 100, 200] as const;
const CRITERIA_LABELS: Record<string, string> = {
  skills: 'Навыки',
  specialization: 'Специализация',
  location: 'Локация',
  salary: 'Зарплата',
  experience: 'Опыт',
  work_format: 'Формат работы',
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

function formatScoreValue(score?: number | null): string {
  return typeof score === 'number' ? `${score}` : '—';
}

function getScoreBadgeClass(score: number | null | undefined): string {
  if (typeof score !== 'number') return 'score-badge score-badge-neutral';
  if (score >= 80) return 'score-badge score-badge-high';
  if (score >= 60) return 'score-badge score-badge-medium';
  return 'score-badge score-badge-low';
}

function buildTooltipRow(item: NonNullable<VacancyResponse['score_breakdown']>[number]): { text: string; matched: boolean } {
  const criterion = item.criterion;
  const reason = typeof item.reason === 'string' ? item.reason.toLowerCase() : '';

  if (criterion === 'skills') {
    const matched = item.points > 5;
    return {
      matched,
      text: matched ? `Совпали навыки (${item.points} из ${item.max_points})` : `Навыков недостаточно (${item.points} из ${item.max_points})`,
    };
  }

  if (criterion === 'specialization') {
    return { matched: item.matched, text: item.matched ? 'Специализация подходит' : 'Специализация не подходит' };
  }

  if (criterion === 'location') {
    if (item.matched) {
      return { matched: true, text: 'Локация подходит' };
    }
    if (reason.includes('удален')) {
      return { matched: false, text: 'Локация не совпадает (удалённая работа)' };
    }
    return { matched: false, text: 'Локация не совпадает' };
  }

  if (criterion === 'salary') {
    return { matched: item.matched, text: item.matched ? 'Зарплата подходит' : 'Зарплата не указана или не подходит' };
  }

  if (criterion === 'experience') {
    const matched = item.points > 0 && !reason.includes('ниже минимума') && !reason.includes('обнулен');
    return { matched, text: matched ? 'Опыт подходит' : 'Недостаточно опыта' };
  }

  if (criterion === 'work_format') {
    return { matched: item.matched, text: item.matched ? 'Формат работы подходит' : 'Формат работы не совпадает' };
  }

  const label = CRITERIA_LABELS[criterion] ?? 'Критерий';
  return { matched: item.matched, text: item.matched ? `${label} подходит` : `${label} не подходит` };
}

export function VacancyDetailsPage() {
  const { vacancyId } = useParams<{ vacancyId: string }>();
  const [vacancy, setVacancy] = useState<VacancyDetails | null>(null);
  const [responses, setResponses] = useState<VacancyResponse[]>([]);
  const [summaryByState, setSummaryByState] = useState<ResponsesSummaryItem[]>([]);
  const [responsesPage, setResponsesPage] = useState(1);
  const [responsesPages, setResponsesPages] = useState(1);
  const [responsesCount, setResponsesCount] = useState(0);
  const [responsesPerPage, setResponsesPerPage] = useState<number>(() => {
    const saved = typeof window !== 'undefined' ? window.localStorage.getItem('perPage') : null;
    const parsed = saved ? Number(saved) : NaN;
    return RESPONSES_PER_PAGE_OPTIONS.includes(parsed as (typeof RESPONSES_PER_PAGE_OPTIONS)[number])
      ? parsed
      : DEFAULT_RESPONSES_PER_PAGE;
  });
  const [isPerPageDropdownOpen, setIsPerPageDropdownOpen] = useState(false);
  const perPageDropdownRef = useRef<HTMLDivElement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setResponsesPage(1);
  }, [vacancyId]);

  useEffect(() => {
    setResponsesPage(1);
  }, [responsesPerPage]);

  useEffect(() => {
    window.localStorage.setItem('perPage', String(responsesPerPage));
  }, [responsesPerPage]);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      if (!perPageDropdownRef.current) return;
      const target = event.target;
      if (target instanceof Node && !perPageDropdownRef.current.contains(target)) {
        setIsPerPageDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, []);

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

        setResponsesCount(loadedResponses);
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

  const visibleResponses = useMemo(() => {
    const filtered = responses.filter(hasVisibleCandidateFields);
    return [...filtered].sort((left, right) => {
      const leftScore = typeof left.score === 'number' ? left.score : -1;
      const rightScore = typeof right.score === 'number' ? right.score : -1;
      if (rightScore !== leftScore) {
        return rightScore - leftScore;
      }

      const leftDate = left.response_created_at ? new Date(left.response_created_at).getTime() : 0;
      const rightDate = right.response_created_at ? new Date(right.response_created_at).getTime() : 0;
      return rightDate - leftDate;
    });
  }, [responses]);

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
            <span>Отклики (доступно): {responsesCount}</span>
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
            <label className="control-group">
              Показывать по:
              <div className="custom-dropdown" ref={perPageDropdownRef}>
                <button
                  type="button"
                  className="custom-dropdown-trigger"
                  onClick={() => setIsPerPageDropdownOpen((prev) => !prev)}
                >
                  <span>{responsesPerPage}</span>
                  <span className="custom-dropdown-arrow">{isPerPageDropdownOpen ? '▲' : '▼'}</span>
                </button>
                {isPerPageDropdownOpen ? (
                  <ul className="custom-dropdown-menu">
                    {RESPONSES_PER_PAGE_OPTIONS.map((value) => (
                      <li key={value}>
                        <button
                          type="button"
                          className={`custom-dropdown-option ${value === responsesPerPage ? 'custom-dropdown-option-active' : ''}`}
                          onClick={() => {
                            setResponsesPerPage(value);
                            setIsPerPageDropdownOpen(false);
                          }}
                        >
                          {value}
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </label>

            {responsesPages > 1 ? (
              <div className="responses-pagination pagination">
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
            <ul className="responses-list list">
              {visibleResponses.map((response, itemIndex) => {
                const displayIndex = (responsesPage - 1) * responsesPerPage + itemIndex + 1;

                return (
                  <li key={response.response_id} className="candidate-card">
                    <div className="candidate-card-header">
                      <h3 className="candidate-name">
                        #{displayIndex} {response.candidate_name ?? 'Кандидат без имени'}
                      </h3>
                      <div
                        className="score-tooltip-wrap"
                      >
                        <button type="button" className="score-info-icon" aria-label="Показать разбор совпадения">
                          !
                        </button>
                        <span className={getScoreBadgeClass(response.score)}>{formatScoreValue(response.score)}</span>
                        <div className="score-tooltip" role="tooltip">
                          <h4>Разбор совпадения</h4>
                          {Array.isArray(response.score_breakdown) && response.score_breakdown.length > 0 ? (
                            <ul>
                              {response.score_breakdown.map((item, idx) => {
                                const row = buildTooltipRow(item);
                                const isPartial = item.criterion === 'location' && row.text.includes('удалённая работа');
                                const icon = isPartial ? '~' : row.matched ? '✔' : '✖';
                                const iconClass = isPartial ? 'match partial' : row.matched ? 'match ok' : 'match fail';
                                return (
                                  <li key={`${response.response_id}-${item.criterion}-${idx}`}>
                                    <span className={iconClass}>{icon}</span>
                                    <span className="tooltip-label">{row.text}</span>
                                  </li>
                                );
                              })}
                            </ul>
                          ) : (
                            <p>Нет деталей расчета.</p>
                          )}
                        </div>
                      </div>
                    </div>
                    <p className="candidate-subheader">{response.resume_title ?? 'Без названия резюме'}</p>
                    <div className="card-meta">
                      {typeof response.age === 'number' ? <span>Возраст: {response.age}</span> : <span>Возраст: —</span>}
                      {response.expected_salary ? <span>Зарплата: {response.expected_salary}</span> : <span>Зарплата: —</span>}
                      {response.location ? <span>Локация: {response.location}</span> : <span>Локация: —</span>}
                    </div>
                    <div className="candidate-card-footer card-footer">
                      <span className="candidate-status">Статус: {response.status || '—'}</span>
                      {response.resume_url ? (
                        <a href={response.resume_url} target="_blank" rel="noreferrer">
                          Открыть резюме
                        </a>
                      ) : (
                        <span>Резюме недоступно</span>
                      )}
                    </div>
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
            <div className="responses-pagination pagination">
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
