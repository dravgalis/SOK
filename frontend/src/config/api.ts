export const AUTH_ENDPOINTS = {
  hhLogin: '/api/auth/hh/login',
  hhCallback: '/api/auth/hh/callback',
} as const;

export const APP_ROUTES = {
  root: '/',
  hhCallback: '/auth/hh/callback',
  app: '/app',
} as const;
