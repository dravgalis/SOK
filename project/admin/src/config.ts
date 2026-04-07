export const ADMIN_API = {
  login: 'https://sok-i9cq.onrender.com/admin/login',
  users: 'https://sok-i9cq.onrender.com/admin/users',
} as const;

export const ADMIN_ROUTES = {
  login: '/admin/login',
  dashboard: '/admin/dashboard',
} as const;

export const ADMIN_STORAGE_KEY = 'admin_token';
