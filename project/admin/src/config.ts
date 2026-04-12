export const ADMIN_API = {
  login: 'https://sok-i9cq.onrender.com/admin/login',
  users: 'https://sok-i9cq.onrender.com/admin/users',
  userSubscription: (hhId: string) => `https://sok-i9cq.onrender.com/admin/users/${hhId}/subscription`,
  billingOperations: (hhId: string) => `https://sok-i9cq.onrender.com/admin/users/${hhId}/billing-operations`,
  userVacancies: (hhId: string, force = false) =>
    `https://sok-i9cq.onrender.com/admin/users/${hhId}/vacancies${force ? '?force=true' : ''}`,
  vacancyResponses: (hhId: string, vacancyId: string, force = false) =>
    `https://sok-i9cq.onrender.com/admin/users/${hhId}/vacancies/${vacancyId}/responses${force ? '?force=true' : ''}`,
  supportMessages: 'https://sok-i9cq.onrender.com/admin/support-messages',
  supportChats: 'https://sok-i9cq.onrender.com/admin/support-chats',
  supportEvents: (token: string) =>
    `https://sok-i9cq.onrender.com/admin/support/events?token=${encodeURIComponent(token)}`,
  supportChatMessages: (hhId: string) => `https://sok-i9cq.onrender.com/admin/support-chats/${hhId}`,
  supportChatRead: (hhId: string) => `https://sok-i9cq.onrender.com/admin/support-chats/${hhId}/read`,
  supportChatReply: (hhId: string) => `https://sok-i9cq.onrender.com/admin/support-chats/${hhId}/reply`,
} as const;

export const ADMIN_ROUTES = {
  login: '/admin/login',
  dashboard: '/admin/dashboard',
  support: '/admin/support',
  userDetails: (hhId: string) => `/admin/users/${hhId}`,
  userOperations: (hhId: string) => `/admin/users/${hhId}/operations`,
  vacancyResponses: (hhId: string, vacancyId: string) => `/admin/users/${hhId}/vacancies/${vacancyId}/responses`,
} as const;

export const ADMIN_STORAGE_KEY = 'admin_token';
