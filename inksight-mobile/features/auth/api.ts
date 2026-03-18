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

type RegisterPayload = {
  username: string;
  password: string;
  phone?: string;
  email?: string;
};

export async function register({ username, password, phone, email }: RegisterPayload) {
  return apiRequest<AuthResponse>('/auth/register', {
    method: 'POST',
    body: { username, password, phone, email },
    token: null,
  });
}

export async function me(token: string) {
  return apiRequest<AuthUser>('/auth/me', { token });
}
