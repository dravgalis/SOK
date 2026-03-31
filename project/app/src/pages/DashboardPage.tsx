import { useEffect, useMemo, useState } from 'react';
import { APP_ENDPOINTS } from '../config';

type Me = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  name?: string | null;
  avatar_url?: string | null;
};

type Vacancy = {
  id: string;
  name: string;
  status?: string | null;
  published_at?: string | null;
  archived?: boolean;
};

type VacancyTabKey = 'active' | 'drafts' | 'archived' | 'templates';

type VacanciesPayload = {
  active: Vacancy[];
  archived: Vacancy[];
  drafts: Vacancy[];
  templates: Vacancy[];
  counts: Record<VacancyTabKey, number>;
};

const TAB_ITEMS: { key: VacancyTabKey; label: string }[] = [
  { key: 'active', label: 'Активные' },
  { key: 'drafts', label: 'Черновики' },
  { key: 'archived', label: 'Архив' },
  { key: 'templates', label: 'Шаблоны' },
];

function formatPublishedAt(value?: string | null): string {
  if (!value) {
    return '—';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function getVacancyStatus(tab: VacancyTabKey, status?: string | null): string {
  if (status) {
    return status;
  }

  if (tab === 'active') return 'Активна';
  if (tab === 'archived') return 'В архиве';
  if (tab === 'drafts') return 'Черновик';
  if (tab === 'templates') return 'Шаблон';
  return '—';
}

export function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [vacanciesByTab, setVacanciesByTab] = useState<Record<VacancyTabKey, Vacancy[]>>({
    active: [],
    archived: [],
    drafts: [],
    templates: [],
  });
  const [counts, setCounts] = useState<Record<VacancyTabKey, number>>({
    active: 0,
    archived: 0,
    drafts: 0,
    templates: 0,
  });
  const [activeTab, setActiveTab] = useState<VacancyTabKey>('active');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError('');

        const [meResponse, vacanciesResponse] = await Promise.all([
          fetch(APP_ENDPOINTS.me, { credentials: 'include' }),
          fetch(APP_ENDPOINTS.vacancies, { credentials: 'include' }),
        ]);

        if (!meResponse.ok) {
          throw new Error('Не удалось загрузить профиль работодателя.');
        }

        if (!vacanciesResponse.ok) {
          throw new Error('Не удалось загрузить вакансии.');
        }

        const mePayload = (await meResponse.json()) as Me;
        const vacanciesPayload = (await vacanciesResponse.json()) as VacanciesPayload;

        setMe(mePayload);
        setVacanciesByTab({
          active: vacanciesPayload.active || [],
          archived: vacanciesPayload.archived || [],
          drafts: vacanciesPayload.drafts || [],
          templates: vacanciesPayload.templates || [],
        });
        setCounts({
          active: vacanciesPayload.counts?.active ?? vacanciesPayload.active?.length ?? 0,
          archived: vacanciesPayload.counts?.archived ?? vacanciesPayload.archived?.length ?? 0,
          drafts: vacanciesPayload.counts?.drafts ?? vacanciesPayload.drafts?.length ?? 0,
          templates: vacanciesPayload.counts?.templates ?? vacanciesPayload.templates?.length ?? 0,
        });
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки данных.');
      } finally {
        setLoading(false);
      }
    };

    void loadData();
  }, []);

  const selectedVacancies = useMemo(() => vacanciesByTab[activeTab] || [], [activeTab, vacanciesByTab]);

  if (loading) {
    return (
      <main className="page page-top">
        <section className="card dashboard-card">
          <p>Загрузка данных...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="page page-top">
        <section className="card dashboard-card status status-error">{error}</section>
      </main>
    );
  }

  const displayName = me?.name || [me?.first_name, me?.last_name].filter(Boolean).join(' ') || 'Работодатель';

  return (
    <main className="page page-top">
      <section className="card dashboard-card dashboard-wide">
        <div className="profile-header profile-header-row">
          {me?.avatar_url ? (
            <img src={me.avatar_url} alt={displayName} className="avatar" />
          ) : (
            <div className="avatar avatar-fallback">{displayName.slice(0, 1).toUpperCase()}</div>
          )}
          <h1>{displayName}</h1>
        </div>

        <div className="vacancies-section">
          <h2>Вакансии</h2>

          <div className="vacancy-tabs" role="tablist" aria-label="Категории вакансий">
            {TAB_ITEMS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.key}
                className={`vacancy-tab ${activeTab === tab.key ? 'vacancy-tab-active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                <span>{tab.label}</span>
                <span className="vacancy-tab-count">{counts[tab.key] ?? 0}</span>
              </button>
            ))}
          </div>

          {selectedVacancies.length === 0 ? (
            <div className="vacancies-empty">
              <h3>Здесь пока пусто</h3>
              <p>Во вкладке «{TAB_ITEMS.find((tab) => tab.key === activeTab)?.label}» пока нет вакансий.</p>
            </div>
          ) : (
            <ul className="vacancies-list">
              {selectedVacancies.map((vacancy) => (
                <li key={vacancy.id} className="vacancy-item">
                  <a
                    href={`/app/vacancies/${vacancy.id}`}
                    onClick={(event) => event.preventDefault()}
                    className="vacancy-link"
                  >
                    <strong>{vacancy.name}</strong>
                    <span>Дата публикации: {formatPublishedAt(vacancy.published_at)}</span>
                    <span>Статус: {getVacancyStatus(activeTab, vacancy.status)}</span>
                    <span>ID: {vacancy.id}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}
