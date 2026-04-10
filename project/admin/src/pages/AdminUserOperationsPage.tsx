import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type BillingOperation = {
  payment_id: string;
  plan_code: string;
  amount: string;
  currency: string;
  status: string;
  failure_reason?: string | null;
  created_at?: string | null;
};

export function AdminUserOperationsPage() {
  const { hhId = '' } = useParams();
  const navigate = useNavigate();
  const [operations, setOperations] = useState<BillingOperation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      const token = window.localStorage.getItem(ADMIN_STORAGE_KEY);
      if (!token) {
        navigate(ADMIN_ROUTES.login, { replace: true });
        return;
      }
      try {
        setLoading(true);
        setError('');
        const response = await fetch(ADMIN_API.billingOperations(hhId), {
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error('Не удалось загрузить операции.');
        }
        const payload = (await response.json()) as { operations: BillingOperation[] };
        setOperations(payload.operations || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить операции.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [hhId, navigate]);

  return (
    <main className="page">
      <section className="card">
        <h1>Операции пользователя</h1>
        <p>HH ID: {hhId}</p>
        {loading ? <p>Загрузка...</p> : null}
        {error ? <p className="error">{error}</p> : null}
        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>ID платежа</th>
                <th>Дата</th>
                <th>Сумма</th>
                <th>План</th>
                <th>Статус</th>
                <th>Причина</th>
              </tr>
            </thead>
            <tbody>
              {operations.map((operation) => (
                <tr key={operation.payment_id}>
                  <td>{operation.payment_id}</td>
                  <td>{operation.created_at ? new Date(operation.created_at).toLocaleString() : '—'}</td>
                  <td>
                    {operation.amount} {operation.currency}
                  </td>
                  <td>{operation.plan_code}</td>
                  <td>
                    <span className={operation.status === 'succeeded' ? 'statusChip statusChipSuccess' : 'statusChip statusChipError'}>
                      {operation.status}
                    </span>
                  </td>
                  <td>{operation.status === 'succeeded' ? '—' : operation.failure_reason || 'Неизвестно'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ marginTop: 16 }}>
          <Link to={ADMIN_ROUTES.dashboard}>← Назад в админку</Link>
        </div>
      </section>
    </main>
  );
}
