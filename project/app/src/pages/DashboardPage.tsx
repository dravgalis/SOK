import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ENDPOINTS } from '../config';

type Me = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  name?: string | null;
  avatar_url?: string | null;
  company_name?: string | null;
  company_logo_url?: string | null;
};

type BillingMe = {
  plan_code?: string | null;
  current_period_end?: string | null;
  days_left?: number;
  auto_renew_enabled?: boolean;
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
type ThemeKey = 'default';
type PlanCode = '1_month' | '6_months' | '12_months';

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
  const [theme, setTheme] = useState<ThemeKey>('default');
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [isAutoPayEnabled, setIsAutoPayEnabled] = useState(false);
  const [isPlanSelectorOpen, setIsPlanSelectorOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<PlanCode>('1_month');
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
        const vacanciesPayload = (await vacanciesResponse.json()) as VacanciesPayload;
        const billingPayload = (await billingResponse.json()) as BillingMe;

        setMe(mePayload);
        setBilling(billingPayload);
        setIsAutoPayEnabled(Boolean(billingPayload.auto_renew_enabled));
        if (billingPayload.plan_code && isPlanCode(billingPayload.plan_code)) {
          setSelectedPlan(billingPayload.plan_code);
        }
        setVacanciesByTab({
          active: vacanciesPayload.active || [],
          archived: vacanciesPayload.archived || [],
        });
        setCounts({
          active: vacanciesPayload.counts?.active ?? vacanciesPayload.active?.length ?? 0,
          archived: vacanciesPayload.counts?.archived ?? vacanciesPayload.archived?.length ?? 0,
        });
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Ошибка загрузки данных.');
      } finally {
        setLoading(false);
      }
    };

    void loadData();
  }, []);

  useEffect(() => {
    document.body.classList.remove('theme-default');
    document.body.classList.add(`theme-${theme}`);
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
      setIsAutoPayEnabled(Boolean(payload.auto_renew_enabled));
      if (payload.status === 'active' || attempts >= maxAttempts) {
        window.sessionStorage.removeItem('billing_refresh_pending');
        window.clearInterval(intervalId);
      }
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, []);

  const selectedVacancies = useMemo(() => vacanciesByTab[activeTab] || [], [activeTab, vacanciesByTab]);
  const currentPlanTitle = formatPlanLabel(billing?.plan_code);
  const planEndDate = formatPlanEndDate(billing?.current_period_end);
  const planDaysLeft = typeof billing?.days_left === 'number' ? `${billing.days_left} дн.` : '—';

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

  const handleToggleAutoPay = async () => {
    const nextValue = !isAutoPayEnabled;
    setIsAutoPayEnabled(nextValue);
    const response = await fetch(APP_ENDPOINTS.autoRenew, {
      method: 'PATCH',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: nextValue }),
    });
    if (!response.ok) {
      setIsAutoPayEnabled(!nextValue);
      throw new Error('Не удалось обновить автоплатеж.');
    }
    setBilling((current) => ({ ...(current || {}), auto_renew_enabled: nextValue }));
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
                  <button
                    type="button"
                    className={`theme-swatch ${theme === 'default' ? 'theme-swatch-active' : ''}`}
                    onClick={() => setTheme('default')}
                    aria-label="Белая тема"
                    title="Белая тема"
                  >
                    <span className="theme-swatch-preview" />
                  </button>
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

                  <div className="settings-toggle-row">
                    <span>Автоплатеж</span>
                    <button
                      type="button"
                      className={`toggle-switch ${isAutoPayEnabled ? 'toggle-switch-active' : ''}`}
                      onClick={() => void handleToggleAutoPay()}
                      aria-pressed={isAutoPayEnabled}
                    >
                      <span className="toggle-switch-thumb" />
                    </button>
                  </div>
                </section>

                <section className="settings-section">
                  <button type="button" className="settings-logout-button" onClick={handleLogout}>
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
                  <Link to={`/app/vacancies/${vacancy.id}`} className="vacancy-link">
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
      </section>
    </main>
  );
}

function formatPlanLabel(planCode?: string | null): string {
  const mapping: Record<string, string> = {
    '1_month': 'Подписка 1 месяц',
    '6_months': 'Подписка 6 месяцев',
    '12_months': 'Подписка 1 год',
  };
  if (!planCode) return 'Подписка не активна';
  return mapping[planCode] || planCode;
}

function isPlanCode(value: string): value is PlanCode {
  return value === '1_month' || value === '6_months' || value === '12_months';
}
