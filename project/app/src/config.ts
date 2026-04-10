const API_BASE_URL = 'https://sok-i9cq.onrender.com';

export const AUTH_ENDPOINTS = {
  hhLogin: `${API_BASE_URL}/api/auth/hh/login`,
} as const;

export const APP_ENDPOINTS = {
  me: `${API_BASE_URL}/api/me`,
  billingMe: `${API_BASE_URL}/api/billing/me`,
  createPayment: `${API_BASE_URL}/api/billing/create-payment`,
  autoRenew: `${API_BASE_URL}/api/billing/auto-renew`,
  vacancies: `${API_BASE_URL}/api/vacancies`,
  vacancyById: (vacancyId: string) => `${API_BASE_URL}/api/vacancies/${vacancyId}`,
  vacancyResponses: (vacancyId: string) => `${API_BASE_URL}/api/vacancies/${vacancyId}/responses`,
} as const;

export const APP_ROUTES = {
  login: '/',
  app: '/app',
  paymentReturn: '/app/payment-return',
  vacancyDetails: '/app/vacancies/:vacancyId',
} as const;
