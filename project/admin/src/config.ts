export const ADMIN_API = {
  login: 'https://sok-i9cq.onrender.com/admin/login',
  users: 'https://sok-i9cq.onrender.com/admin/users',
  userVacancies: (hhId: string, force = false) =>
    `https://sok-i9cq.onrender.com/admin/users/${hhId}/vacancies${force ? '?force=true' : ''}`,
} as const;

export const ADMIN_ROUTES = {
  login: '/admin/login',
  dashboard: '/admin/dashboard',
  userDetails: (hhId: string) => `/admin/users/${hhId}`,
} as const;

export const ADMIN_STORAGE_KEY = 'admin_token';
