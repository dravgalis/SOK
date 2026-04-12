import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_ENDPOINTS, APP_ROUTES } from '../config';
import { SupportChatWidget } from '../components/SupportChatWidget';

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
  const [supportSending, setSupportSending] = useState(false);

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

  const handleSupport = async () => {
    const message = window.prompt('Опишите ваш вопрос для поддержки:');
    if (!message || !message.trim()) return;
    try {
      setSupportSending(true);
      const response = await fetch(APP_ENDPOINTS.supportMessage, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message.trim() }),
      });
      if (!response.ok) {
        throw new Error('Не удалось отправить сообщение.');
      }
      window.alert('Сообщение отправлено в поддержку.');
    } catch {
      window.alert('Ошибка отправки в поддержку.');
    } finally {
      setSupportSending(false);
    }
  };

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
        <div className="page-top-link-row">
          <Link to={APP_ROUTES.app} className="back-link-button">
            ← Назад в кабинет
          </Link>
        </div>
        <h2>Операции</h2>
        <div className="operations-summary-grid">
          <article className="operations-summary-card">
            <span>Всего оплат</span>
            <strong>{totalOperations}</strong>
          </article>
          <article className="operations-summary-card">
            <span>Оплачено</span>
            <strong>{payload?.total_paid ?? 0} ₽</strong>
          </article>
          <article className="operations-summary-card">
            <span>Осталось</span>
            <strong>{payload?.days_left ?? 0} дн.</strong>
          </article>
        </div>
        {error ? <p className="status status-error">{error}</p> : null}

        <ul className="operations-list">
          {(payload?.operations || []).map((operation) => (
            <li key={operation.payment_id} className="operations-item">
              <div className="operations-item-head">
                <div className={`operation-badge ${operation.status === 'succeeded' ? 'operation-success' : 'operation-failed'}`}>
                  {operation.status === 'succeeded' ? 'Успешно' : 'Ошибка'}
                </div>
                <strong>
                  {operation.amount} {operation.currency}
                </strong>
              </div>
              <p>ID: {operation.payment_id}</p>
              <p>План: {operation.plan_code}</p>
              <p>Продлено на: {operation.months_extended} мес.</p>
              <p>Дата: {operation.created_at ? new Date(operation.created_at).toLocaleString() : '—'}</p>
              {operation.status !== 'succeeded' ? <p>Причина: {operation.reason || 'Неизвестно'}</p> : null}
            </li>
          ))}
        </ul>

      </section>
      <SupportChatWidget />
    </main>
  );
}
