export type AuthStatus = 'idle' | 'loading' | 'success' | 'error';

export interface HhCallbackRequest {
  code: string;
  state: string;
}

export interface HhCallbackResponse {
  success: boolean;
  redirectTo?: string;
  message?: string;
}
