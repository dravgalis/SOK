const API_BASE_URL = 'https://sok-i9cq.onrender.com';

export const ADMIN_ENDPOINTS = {
  login: `${API_BASE_URL}/admin/login`,
  users: `${API_BASE_URL}/admin/users`,
} as const;

export type AdminUser = {
  hh_id: string;
  name: string;
  email: string | null;
  created_at: string;
  last_login: string;
};

export async function adminLogin(login: string, password: string): Promise<string> {
  const response = await fetch(ADMIN_ENDPOINTS.login, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ login, password }),
  });

  if (!response.ok) {
    throw new Error('Неверный логин или пароль.');
  }

  const payload = (await response.json()) as { token?: string };
  if (!payload.token) {
    throw new Error('Токен авторизации не получен.');
  }

  return payload.token;
}

export async function fetchAdminUsers(token: string): Promise<AdminUser[]> {
  const response = await fetch(ADMIN_ENDPOINTS.users, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Сессия истекла. Войдите снова.');
    }

    throw new Error('Не удалось загрузить пользователей.');
  }

  return response.json() as Promise<AdminUser[]>;
}
