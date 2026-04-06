const API_BASE_URL = 'https://sok-i9cq.onrender.com';

export const ADMIN_API = {
  login: `${API_BASE_URL}/api/admin/login`,
  usersCount: `${API_BASE_URL}/api/admin/users-count`,
} as const;

export const ADMIN_ROUTES = {
  login: '/admin/login',
  dashboard: '/admin/dashboard',
} as const;

export const ADMIN_STORAGE_KEY = 'admin_authenticated';
