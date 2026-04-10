import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ENDPOINTS, APP_ROUTES } from '../config';

type Operation = {
  payment_id: string;
  plan_code: string;
  months_extended: number;
  amount: string;
  currency: string;
  status: string;
  reason?: string | null;
  created_at?: string | null;
  processed_at?: string | null;
};

type OperationsPayload = {
  operations: Operation[];
  total_paid: number;
  days_left: number;
};

export function OperationsPage() {
  const [payload, setPayload] = useState<OperationsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        setError('');
        const response = await fetch(APP_ENDPOINTS.operations, { credentials: 'include' });
        if (!response.ok) {
          throw new Error('Не удалось загрузить операции.');
        }
        setPayload((await response.json()) as OperationsPayload);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить операции.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, []);

  const totalOperations = useMemo(() => payload?.operations.length ?? 0, [payload]);

  if (loading) {
    return (
      <main className="page page-top">
        <section className="card dashboard-card">
          <p>Загружаем операции...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="page page-top">
      <section className="card dashboard-card dashboard-wide">
        <h2>Операции</h2>
        <p>
          Всего оплат: <strong>{totalOperations}</strong> · Оплачено: <strong>{payload?.total_paid ?? 0} ₽</strong> · Осталось:{' '}
          <strong>{payload?.days_left ?? 0} дн.</strong>
        </p>
        {error ? <p className="status status-error">{error}</p> : null}

        <ul className="vacancies-list">
          {(payload?.operations || []).map((operation) => (
            <li key={operation.payment_id} className="vacancy-item">
              <div className={`operation-badge ${operation.status === 'succeeded' ? 'operation-success' : 'operation-failed'}`}>
                {operation.status === 'succeeded' ? 'Успешно' : 'Ошибка'}
              </div>
              <p>ID: {operation.payment_id}</p>
              <p>
                Сумма: {operation.amount} {operation.currency}
              </p>
              <p>План: {operation.plan_code}</p>
              <p>Продлено на: {operation.months_extended} мес.</p>
              <p>Дата: {operation.created_at ? new Date(operation.created_at).toLocaleString() : '—'}</p>
              {operation.status !== 'succeeded' ? <p>Причина: {operation.reason || 'Неизвестно'}</p> : null}
            </li>
          ))}
        </ul>

        <Link to={APP_ROUTES.app}>← Назад в кабинет</Link>
      </section>
    </main>
  );
}
