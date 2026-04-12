import { MouseEvent, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ENDPOINTS, APP_ROUTES } from '../config';
import { SupportChatWidget } from '../components/SupportChatWidget';
import { ThemeKey, applyTheme, readTheme } from '../theme';

type Me = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  name?: string | null;
  avatar_url?: string | null;
  company_name?: string | null;
  company_logo_url?: string | null;
  subscription_status?: string | null;
  subscription_label?: string | null;
};

type BillingMe = {
  plan_code?: string | null;
  current_period_end?: string | null;
  days_left?: number;
  status?: string | null;
};

type Vacancy = {
  id: string;
  name: string;
  status?: string | null;
  normalized_status?: string | null;
  archived?: boolean;
  published_at?: string | null;
  archived_at?: string | null;
  responses_count?: number;
};

type VacancyTabKey = 'active' | 'archived';
type PlanCode = '1_month' | '6_months' | '12_months';
type AccessToast = { x: number; y: number; text: string };

type VacanciesPayload = {
  active: Vacancy[];
  archived: Vacancy[];
  counts: Record<VacancyTabKey, number>;
};

const TAB_ITEMS: { key: VacancyTabKey; label: string }[] = [
  { key: 'active', label: 'Активные' },
  { key: 'archived', label: 'Архив' },
];

const PLAN_OPTIONS: { code: PlanCode; label: string; price: string }[] = [
  { code: '1_month', label: '1 месяц', price: '399 ₽' },
  { code: '6_months', label: '6 месяцев', price: '2 150 ₽' },
  { code: '12_months', label: '12 месяцев', price: '3 799 ₽' },
];

function formatDate(value?: string | null): string {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

function getVacancyMetaDate(tab: VacancyTabKey, vacancy: Vacancy): string {
  if (tab === 'archived') {
    return formatDate(vacancy.archived_at || vacancy.published_at);
  }

  return formatDate(vacancy.published_at);
}

function getVacancyMetaLabel(tab: VacancyTabKey): string {
  return tab === 'archived' ? 'Дата архивирования' : 'Дата публикации';
}

function getNormalizedStatus(tab: VacancyTabKey, vacancy: Vacancy): string {
  if (vacancy.normalized_status) {
    return vacancy.normalized_status;
  }

  if (typeof vacancy.archived === 'boolean') {
    return vacancy.archived ? 'Архивная' : 'Активная';
  }

  return tab === 'archived' ? 'Архивная' : 'Активная';
}

function formatPlanEndDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  }).format(date);
}

export function DashboardPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [vacanciesByTab, setVacanciesByTab] = useState<Record<VacancyTabKey, Vacancy[]>>({
    active: [],
    archived: [],
  });
  const [counts, setCounts] = useState<Record<VacancyTabKey, number>>({
    active: 0,
    archived: 0,
  });
  const [activeTab, setActiveTab] = useState<VacancyTabKey>('active');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [theme] = useState<ThemeKey>(() => readTheme());
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [isPlanSelectorOpen, setIsPlanSelectorOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<PlanCode>('1_month');
  const [accessToast, setAccessToast] = useState<AccessToast | null>(null);
  const [supportSending, setSupportSending] = useState(false);
  const [isSupportOpen, setIsSupportOpen] = useState(false);
  const [supportUnread, setSupportUnread] = useState(0);
  const [expiringNoticeDismissed, setExpiringNoticeDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        setError('');

        const [meResponse, vacanciesResponse, billingResponse] = await Promise.all([
          fetch(APP_ENDPOINTS.me, { credentials: 'include' }),
          fetch(APP_ENDPOINTS.vacancies, { credentials: 'include' }),
          fetch(APP_ENDPOINTS.billingMe, { credentials: 'include' }),
        ]);

        if (!meResponse.ok) {
          throw new Error('Не удалось загрузить профиль работодателя.');
        }

        if (!vacanciesResponse.ok) {
          throw new Error('Не удалось загрузить вакансии.');
        }
        if (!billingResponse.ok) {
          throw new Error('Не удалось загрузить подписку.');
        }

        const mePayload = (await meResponse.json()) as Me;
        const vacanciesPayload = normalizeVacanciesPayload(await vacanciesResponse.json());
        const billingPayload = (await billingResponse.json()) as BillingMe;

        setMe(mePayload);
        setBilling(billingPayload);
        if (billingPayload.plan_code && isPlanCode(billingPayload.plan_code)) {
          setSelectedPlan(billingPayload.plan_code);
        }
        setVacanciesByTab({
          active: vacanciesPayload.active,
          archived: vacanciesPayload.archived,
        });
        setCounts(vacanciesPayload.counts);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки данных.');
      } finally {
        setLoading(false);
      }
    };

    void loadData();
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    if (window.sessionStorage.getItem('billing_refresh_pending') !== '1') {
      return;
    }

    let attempts = 0;
    const maxAttempts = 10;
    const intervalId = window.setInterval(async () => {
      attempts += 1;
      const response = await fetch(APP_ENDPOINTS.billingMe, { credentials: 'include' });
      if (!response.ok) {
        if (attempts >= maxAttempts) {
          window.sessionStorage.removeItem('billing_refresh_pending');
          window.clearInterval(intervalId);
        }
        return;
      }

      const payload = (await response.json()) as BillingMe;
      setBilling(payload);
      if (payload.status === 'active' || attempts >= maxAttempts) {
        window.sessionStorage.removeItem('billing_refresh_pending');
        window.clearInterval(intervalId);
      }
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, []);

  const selectedVacancies = useMemo(() => vacanciesByTab[activeTab] || [], [activeTab, vacanciesByTab]);
  const remainingDays = typeof billing?.days_left === 'number' ? billing.days_left : 0;
  const normalizedDaysLeft = Math.max(0, remainingDays);
  const planEndDate = formatPlanEndDate(billing?.current_period_end);
  const planDaysLeft = `${normalizedDaysLeft} дн.`;
  const hasAccess = billing?.status === 'active' && normalizedDaysLeft > 0;
  const trialActive = hasAccess && (me?.subscription_status === 'trial_3d' || billing?.plan_code === 'trial_3d');
  const currentPlanTitle = trialActive ? 'Тест 3 дня' : formatPlanLabel(normalizedDaysLeft);
  const isExpiringSoon = hasAccess && normalizedDaysLeft <= 3;
  const isExpired = !hasAccess;

  useEffect(() => {
    if (!isExpiringSoon) {
      setExpiringNoticeDismissed(false);
    }
  }, [isExpiringSoon]);

  const showAccessNotice = (event?: MouseEvent<HTMLElement>, text?: string) => {
    if (accessToast) {
      return;
    }
    setAccessToast({
      text: text || 'Оплатите подписку, чтобы открыть этот раздел.',
      x: event?.clientX ?? Math.max(180, window.innerWidth - 260),
      y: event?.clientY ?? 24,
    });
    window.setTimeout(() => setAccessToast(null), 5000);
  };

  const handleBlockedAction = (event: MouseEvent<HTMLElement>) => {
    event.preventDefault();
    showAccessNotice(event);
  };

  const handleLogout = () => {
    window.location.assign('https://sok-app.onrender.com');
  };

  const handleRenew = async (planCode: PlanCode) => {
    const response = await fetch(APP_ENDPOINTS.createPayment, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan_code: planCode }),
    });
    if (!response.ok) {
      throw new Error('Не удалось создать оплату.');
    }
    const payload = (await response.json()) as { confirmation_url?: string };
    if (!payload.confirmation_url) {
      throw new Error('Платежная ссылка не получена.');
    }
    setIsPlanSelectorOpen(false);
    window.location.href = payload.confirmation_url;
  };

  const handleSupport = async (): Promise<void> => {
    setSupportSending(true);
    setIsSupportOpen(true);
    window.setTimeout(() => setSupportSending(false), 120);
  };

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

  const companyName = me?.company_name || 'Компания';

  return (
    <main className="page page-top">
      <section className="card dashboard-card dashboard-wide">
        {isExpiringSoon && !expiringNoticeDismissed ? (
            <div className="status status-warning status-dismissible">
            Внимание: подписка заканчивается через {normalizedDaysLeft} дн. Продлите заранее, чтобы не потерять доступ.
            <button
              type="button"
              className="status-dismiss"
              onClick={() => setExpiringNoticeDismissed(true)}
              aria-label="Закрыть предупреждение"
            >
              ✕
            </button>
          </div>
        ) : null}
        {isExpired ? (
          <div className="status status-error">
            Подписка закончилась. Пожалуйста, оплатите подписку, чтобы пользоваться сервисом.
          </div>
        ) : null}
        {accessToast ? (
          <div
            className="access-toast"
            style={{ left: Math.max(16, accessToast.x - 180), top: Math.max(16, accessToast.y - 56) }}
            role="status"
            aria-live="polite"
          >
            {accessToast.text}
          </div>
        ) : null}

        <div className="profile-header-row">
          <div className="profile-header-company">
            {me?.company_logo_url ? (
              <img src={me.company_logo_url} alt={companyName} className="avatar avatar-company" />
            ) : (
              <div className="avatar avatar-fallback avatar-company">{companyName.slice(0, 1).toUpperCase()}</div>
            )}

            <div className="profile-header-content">
              <p className="profile-header-label">Работодатель</p>
              <h1>{companyName}</h1>
            </div>
          </div>

          <div className="settings-wrap">
            <button
              type="button"
              className="settings-trigger"
              onClick={() => setIsSettingsOpen((value) => !value)}
              aria-expanded={isSettingsOpen}
              aria-label="Открыть настройки"
            >
              <span aria-hidden>⚙️</span>
            </button>

            {isSettingsOpen ? (
              <div className="settings-menu">
                <section className="settings-section">
                  <h3>Тема</h3>
                  <span className="settings-label">Текущая тема</span>
                  <Link
                    to={APP_ROUTES.theme}
                    className={`settings-secondary-button ${!hasAccess ? 'settings-button-disabled' : ''}`}
                    onClick={!hasAccess ? handleBlockedAction : undefined}
                    aria-disabled={!hasAccess}
                  >
                    Выбрать тему
                  </Link>
                </section>

                <section className="settings-section">
                  <h3>Оплата</h3>
                  <span className="settings-label">Вид тарифа</span>
                  <div className="settings-plan-card">
                    <strong>{currentPlanTitle}</strong>
                    <span>Заканчивается: {planEndDate}</span>
                    <span>Осталось: {planDaysLeft}</span>
                  </div>

                  <button type="button" className="settings-secondary-button" onClick={() => setIsPlanSelectorOpen(true)}>
                    Продлить подписку
                  </button>

                  {isPlanSelectorOpen ? (
                    <div className="settings-plan-card">
                      <strong>Выберите тариф</strong>
                      {PLAN_OPTIONS.map((plan) => (
                        <label key={plan.code} style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                          <span>
                            <input
                              type="radio"
                              name="billing-plan"
                              checked={selectedPlan === plan.code}
                              onChange={() => setSelectedPlan(plan.code)}
                            />{' '}
                            {plan.label}
                          </span>
                          <span>{plan.price}</span>
                        </label>
                      ))}
                      <button type="button" className="settings-secondary-button" onClick={() => void handleRenew(selectedPlan)}>
                        Перейти к оплате
                      </button>
                    </div>
                  ) : null}

                </section>

                <section className="settings-section">
                  <Link
                    to={APP_ROUTES.operations}
                    className={`settings-secondary-button ${!hasAccess ? 'settings-button-disabled' : ''}`}
                    onClick={!hasAccess ? handleBlockedAction : undefined}
                    aria-disabled={!hasAccess}
                  >
                    Операции
                  </Link>
                  <button
                    type="button"
                    className="settings-logout-button"
                    onClick={handleLogout}
                  >
                    Выйти из аккаунта
                  </button>
                </section>
              </div>
            ) : null}
          </div>
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
                className={`vacancy-tab ${activeTab === tab.key ? 'vacancy-tab-active' : ''} ${!hasAccess ? 'settings-button-disabled' : ''}`}
                onClick={hasAccess ? () => setActiveTab(tab.key) : handleBlockedAction}
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
                  <Link
                    to={`/app/vacancies/${vacancy.id}`}
                    className={`vacancy-link ${!hasAccess ? 'settings-button-disabled' : ''}`}
                    onClick={!hasAccess ? handleBlockedAction : undefined}
                    aria-disabled={!hasAccess}
                  >
                    <strong>{vacancy.name}</strong>
                    <span>
                      {getVacancyMetaLabel(activeTab)}: {getVacancyMetaDate(activeTab, vacancy)}
                    </span>
                    <span>Статус: {getNormalizedStatus(activeTab, vacancy)}</span>
                    <span>Отклики (по счётчику HH): {vacancy.responses_count ?? 0}</span>
                    <span>ID: {vacancy.id}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button type="button" className="support-fab" onClick={() => void handleSupport()} disabled={supportSending}>
          {supportSending ? 'Открываем чат...' : 'Связаться с поддержкой'}
          {supportUnread > 0 ? <span className="support-badge">{supportUnread}</span> : null}
        </button>
      </section>
      <SupportChatWidget open={isSupportOpen} onOpenChange={setIsSupportOpen} onUnreadChange={setSupportUnread} hideFab />
    </main>
  );
}

function normalizeVacanciesPayload(payload: unknown): VacanciesPayload {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('Получен невалидный ответ по вакансиям.');
  }

  const raw = payload as Record<string, unknown>;
  const active = normalizeVacanciesArray(raw.active);
  const archived = normalizeVacanciesArray(raw.archived);

  const countsFromPayload = normalizeCounts(raw.counts);
  return {
    active,
    archived,
    counts: {
      active: countsFromPayload?.active ?? active.length,
      archived: countsFromPayload?.archived ?? archived.length,
    },
  };
}

function normalizeVacanciesArray(value: unknown): Vacancy[] {
  if (value == null) return [];
  if (!Array.isArray(value)) {
    throw new Error('Получен невалидный формат списка вакансий.');
  }

  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return [];
    const row = item as Record<string, unknown>;
    const idRaw = row.id;
    if (typeof idRaw !== 'string' && typeof idRaw !== 'number') return [];

    return [
      {
        id: String(idRaw),
        name: typeof row.name === 'string' ? row.name : 'Без названия вакансии',
        status: typeof row.status === 'string' ? row.status : null,
        normalized_status: typeof row.normalized_status === 'string' ? row.normalized_status : null,
        archived: typeof row.archived === 'boolean' ? row.archived : undefined,
        published_at: typeof row.published_at === 'string' ? row.published_at : null,
        archived_at: typeof row.archived_at === 'string' ? row.archived_at : null,
        responses_count: typeof row.responses_count === 'number' ? row.responses_count : 0,
      },
    ];
  });
}

function normalizeCounts(value: unknown): Record<VacancyTabKey, number> | null {
  if (value == null) return null;
  if (typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Получен невалидный формат counts по вакансиям.');
  }

  const row = value as Record<string, unknown>;
  return {
    active: asNonNegativeInteger(row.active) ?? 0,
    archived: asNonNegativeInteger(row.archived) ?? 0,
  };
}

function asNonNegativeInteger(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  const normalized = Math.floor(value);
  return normalized >= 0 ? normalized : 0;
}

function formatPlanLabel(daysLeft: number, planCode?: string | null): string {
  if (planCode === 'trial_3d') {
    return 'Тест 3 дня';
  }
  if (daysLeft <= 0) return 'Подписка закончилась';
  if (daysLeft <= 31) return 'Подписка 1 месяц';
  if (daysLeft <= 183) return 'Подписка 6 месяцев';
  return 'Подписка 1 год';
}

function isPlanCode(value: string): value is PlanCode {
  return value === '1_month' || value === '6_months' || value === '12_months';
}
