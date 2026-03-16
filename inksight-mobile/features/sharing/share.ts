import { Linking, Platform, Share } from 'react-native';
import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import type { TodayItem } from '@/features/content/api';
import { buildAuthHeaders } from '@/lib/api-client';

export async function shareTodayItem(item: TodayItem, options?: { sourceLabel?: string }) {
  const attribution = typeof item.content?.author === 'string' ? `\n\n${item.content.author}` : '';
  const message = `${item.display_name}\n\n${item.summary}${attribution}\n\n${options?.sourceLabel || 'From InkSight'}`;
  return Share.share({
    title: item.display_name,
    message,
  });
}

export async function shareRemoteImage(input: {
  url: string;
  token?: string | null;
  filename?: string;
  fallbackMessage?: string;
}) {
  if (Platform.OS === 'web') {
    await Linking.openURL(input.url);
    return { ok: true, mode: 'web-open' as const };
  }

  const targetUri = `${FileSystem.cacheDirectory || FileSystem.documentDirectory}${input.filename || `inksight-${Date.now()}.png`}`;
  await FileSystem.downloadAsync(input.url, targetUri, {
    headers: buildAuthHeaders(input.token, ''),
  });

  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(targetUri);
    return { ok: true, mode: 'share' as const };
  }

  await Share.share({
    message: input.fallbackMessage || input.url,
    url: targetUri,
  });
  return { ok: true, mode: 'fallback' as const };
}
