import { isRunningInExpoGo } from 'expo';
import { Platform } from 'react-native';
import type { TodayItem } from '@/features/content/api';
import { clearLocalNotificationId, getLocalNotificationId, setLocalNotificationId } from '@/lib/storage';

let isHandlerConfigured = false;

export function isNotificationRuntimeAvailable() {
  if (Platform.OS === 'web') {
    return false;
  }
  if (Platform.OS === 'android' && isRunningInExpoGo()) {
    return false;
  }
  return true;
}

async function loadNotifications() {
  if (!isNotificationRuntimeAvailable()) {
    return null;
  }
  return import('expo-notifications');
}

export function ensureLocalNotificationHandler() {
  if (!isNotificationRuntimeAvailable() || isHandlerConfigured) {
    return;
  }
  loadNotifications()
    .then((Notifications) => {
      if (!Notifications || isHandlerConfigured) {
        return;
      }
      Notifications.setNotificationHandler({
        handleNotification: async () => ({
          shouldShowBanner: true,
          shouldShowList: true,
          shouldPlaySound: false,
          shouldSetBadge: false,
        }),
      });
      isHandlerConfigured = true;
    })
    .catch(() => undefined);
}

function parsePushTime(value: string) {
  const [hourText, minuteText] = value.split(':');
  return {
    hour: Number(hourText) || 8,
    minute: Number(minuteText) || 0,
  };
}

export async function syncLocalDailyNotification(input: {
  enabled: boolean;
  pushTime: string;
  item?: TodayItem | null;
  title?: string;
  body?: string;
}) {
  if (!isNotificationRuntimeAvailable()) {
    return { ok: false, reason: 'runtime_unsupported' as const };
  }

  ensureLocalNotificationHandler();
  const Notifications = await loadNotifications();
  if (!Notifications) {
    return { ok: false, reason: 'native_module_unavailable' as const };
  }
  const existingId = await getLocalNotificationId();
  if (existingId) {
    await Notifications.cancelScheduledNotificationAsync(existingId).catch(() => undefined);
    await clearLocalNotificationId();
  }

  if (!input.enabled) {
    return { ok: true, scheduled: false as const };
  }

  const permission = await Notifications.requestPermissionsAsync();
  if (!permission.granted) {
    return { ok: false, reason: 'permission_denied' as const };
  }

  const { hour, minute } = parsePushTime(input.pushTime);
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title: input.item?.display_name || input.title || 'InkSight Daily Brief',
      body: input.item?.summary || input.body || 'Open InkSight to see what is worth reading today.',
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DAILY,
      hour,
      minute,
    },
  });
  await setLocalNotificationId(id);
  return { ok: true, scheduled: true as const, id };
}
