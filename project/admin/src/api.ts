const API_BASE_URL = 'https://sok-i9cq.onrender.com';

export const ADMIN_ENDPOINTS = {
  me: `${API_BASE_URL}/api/me`,
  vacancies: `${API_BASE_URL}/api/vacancies`,
  vacancyResponses: (vacancyId: string) => `${API_BASE_URL}/api/vacancies/${vacancyId}/responses`,
} as const;

export type MeResponse = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  name: string | null;
  avatar_url: string | null;
  company_name: string | null;
  company_logo_url: string | null;
};

export type Vacancy = {
  id: string;
  name: string;
  normalized_status: string;
  responses_count: number;
};

export type VacanciesResponse = {
  active: Vacancy[];
  archived: Vacancy[];
  counts: {
    active: number;
    archived: number;
  };
};

export type Candidate = {
  response_id: string;
  candidate_name: string | null;
  resume_title: string | null;
  status: string | null;
};

export async function fetchMe(): Promise<MeResponse> {
  const response = await fetch(ADMIN_ENDPOINTS.me, { credentials: 'include' });
  if (!response.ok) {
    throw new Error('Failed to fetch profile. Please login first.');
  }
  return response.json() as Promise<MeResponse>;
}

export async function fetchVacancies(): Promise<VacanciesResponse> {
  const response = await fetch(ADMIN_ENDPOINTS.vacancies, { credentials: 'include' });
  if (!response.ok) {
    throw new Error('Failed to fetch vacancies.');
  }
  return response.json() as Promise<VacanciesResponse>;
}

export async function fetchCandidatesFromFirstVacancy(): Promise<Candidate[]> {
  const vacancies = await fetchVacancies();
  const firstVacancy = vacancies.active[0] ?? vacancies.archived[0];

  if (!firstVacancy) {
    return [];
  }

  const response = await fetch(ADMIN_ENDPOINTS.vacancyResponses(firstVacancy.id), {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error('Failed to fetch candidates.');
  }

  const payload = (await response.json()) as { items?: Candidate[] };
  return payload.items ?? [];
}
