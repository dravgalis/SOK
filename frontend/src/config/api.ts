const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'https://sok-i9cq.onrender.com').replace(/\/$/, '');

export const AUTH_ENDPOINTS = {
  hhLogin: `${API_BASE_URL}/api/auth/hh/login`,
  hhCallback: `${API_BASE_URL}/api/auth/hh/callback`,
} as const;

export const APP_ROUTES = {
  root: '/',
  hhCallback: '/auth/hh/callback',
  app: '/app',
} as const;
