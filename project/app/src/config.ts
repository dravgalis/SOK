const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export const AUTH_ENDPOINTS = {
  hhLogin: `${API_BASE_URL}/api/auth/hh/login`,
} as const;
