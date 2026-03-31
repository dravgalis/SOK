const API_BASE_URL = 'https://sok-i9cq.onrender.com';

export const AUTH_ENDPOINTS = {
  hhLogin: `${API_BASE_URL}/api/auth/hh/login`,
} as const;

export const APP_ENDPOINTS = {
  me: `${API_BASE_URL}/api/me`,
  vacancies: `${API_BASE_URL}/api/vacancies`,
  vacancyById: (vacancyId: string) => `${API_BASE_URL}/api/vacancies/${vacancyId}`,
  vacancyResponses: (vacancyId: string) => `${API_BASE_URL}/api/vacancies/${vacancyId}/responses`,
} as const;

export const APP_ROUTES = {
  login: '/',
  app: '/app',
  vacancyDetails: '/app/vacancies/:vacancyId',
} as const;
