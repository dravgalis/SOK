import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ADMIN_API, ADMIN_ROUTES, ADMIN_STORAGE_KEY } from '../config';

type SupportChat = {
  hh_id: string;
  company_name: string | null;
  unread_by_admin: number;
  last_message_at: string;
};

type SupportMessage = {
  message_id: string;
  hh_id: string;
  message: string;
  sender_role: 'user' | 'admin';
  created_at: string;
};

export function AdminSupportMessagesPage() {
  const navigate = useNavigate();
  const [chats, setChats] = useState<SupportChat[]>([]);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [selectedHhId, setSelectedHhId] = useState('');
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const selectedChat = chats.find((chat) => chat.hh_id === selectedHhId);

  const getToken = () => window.localStorage.getItem(ADMIN_STORAGE_KEY);

  const loadChats = async () => {
    const token = getToken();
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }
    try {
      setLoading(true);
      const response = await fetch(ADMIN_API.supportChats, {
        headers: { Authorization: `Bearer ${token}` },
        credentials: 'include',
      });
      if (response.status === 401) {
        window.localStorage.removeItem(ADMIN_STORAGE_KEY);
        navigate(ADMIN_ROUTES.login, { replace: true });
        return;
      }
      if (!response.ok) throw new Error('Не удалось загрузить чаты.');
      const payload = (await response.json()) as { chats: SupportChat[] };
      const nextChats = payload.chats || [];
      setChats(nextChats);
      if (!selectedHhId && nextChats.length > 0) {
        setSelectedHhId(nextChats[0].hh_id);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить чаты.');
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (hhId: string) => {
    const token = getToken();
    if (!token || !hhId) return;
    const response = await fetch(ADMIN_API.supportChatMessages(hhId), {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    });
    if (!response.ok) return;
    const payload = (await response.json()) as { messages: SupportMessage[] };
    setMessages(payload.messages || []);
    await fetch(ADMIN_API.supportChatRead(hhId), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    });
    await loadChats();
  };

  useEffect(() => {
    void loadChats();
    const id = window.setInterval(() => void loadChats(), 10000);
    return () => window.clearInterval(id);
  }, [navigate]);

  useEffect(() => {
    if (!selectedHhId) return;
    void loadMessages(selectedHhId);
  }, [selectedHhId]);

  const handleReply = async () => {
    const token = getToken();
    const message = replyText.trim();
    if (!token || !selectedHhId || !message) return;
    await fetch(ADMIN_API.supportChatReply(selectedHhId), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      credentials: 'include',
      body: JSON.stringify({ message }),
    });
    setReplyText('');
    await loadMessages(selectedHhId);
  };

  return (
    <main className="page">
      <section className="card">
        <div className="tableHeaderRow">
          <h1>Поддержка</h1>
          <button type="button" onClick={() => navigate(ADMIN_ROUTES.dashboard)} className="back-link-button">
            ← Назад в админку
          </button>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="admin-chat-layout">
          <aside className="admin-chat-list">
            {loading ? <p>Загрузка...</p> : null}
            {chats.map((chat) => (
              <button
                key={chat.hh_id}
                type="button"
                className={`admin-chat-item ${selectedHhId === chat.hh_id ? 'admin-chat-item-active' : ''}`}
                onClick={() => setSelectedHhId(chat.hh_id)}
              >
                <strong>HH ID: {chat.hh_id}</strong>
                <span className="admin-chat-company">Компания: {chat.company_name || 'Не указана'}</span>
                <small>{chat.last_message_at ? new Date(chat.last_message_at).toLocaleString() : '—'}</small>
                {chat.unread_by_admin > 0 ? <span className="admin-badge">{chat.unread_by_admin}</span> : null}
              </button>
            ))}
          </aside>
          <section className="admin-chat-thread">
            {selectedHhId ? (
              <h3>
                Чат c HH ID {selectedHhId}
                {selectedChat?.company_name ? ` · ${selectedChat.company_name}` : ''}
              </h3>
            ) : (
              <h3>Выберите чат</h3>
            )}
            <div className="admin-chat-messages">
              {messages.map((item) => (
                <div key={item.message_id} className={`admin-chat-bubble ${item.sender_role === 'admin' ? 'admin-chat-bubble-me' : ''}`}>
                  <p>{item.message}</p>
                  <small>{new Date(item.created_at).toLocaleString()}</small>
                </div>
              ))}
            </div>
            {selectedHhId ? (
              <div className="admin-chat-reply">
                <textarea value={replyText} onChange={(event) => setReplyText(event.target.value)} placeholder="Ответить..." />
                <button type="button" onClick={() => void handleReply()}>
                  Отправить
                </button>
              </div>
            ) : null}
          </section>
        </div>
      </section>
    </main>
  );
}
