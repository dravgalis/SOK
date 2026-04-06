export const ADMIN_API = {
  login: 'https://sok-i9cq.onrender.com/api/admin/login',
  usersCount: 'https://sok-i9cq.onrender.com/api/admin/users-count',
} as const;

export const ADMIN_ROUTES = {
  login: '/admin/login',
  dashboard: '/admin/dashboard',
} as const;

export const ADMIN_STORAGE_KEY = 'admin_authenticated';
