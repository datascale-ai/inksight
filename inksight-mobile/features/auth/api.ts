import { apiRequest } from '@/lib/api-client';

export type AuthUser = {
  user_id: number;
  username: string;
  created_at?: string;
};

type AuthResponse = {
  ok: boolean;
  token: string;
  user_id: number;
  username: string;
};

export async function login(username: string, password: string) {
  return apiRequest<AuthResponse>('/auth/login', {
    method: 'POST',
    body: { username, password },
    token: null,
  });
}

export async function register(
  username: string,
  password: string,
  extra?: { phone?: string; email?: string },
) {
  return apiRequest<AuthResponse>('/auth/register', {
    method: 'POST',
    body: { username, password, ...(extra || {}) },
    token: null,
  });
}

export async function me(token: string) {
  return apiRequest<AuthUser>('/auth/me', { token });
}

export async function sendResetCode(email: string) {
  return apiRequest<{ ok: boolean; message: string }>('/auth/reset-password/send-code', {
    method: 'POST',
    body: { email },
    token: null,
  });
}

export async function resetPasswordWithCode(email: string, code: string, password: string) {
  return apiRequest<{ ok: boolean; message: string }>('/auth/reset-password', {
    method: 'POST',
    body: { email, code, password },
    token: null,
  });
}
