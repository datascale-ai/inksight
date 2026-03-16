import { apiRequest } from '@/lib/api-client';

export type UserPreferences = {
  user_id: number;
  push_enabled: boolean;
  push_time: string;
  push_modes: string[];
  widget_mode: string;
  locale: string;
  timezone: string;
};

export async function getPreferences(token: string) {
  return apiRequest<UserPreferences>('/user/preferences', { token });
}

export async function updatePreferences(token: string, body: Partial<UserPreferences>) {
  return apiRequest<{ ok: boolean; preferences: UserPreferences }>('/user/preferences', {
    method: 'PUT',
    token,
    body,
  });
}
