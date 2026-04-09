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
  selected_interface: string | null;
  created_at: string;
  last_login: string;
};

function getAdminPeriodLabel(status: string | null): string {
  if (!status) return '—';

  const labelMap: Record<string, string> = {
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
  const [subscriptionDrafts, setSubscriptionDrafts] = useState<Record<string, { periodType: string; periodEndsOn: string }>>(
    {}
  );
  const [savingByUser, setSavingByUser] = useState<Record<string, boolean>>({});

  const toDateInputValue = (value: string | null): string => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toISOString().slice(0, 10);
  };

  useEffect(() => {
    const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);

    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }

    const loadUsers = async () => {
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
          throw new Error('Failed to load HH users data.');
        }

        const payload = (await response.json()) as AdminUser[];
        setUsers(payload);
        setSubscriptionDrafts(
          payload.reduce<Record<string, { periodType: string; periodEndsOn: string }>>((acc, user) => {
            acc[user.hh_id] = {
              periodType: user.subscription_status ?? 'trial_3d',
              periodEndsOn: toDateInputValue(user.subscription_expires_at),
            };
            return acc;
          }, {})
        );
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load HH users data.');
      }
    };

    void loadUsers();
  }, [navigate]);

  const updateDraft = (hhId: string, patch: Partial<{ periodType: string; periodEndsOn: string }>) => {
    setSubscriptionDrafts((previous) => ({
      ...previous,
      [hhId]: {
        periodType: previous[hhId]?.periodType ?? 'trial_3d',
        periodEndsOn: previous[hhId]?.periodEndsOn ?? '',
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

      const updated = (await response.json()) as { hh_id: string; subscription_status: string; subscription_expires_at: string | null };
      setUsers((previous) =>
        previous.map((user) =>
          user.hh_id === updated.hh_id
            ? {
                ...user,
                subscription_status: updated.subscription_status,
                subscription_expires_at: updated.subscription_expires_at,
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
        <h1>Admin Dashboard</h1>

        {error ? <p className="error">{error}</p> : null}

        <p>Users who logged in via HH: {users.length}</p>
        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>User</th>
                <th>Last login</th>
                <th>Period type</th>
                <th>Period ends</th>
                <th>Selected interface</th>
                <th>Account</th>
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
                      value={subscriptionDrafts[user.hh_id]?.periodType ?? 'trial_3d'}
                      onChange={(event) => updateDraft(user.hh_id, { periodType: event.target.value })}
                    >
                      <option value="trial_3d">Тест 3 дня</option>
                      <option value="paid_1m">Оплачено: 1 месяц</option>
                      <option value="paid_6m">Оплачено: 6 месяцев</option>
                      <option value="paid_1y">Оплачено: 1 год</option>
                    </select>
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
                  <td>{user.selected_interface ?? '—'}</td>
                  <td>
                    <div className="tableActions">
                      <button type="button" onClick={() => handleSaveSubscription(user.hh_id)} disabled={savingByUser[user.hh_id]}>
                        {savingByUser[user.hh_id] ? 'Saving...' : 'Save period'}
                      </button>
                      <button type="button" onClick={() => navigate(ADMIN_ROUTES.userDetails(user.hh_id))}>
                        Open
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
