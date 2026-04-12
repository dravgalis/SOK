import { useEffect, useMemo, useState } from 'react';
import { APP_ENDPOINTS } from '../config';

type SupportMessage = {
  message_id: string;
  hh_id: string;
  message: string;
  sender_role: 'user' | 'admin';
  created_at: string;
};

export function SupportChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [unreadCount, setUnreadCount] = useState(0);
  const [sending, setSending] = useState(false);

  const loadChat = async () => {
    const response = await fetch(APP_ENDPOINTS.supportChat, { credentials: 'include' });
    if (!response.ok) {
      return;
    }
    const payload = (await response.json()) as { messages?: SupportMessage[]; unread_for_user?: number };
    setMessages(payload.messages || []);
    setUnreadCount(payload.unread_for_user ?? 0);
  };

  useEffect(() => {
    void loadChat();
    const id = window.setInterval(() => void loadChat(), 10000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!open || unreadCount <= 0) return;
    const markRead = async () => {
      await fetch(APP_ENDPOINTS.supportChatRead, {
        method: 'POST',
        credentials: 'include',
      });
      setUnreadCount(0);
    };
    void markRead();
  }, [open, unreadCount]);

  const sortedMessages = useMemo(
    () => [...messages].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
    [messages]
  );

  const sendMessage = async () => {
    const message = draft.trim();
    if (!message) return;
    try {
      setSending(true);
      const response = await fetch(APP_ENDPOINTS.supportMessage, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      if (!response.ok) return;
      setDraft('');
      await loadChat();
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="support-widget">
      {open ? (
        <div className="support-chat-panel">
          <div className="support-chat-head">
            <strong>Поддержка</strong>
            <button type="button" onClick={() => setOpen(false)}>
              ✕
            </button>
          </div>
          <div className="support-chat-list">
            {sortedMessages.map((item) => (
              <div key={item.message_id} className={`support-chat-bubble ${item.sender_role === 'admin' ? 'support-chat-bubble-admin' : ''}`}>
                <p>{item.message}</p>
                <small>{new Date(item.created_at).toLocaleString()}</small>
              </div>
            ))}
          </div>
          <div className="support-chat-input">
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Введите сообщение..." />
            <button type="button" onClick={() => void sendMessage()} disabled={sending}>
              {sending ? 'Отправка...' : 'Отправить'}
            </button>
          </div>
        </div>
      ) : null}
      <button type="button" className="support-fab" onClick={() => setOpen((value) => !value)}>
        Связаться с поддержкой
        {unreadCount > 0 ? <span className="support-badge">{unreadCount}</span> : null}
      </button>
    </div>
  );
}
