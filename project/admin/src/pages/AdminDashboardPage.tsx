import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type AdminUser = {
  hh_id: string;
  name: string;
  email: string | null;
  company_name: string | null;
  subscription_status: string | null;
  subscription_expires_at: string | null;
  trial_3d_granted: number | boolean | null;
  plan_code?: string | null;
  current_period_end?: string | null;
  billing_status?: string | null;
  selected_interface: string | null;
  created_at: string;
  last_login: string;
};

const THEME_SWATCH_CLASS: Record<string, string> = {
  default: 'admin-theme-preview-default',
  dark: 'admin-theme-preview-dark',
  blue: 'admin-theme-preview-blue',
  beige: 'admin-theme-preview-beige',
  mint: 'admin-theme-preview-mint',
  lavender: 'admin-theme-preview-lavender',
  sunset: 'admin-theme-preview-sunset',
  aurora: 'admin-theme-preview-aurora',
  neon: 'admin-theme-preview-neon',
  'golden-sakura': 'admin-theme-preview-golden-sakura',
  'mythic-pop': 'admin-theme-preview-mythic-pop',
};

function getAdminPeriodLabel(status: string | null): string {
  if (!status) return '—';

  const labelMap: Record<string, string> = {
    inactive: 'Без подписки',
    trial_3d: 'Тест 3 дня',
    paid_1m: 'Оплачено: 1 месяц',
    paid_6m: 'Оплачено: 6 месяцев',
    paid_1y: 'Оплачено: 1 год',
  };

  return labelMap[status] ?? status;
}

export function AdminDashboardPage() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');
  const [subscriptionDrafts, setSubscriptionDrafts] = useState<
    Record<string, { periodType: string; periodEndsOn: string; trial3dGranted: boolean }>
  >(
    {}
  );
  const [savingByUser, setSavingByUser] = useState<Record<string, boolean>>({});
  const [refreshing, setRefreshing] = useState(false);
  const [unreadSupportCount, setUnreadSupportCount] = useState(0);

  const toDateInputValue = (value: string | null): string => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toISOString().slice(0, 10);
  };

  const loadUsers = async (options?: { silent?: boolean }) => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }
    if (!options?.silent) {
      setRefreshing(true);
    }
    try {
      setError('');
      const response = await fetch(ADMIN_API.users, {
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
        throw new Error('Не удалось загрузить пользователей.');
      }

      const payload = (await response.json()) as AdminUser[];
      setUsers(payload);
      const supportResponse = await fetch(ADMIN_API.supportChats, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
      });
      if (supportResponse.ok) {
        const supportPayload = (await supportResponse.json()) as { chats?: Array<{ unread_by_admin?: number }> };
        setUnreadSupportCount(
          (supportPayload.chats || []).reduce((acc, chat) => acc + (chat.unread_by_admin ?? 0), 0)
        );
      }
      setSubscriptionDrafts(
        payload.reduce<Record<string, { periodType: string; periodEndsOn: string; trial3dGranted: boolean }>>((acc, user) => {
          acc[user.hh_id] = {
            periodType: user.subscription_status ?? 'inactive',
            periodEndsOn: toDateInputValue(user.subscription_expires_at),
            trial3dGranted: Boolean(user.trial_3d_granted),
          };
          return acc;
        }, {})
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить пользователей.');
    } finally {
      if (!options?.silent) {
        setRefreshing(false);
      }
    }
  };

  useEffect(() => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }
    void loadUsers();
    const intervalId = window.setInterval(() => {
      void loadUsers({ silent: true });
    }, 15000);

    return () => window.clearInterval(intervalId);
  }, [navigate]);

  const updateDraft = (hhId: string, patch: Partial<{ periodType: string; periodEndsOn: string; trial3dGranted: boolean }>) => {
    setSubscriptionDrafts((previous) => ({
      ...previous,
      [hhId]: {
        periodType: previous[hhId]?.periodType ?? 'inactive',
        periodEndsOn: previous[hhId]?.periodEndsOn ?? '',
        trial3dGranted: previous[hhId]?.trial3dGranted ?? false,
        ...patch,
      },
    }));
  };

  const handleSaveSubscription = async (hhId: string) => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }

    const draft = subscriptionDrafts[hhId];
    if (!draft) return;

    setSavingByUser((previous) => ({ ...previous, [hhId]: true }));
    setError('');

    try {
      const response = await fetch(ADMIN_API.userSubscription(hhId), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        credentials: 'include',
        body: JSON.stringify({
          period_type: draft.periodType,
          period_ends_on: draft.periodEndsOn || null,
          trial_3d_granted: draft.trial3dGranted,
        }),
      });

      if (response.status === 401) {
        window.localStorage.removeItem(ADMIN_STORAGE_KEY);
        navigate(ADMIN_ROUTES.login, { replace: true });
        return;
      }

      if (!response.ok) {
        throw new Error('Не удалось сохранить период.');
      }

      const updated = (await response.json()) as {
        hh_id: string;
        subscription_status: string | null;
        subscription_expires_at: string | null;
        trial_3d_granted: boolean | null;
      };
      setUsers((previous) =>
        previous.map((user) =>
          user.hh_id === updated.hh_id
            ? {
                ...user,
                subscription_status: updated.subscription_status,
                subscription_expires_at: updated.subscription_expires_at,
                trial_3d_granted: updated.trial_3d_granted,
              }
            : user
        )
      );
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Не удалось сохранить период.');
    } finally {
      setSavingByUser((previous) => ({ ...previous, [hhId]: false }));
    }
  };

  return (
    <main className="page">
      <section className="card">
        <h1>Панель администратора</h1>

        {error ? <p className="error">{error}</p> : null}

        <div className="tableHeaderRow">
          <p>Пользователи, вошедшие через HH: {users.length}</p>
          <div className="tableActionsInline">
            <button type="button" onClick={() => navigate(ADMIN_ROUTES.support)}>
              Поддержка
              {unreadSupportCount > 0 ? <span className="admin-badge">{unreadSupportCount}</span> : null}
            </button>
            <button type="button" onClick={() => void loadUsers()} disabled={refreshing}>
              {refreshing ? 'Обновляю...' : 'Обновить'}
            </button>
          </div>
        </div>
        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Компания</th>
                <th>Пользователь</th>
                <th>Последний вход</th>
                <th>Тип подписки</th>
                <th>Триал 3 дня</th>
                <th>Окончание подписки</th>
                <th>Биллинг</th>
                <th>Интерфейс</th>
                <th>Аккаунт</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.hh_id}>
                  <td>{user.company_name ?? '—'}</td>
                  <td>{user.name}</td>
                  <td>{new Date(user.last_login).toLocaleString()}</td>
                  <td>
                    <select
                      className="tableSelect"
                      value={subscriptionDrafts[user.hh_id]?.periodType ?? 'inactive'}
                      onChange={(event) => updateDraft(user.hh_id, { periodType: event.target.value })}
                    >
                      <option value="inactive">Без подписки</option>
                      <option value="trial_3d">Тест 3 дня</option>
                      <option value="paid_1m">Оплачено: 1 месяц</option>
                      <option value="paid_6m">Оплачено: 6 месяцев</option>
                      <option value="paid_1y">Оплачено: 1 год</option>
                    </select>
                  </td>
                  <td>
                    <select
                      className="tableSelect"
                      value={subscriptionDrafts[user.hh_id]?.trial3dGranted ? 'yes' : 'no'}
                      onChange={(event) => updateDraft(user.hh_id, { trial3dGranted: event.target.value === 'yes' })}
                    >
                      <option value="yes">Было</option>
                      <option value="no">Не было</option>
                    </select>
                    <div className="tableMetaText">Сейчас: {Boolean(user.trial_3d_granted) ? 'Было' : 'Не было'}</div>
                  </td>
                  <td>
                    <input
                      className="tableDateInput"
                      type="date"
                      value={subscriptionDrafts[user.hh_id]?.periodEndsOn ?? ''}
                      onChange={(event) => updateDraft(user.hh_id, { periodEndsOn: event.target.value })}
                    />
                    <div className="tableMetaText">Сейчас: {getAdminPeriodLabel(user.subscription_status)}</div>
                    <div className="tableMetaText">
                      Текущая дата: {user.subscription_expires_at ? new Date(user.subscription_expires_at).toLocaleDateString() : '—'}
                    </div>
                  </td>
                  <td>
                    <div className="tableMetaText">План: {user.plan_code ?? '—'}</div>
                    <div className="tableMetaText">
                      Период: {user.current_period_end ? new Date(user.current_period_end).toLocaleDateString() : '—'}
                    </div>
                    <div className="tableMetaText">Статус: {user.billing_status ?? '—'}</div>
                  </td>
                  <td>
                    {user.selected_interface ? (
                      <span className="admin-theme-cell" title={user.selected_interface}>
                        <span
                          className={`admin-theme-swatch ${THEME_SWATCH_CLASS[user.selected_interface] ?? 'admin-theme-preview-default'}`}
                          aria-hidden="true"
                        />
                        <span>{user.selected_interface}</span>
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>
                    <div className="tableActions">
                      <button type="button" onClick={() => handleSaveSubscription(user.hh_id)} disabled={savingByUser[user.hh_id]}>
                        {savingByUser[user.hh_id] ? 'Сохраняю...' : 'Сохранить'}
                      </button>
                      <button type="button" onClick={() => navigate(ADMIN_ROUTES.userDetails(user.hh_id))}>
                        Открыть
                      </button>
                      <button type="button" onClick={() => navigate(ADMIN_ROUTES.userOperations(user.hh_id))}>
                        Операции
                      </button>
                    </div>
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
