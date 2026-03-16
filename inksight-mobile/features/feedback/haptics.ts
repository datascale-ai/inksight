import { Platform } from 'react-native';
import * as Haptics from 'expo-haptics';

async function run(effect: () => Promise<void>) {
  if (Platform.OS === 'web') {
    return;
  }
  try {
    await effect();
  } catch {
    // Ignore devices that don't support haptics.
  }
}

export function lightImpact() {
  return run(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
}

export function mediumImpact() {
  return run(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
}

export function successFeedback() {
  return run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
}
