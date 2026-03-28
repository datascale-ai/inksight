import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'inksight.auth.token';
const ONBOARDING_SEEN_KEY = 'inksight.onboarding.seen';
const LOCALE_KEY = 'inksight.locale';
const NOTIFICATION_TIME_KEY = 'inksight.notifications.time';
const PUSH_REGISTRATION_KEY = 'inksight.push.registration';
const LOCAL_NOTIFICATION_ID_KEY = 'inksight.notifications.local.id';

export type StoredPushRegistration = {
  push_token: string;
  platform: string;
  timezone: string;
  push_time: string;
};

async function secureGet(key: string) {
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return AsyncStorage.getItem(key);
  }
}

async function secureSet(key: string, value: string) {
  try {
    await SecureStore.setItemAsync(key, value);
    return;
  } catch {
    await AsyncStorage.setItem(key, value);
  }
}

async function secureDelete(key: string) {
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    // Ignore and fall back below.
  }
  await AsyncStorage.removeItem(key);
}

export async function getToken() {
  return secureGet(TOKEN_KEY);
}

export async function setToken(token: string) {
  await secureSet(TOKEN_KEY, token);
}

export async function clearToken() {
  await secureDelete(TOKEN_KEY);
}

export async function getOnboardingSeen() {
  const raw = await AsyncStorage.getItem(ONBOARDING_SEEN_KEY);
  return raw === '1';
}

export async function setOnboardingSeen(seen: boolean) {
  await AsyncStorage.setItem(ONBOARDING_SEEN_KEY, seen ? '1' : '0');
}

export async function getStoredLocale() {
  return AsyncStorage.getItem(LOCALE_KEY);
}

export async function setStoredLocale(locale: 'zh' | 'en') {
  await AsyncStorage.setItem(LOCALE_KEY, locale);
}

export async function getNotificationTime() {
  return (await AsyncStorage.getItem(NOTIFICATION_TIME_KEY)) || '08:00';
}

export async function setNotificationTime(value: string) {
  await AsyncStorage.setItem(NOTIFICATION_TIME_KEY, value);
}

export async function getStoredPushRegistration(): Promise<StoredPushRegistration | null> {
  const raw = await AsyncStorage.getItem(PUSH_REGISTRATION_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as StoredPushRegistration;
  } catch {
    await AsyncStorage.removeItem(PUSH_REGISTRATION_KEY);
    return null;
  }
}

export async function setStoredPushRegistration(value: StoredPushRegistration) {
  await AsyncStorage.setItem(PUSH_REGISTRATION_KEY, JSON.stringify(value));
}

export async function clearStoredPushRegistration() {
  await AsyncStorage.removeItem(PUSH_REGISTRATION_KEY);
}

export async function getLocalNotificationId() {
  return AsyncStorage.getItem(LOCAL_NOTIFICATION_ID_KEY);
}

export async function setLocalNotificationId(id: string) {
  await AsyncStorage.setItem(LOCAL_NOTIFICATION_ID_KEY, id);
}

export async function clearLocalNotificationId() {
  await AsyncStorage.removeItem(LOCAL_NOTIFICATION_ID_KEY);
}
