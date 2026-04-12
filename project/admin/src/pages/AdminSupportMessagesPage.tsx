import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type SupportMessage = {
  message_id: string;
  hh_id: string;
  message: string;
  created_at: string;
};

export function AdminSupportMessagesPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

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
        const response = await fetch(ADMIN_API.supportMessages, {
          headers: { Authorization: `Bearer ${token}` },
          credentials: 'include',
        });
        if (response.status === 401) {
          window.localStorage.removeItem(ADMIN_STORAGE_KEY);
          navigate(ADMIN_ROUTES.login, { replace: true });
          return;
        }
        if (!response.ok) {
          throw new Error('Не удалось загрузить сообщения поддержки.');
        }
        const payload = (await response.json()) as { messages: SupportMessage[] };
        setMessages(payload.messages || []);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить сообщения поддержки.');
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [navigate]);

  return (
    <main className="page">
      <section className="card">
        <div className="tableHeaderRow">
          <h1>Сообщения в поддержку</h1>
          <button type="button" onClick={() => navigate(ADMIN_ROUTES.dashboard)}>
            ← Назад в админку
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        {loading ? <p>Загрузка...</p> : null}
        {!loading && messages.length === 0 ? <p>Сообщений пока нет.</p> : null}
        <div className="tableWrapper">
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>HH ID</th>
                <th>Сообщение</th>
              </tr>
            </thead>
            <tbody>
              {messages.map((item) => (
                <tr key={item.message_id}>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td>{item.hh_id}</td>
                  <td>{item.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
