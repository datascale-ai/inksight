import { Platform } from 'react-native';
import { apiRequest } from '@/lib/api-client';
import {
  clearStoredPushRegistration,
  getStoredPushRegistration,
  setStoredPushRegistration,
} from '@/lib/storage';

export type PushRegistrationRecord = {
  id?: number;
  push_token: string;
  platform: string;
  timezone: string;
  push_time: string;
};

function getResolvedTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';
}

function getResolvedPlatform() {
  if (Platform.OS === 'ios' || Platform.OS === 'android') {
    return Platform.OS;
  }
  return 'expo';
}

function buildPreviewToken() {
  return `inksight-${getResolvedPlatform()}-${Date.now()}`;
}

export async function registerPushNotifications(token: string, pushTime: string) {
  const stored = await getStoredPushRegistration();
  const payload: PushRegistrationRecord = {
    push_token: stored?.push_token || buildPreviewToken(),
    platform: stored?.platform || getResolvedPlatform(),
    timezone: stored?.timezone || getResolvedTimezone(),
    push_time: pushTime,
  };

  const result = await apiRequest<{ ok: boolean; registration: PushRegistrationRecord }>('/push/register', {
    method: 'POST',
    token,
    body: payload,
  });
  await setStoredPushRegistration(payload);
  return result;
}

export async function unregisterPushNotifications(token: string) {
  const stored = await getStoredPushRegistration();
  if (!stored?.push_token) {
    return { ok: true, deleted: 0 };
  }

  const result = await apiRequest<{ ok: boolean; deleted: number }>('/push/unregister', {
    method: 'DELETE',
    token,
    body: {
      push_token: stored.push_token,
    },
  });
  await clearStoredPushRegistration();
  return result;
}

export async function getStoredNotificationStatus() {
  return getStoredPushRegistration();
}
