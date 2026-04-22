import { useCallback, useEffect, useRef, useState } from 'react';
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
  const PAGE_SIZE = 25;
  const navigate = useNavigate();
  const [chats, setChats] = useState<SupportChat[]>([]);
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [selectedHhId, setSelectedHhId] = useState('');
  const [replyText, setReplyText] = useState('');
  const [error, setError] = useState('');
  const [loadingOlderMessages, setLoadingOlderMessages] = useState(false);
  const selectedChat = chats.find((chat) => chat.hh_id === selectedHhId);

  const unreadByChatRef = useRef<Record<string, number>>({});
  const hasLoadedChatsRef = useRef(false);
  const selectedHhIdRef = useRef('');
  const oldestLoadedAtRef = useRef<string | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

  const canNotify = () => typeof window !== 'undefined' && 'Notification' in window && Notification.permission === 'granted';

  const notifyAboutNewMessages = (nextChats: SupportChat[]) => {
    if (!hasLoadedChatsRef.current || !canNotify()) return;

    const prevUnreadMap = unreadByChatRef.current;
    const increased = nextChats.filter((chat) => (chat.unread_by_admin ?? 0) > (prevUnreadMap[chat.hh_id] ?? 0));
    if (!increased.length) return;

    if (increased.length === 1) {
      const chat = increased[0];
      const delta = (chat.unread_by_admin ?? 0) - (prevUnreadMap[chat.hh_id] ?? 0);
      new Notification('Новое сообщение в поддержке', {
        body: `HH ID: ${chat.hh_id}${chat.company_name ? ` · ${chat.company_name}` : ''} (+${delta})`,
        tag: `support-chat-${chat.hh_id}` ,
      });
      return;
    }

    new Notification('Новые сообщения в поддержке', {
      body: `Новых чатов с сообщениями: ${increased.length}`,
      tag: 'support-chat-multi',
    });
  };

  const getToken = () => window.localStorage.getItem(ADMIN_STORAGE_KEY);

  const loadChats = useCallback(async () => {
    const token = getToken();
    if (!token) {
      navigate(ADMIN_ROUTES.login, { replace: true });
      return;
    }
    try {
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
      notifyAboutNewMessages(nextChats);
      unreadByChatRef.current = nextChats.reduce<Record<string, number>>((acc, chat) => {
        acc[chat.hh_id] = chat.unread_by_admin ?? 0;
        return acc;
      }, {});
      hasLoadedChatsRef.current = true;
      if (nextChats.length > 0) {
        setSelectedHhId((prev) => prev || nextChats[0].hh_id);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Не удалось загрузить чаты.');
    }
  }, [navigate]);

  const loadMessages = useCallback(async (hhId: string, loadOlder = false) => {
    const token = getToken();
    if (!token || !hhId) return;
    const requestUrl = new URL(ADMIN_API.supportChatMessages(hhId));
    requestUrl.searchParams.set('limit', String(PAGE_SIZE));
    if (loadOlder && oldestLoadedAtRef.current) {
      requestUrl.searchParams.set('before', oldestLoadedAtRef.current);
    }

    const messagesContainer = messagesContainerRef.current;
    const previousHeight = messagesContainer?.scrollHeight ?? 0;
    const previousTop = messagesContainer?.scrollTop ?? 0;

    if (loadOlder) setLoadingOlderMessages(true);
    const response = await fetch(requestUrl.toString(), {
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    });
    if (!response.ok) {
      setLoadingOlderMessages(false);
      return;
    }
    const payload = (await response.json()) as { messages: SupportMessage[]; has_more?: boolean };
    const nextMessages = payload.messages || [];
    setHasMoreMessages(Boolean(payload.has_more));

    if (loadOlder) {
      setMessages((prev) => {
        if (!nextMessages.length) return prev;
        const known = new Set(prev.map((item) => item.message_id));
        const onlyNew = nextMessages.filter((item) => !known.has(item.message_id));
        const merged = [...onlyNew, ...prev];
        if (merged.length > 0) oldestLoadedAtRef.current = merged[0].created_at;
        return merged;
      });
    } else {
      setMessages(nextMessages);
      oldestLoadedAtRef.current = nextMessages.length > 0 ? nextMessages[0].created_at : null;
    }

    requestAnimationFrame(() => {
      const container = messagesContainerRef.current;
      if (!container) return;
      if (loadOlder) {
        const newHeight = container.scrollHeight;
        container.scrollTop = newHeight - previousHeight + previousTop;
      } else {
        container.scrollTop = container.scrollHeight;
      }
    });

    await fetch(ADMIN_API.supportChatRead(hhId), {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      credentials: 'include',
    });
    await loadChats();
    setLoadingOlderMessages(false);
  }, [loadChats, PAGE_SIZE]);

  useEffect(() => {
    selectedHhIdRef.current = selectedHhId;
  }, [selectedHhId]);

  useEffect(() => {
    void loadChats();
    const fullReloadId = window.setInterval(() => window.location.reload(), 30 * 60 * 1000);
    const fallbackPollingId = window.setInterval(() => void loadChats(), 5 * 60 * 1000);
    const token = getToken();
    const events = token ? new EventSource(ADMIN_API.supportEvents(token), { withCredentials: true }) : null;

    const onSupportMessage = (event: MessageEvent<string>) => {
      let chatId = '';
      try {
        const payload = JSON.parse(event.data) as { type?: string; chatId?: string };
        if (payload.type !== 'support_message') return;
        chatId = typeof payload.chatId === 'string' ? payload.chatId : '';
      } catch {
        return;
      }

      void loadChats();
      const currentSelected = selectedHhIdRef.current;
      if (currentSelected && (!chatId || chatId === currentSelected)) {
        void loadMessages(currentSelected);
      }
    };

    events?.addEventListener('support_message', onSupportMessage as EventListener);

    if ('Notification' in window && Notification.permission === 'default') {
      void Notification.requestPermission();
    }
    return () => {
      window.clearInterval(fallbackPollingId);
      window.clearInterval(fullReloadId);
      events?.removeEventListener('support_message', onSupportMessage as EventListener);
      events?.close();
    };
  }, [loadChats, loadMessages]);

  useEffect(() => {
    if (!selectedHhId) return;
    setMessages([]);
    setHasMoreMessages(false);
    oldestLoadedAtRef.current = null;
    void loadMessages(selectedHhId);
  }, [selectedHhId, loadMessages]);

  const handleMessagesScroll = () => {
    if (!selectedHhId || !hasMoreMessages || loadingOlderMessages) return;
    const container = messagesContainerRef.current;
    if (!container) return;
    if (container.scrollTop > 40) return;
    void loadMessages(selectedHhId, true);
  };

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
        <div className="support-layout admin-chat-layout">
          <aside className="chat-list admin-chat-list">
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
          <section className="chat-content admin-chat-thread">
            {selectedHhId ? (
              <h3>
                Чат c HH ID {selectedHhId}
                {selectedChat?.company_name ? ` · ${selectedChat.company_name}` : ''}
              </h3>
            ) : (
              <h3>Выберите чат</h3>
            )}
            <div className="admin-chat-messages" ref={messagesContainerRef} onScroll={handleMessagesScroll}>
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
