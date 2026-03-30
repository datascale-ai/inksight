import { useEffect, useState } from 'react';
import { Alert, Image, StyleSheet, View } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import * as FileSystem from 'expo-file-system/legacy';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { getDeviceConfig, getDeviceShareImageUrl, getDeviceState, pushPreviewImageToDevice, switchDeviceMode } from '@/features/device/api';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';
import { shareRemoteImage } from '@/features/sharing/share';
import { listModes, type ModeCatalogItem } from '@/features/modes/api';
import { getWidgetData } from '@/features/widgets/api';
import { buildApiUrl } from '@/lib/api-client';
import { useI18n } from '@/lib/i18n';
import { modeDisplayName } from '@/lib/mode-display';
import { theme } from '@/lib/theme';

function uint8ArrayToBase64(bytes: Uint8Array): string {
  const table = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let out = '';
  let i = 0;
  const len = bytes.length;
  while (i < len) {
    const b1 = bytes[i++]!;
    const b2 = i < len ? bytes[i++] : undefined;
    const b3 = i < len ? bytes[i++] : undefined;
    const enc1 = b1 >> 2;
    const enc2 = ((b1 & 3) << 4) | (b2 === undefined ? 0 : b2 >> 4);
    out += table[enc1]! + table[enc2]!;
    if (b2 === undefined) {
      out += '==';
    } else if (b3 === undefined) {
      out += table[((b2 & 15) << 2)]! + '=';
    } else {
      out += table[((b2 & 15) << 2) | (b3 >> 6)]! + table[b3 & 63]!;
    }
  }
  return out;
}

function buildPreviewCacheUri(mac: string, mode: string) {
  const base = FileSystem.cacheDirectory || FileSystem.documentDirectory || '';
  const safeMac = mac.replace(/[^a-zA-Z0-9]/g, '-');
  const safeMode = mode.replace(/[^a-zA-Z0-9]/g, '-');
  return `${base}device-preview-${safeMac}-${safeMode}.png`;
}

function firstWidgetSnippet(content: Record<string, unknown> | undefined) {
  if (!content) {
    return '-';
  }
  const raw =
    content.text ??
    content.summary ??
    content.quote ??
    content.word ??
    content.title ??
    content.question;
  if (typeof raw === 'string' && raw.trim()) {
    return raw.trim();
  }
  return '-';
}

function resolveApplyPreviewMessage(
  t: (key: string, vars?: Record<string, string | number>) => string,
  state: { is_online?: boolean; runtime_mode?: string } | undefined,
) {
  if (state?.is_online && state?.runtime_mode === 'active') {
    return t('device.applyPreviewSuccessActive');
  }
  return t('device.applyPreviewSuccessQueued');
}

export default function DeviceDetailScreen() {
  const { locale, t } = useI18n();
  const { mac } = useLocalSearchParams<{ mac: string }>();
  const token = useAuthStore((state) => state.token);
  const hydrated = useAuthStore((state) => state.hydrated);
  const showToast = useToast();
  const [selectedWidgetMode, setSelectedWidgetMode] = useState('STOIC');
  const [lastWidgetRefreshAt, setLastWidgetRefreshAt] = useState(0);
  const [previewImageUri, setPreviewImageUri] = useState<string | null>(null);
  const [previewImageBytes, setPreviewImageBytes] = useState<ArrayBuffer | null>(null);

  const stateQuery = useQuery({
    queryKey: ['device-state', mac, token],
    queryFn: () => getDeviceState(mac || '', token || ''),
    enabled: Boolean(mac && token),
    staleTime: 10 * 1000,
  });
  const configQuery = useQuery({
    queryKey: ['device-config', mac, token],
    queryFn: () => getDeviceConfig(mac || '', token || ''),
    enabled: Boolean(mac && token),
  });
  const modesQuery = useQuery({
    queryKey: ['mode-catalog-detail'],
    queryFn: listModes,
  });
  const widgetQuery = useQuery({
    queryKey: ['device-widget', mac, token, selectedWidgetMode],
    queryFn: () => getWidgetData(mac || '', token || '', selectedWidgetMode),
    enabled: Boolean(mac && token && selectedWidgetMode),
  });

  useEffect(() => {
    if (configQuery.data?.modes?.[0]) {
      setSelectedWidgetMode(configQuery.data.modes[0]);
    }
  }, [configQuery.data]);

  useEffect(() => {
    setPreviewImageUri(null);
    setPreviewImageBytes(null);
  }, [selectedWidgetMode]);

  const state = stateQuery.data;
  const config = configQuery.data;
  const widget = widgetQuery.data;

  const applyPreviewMutation = useMutation({
    mutationFn: async () => {
      if (!previewImageBytes) {
        throw new Error(t('device.previewApplyMissing'));
      }
      return pushPreviewImageToDevice(mac || '', token || '', previewImageBytes.slice(0), selectedWidgetMode);
    },
    onSuccess: async () => {
      await successFeedback();
      showToast(resolveApplyPreviewMessage(t, state), 'success');
      await stateQuery.refetch();
    },
    onError: (error) => Alert.alert(t('device.applyPreview'), error instanceof Error ? error.message : t('device.applyPreview')),
  });

  function confirmApplyPreview() {
    if (!previewImageBytes) {
      Alert.alert(t('device.applyPreview'), t('device.previewApplyMissing'));
      return;
    }
    Alert.alert(t('device.applyPreviewTitle'), t('device.applyPreviewHint'), [
      { text: t('common.cancel'), style: 'cancel' },
      { text: t('common.confirm'), onPress: () => applyPreviewMutation.mutate() },
    ]);
  }
  const switchMutation = useMutation({
    mutationFn: async () => switchDeviceMode(mac || '', token || '', config?.modes?.[0] || 'DAILY'),
    onSuccess: (result) => showToast(result.message, 'success'),
    onError: (error) => Alert.alert(t('device.switchMode'), error instanceof Error ? error.message : t('device.switchMode')),
  });

  async function handleRefreshWidget() {
    const now = Date.now();
    const secondsLeft = Math.max(0, 30 - Math.floor((now - lastWidgetRefreshAt) / 1000));
    if (lastWidgetRefreshAt && secondsLeft > 0) {
      Alert.alert(t('device.previewCoolingTitle'), t('device.previewCooling', { seconds: secondsLeft }));
      return;
    }
    await lightImpact();
    setLastWidgetRefreshAt(now);
    const result = await widgetQuery.refetch();
    if (result.error) {
      showToast(result.error instanceof Error ? result.error.message : t('device.widgetError'), 'error');
      return;
    }
    // Fetch PNG preview image after data refresh
    setPreviewImageUri(null);
    setPreviewImageBytes(null);
    const data = result.data;
    if (data?.preview_url) {
      try {
        const rawUrl = buildApiUrl(data.preview_url);
        const sep = rawUrl.includes('?') ? '&' : '?';
        const url = `${rawUrl}${sep}no_cache=1`;
        const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (resp.ok) {
          const bytes = await resp.arrayBuffer();
          setPreviewImageBytes(bytes);
          const b64 = uint8ArrayToBase64(new Uint8Array(bytes));
          const targetUri = buildPreviewCacheUri(mac || 'device', selectedWidgetMode);
          await FileSystem.writeAsStringAsync(targetUri, b64, {
            encoding: FileSystem.EncodingType.Base64,
          });
          setPreviewImageUri(`${targetUri}?t=${Date.now()}`);
        }
      } catch {
        // Non-critical: keep data without image
      }
    }
    showToast(t('device.previewUpdated'), 'success');
  }

  async function handleShareImage() {
    if (!mac) {
      return;
    }
    try {
      if (!token) {
        throw new Error(t('device.shareMissing'));
      }
      const previewPath = widget?.preview_url?.trim();
      const shareUrl =
        previewPath && previewPath.length > 0 ? buildApiUrl(previewPath) : getDeviceShareImageUrl(mac);
      await shareRemoteImage({
        url: shareUrl,
        token,
        filename: `inksight-${mac.replace(/:/g, '-')}.png`,
        fallbackMessage: shareUrl,
      });
    } catch (error) {
      Alert.alert(t('device.shareFailed'), error instanceof Error ? error.message : t('device.shareFailed'));
    }
  }

  function widgetStatusText() {
    if (!hydrated) {
      return t('common.loading');
    }
    if (!token) {
      return t('device.widgetLoginPrompt');
    }
    if (widgetQuery.isError) {
      const message = widgetQuery.error instanceof Error ? widgetQuery.error.message : '';
      return message ? t('device.widgetError', { message }) : t('device.widgetErrorGeneric');
    }
    if (widgetQuery.isPending && !widget) {
      return t('device.widgetLoading');
    }
    if (widget) {
      const label = modeDisplayName(widget.mode_id, locale, widget.display_name);
      return `${label} · ${firstWidgetSnippet(widget.content)}`;
    }
    return t('device.widgetEmpty');
  }

  const HARDCODED_CONFIGURABLE = ['CALENDAR', 'TIMETABLE'];

  function isModeConfigurable(modeId: string): boolean {
    if (HARDCODED_CONFIGURABLE.includes(modeId.toUpperCase())) return true;
    const catalog = modesQuery.data?.modes;
    if (!catalog) return false;
    const info = catalog.find((m: ModeCatalogItem) => m.mode_id === modeId);
    return Boolean(info?.settings_schema && info.settings_schema.length > 0);
  }

  const configModesLabel =
    config?.modes?.map((id) => modeDisplayName(id, locale, id)).join(', ') ?? '';

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{state?.mac || mac || t('nav.deviceDetail')}</InkText>
      <InkText dimmed>{t('device.detailSubtitle')}</InkText>

      <InkCard>
        <InkText style={styles.cardTitle}>{t('device.stateTitle')}</InkText>
        <InkText dimmed style={styles.cardBody}>
          {state
            ? t('device.stateBody', {
                mode: state.last_persona || '-',
                online: state.is_online ? t('device.online') : t('device.offline'),
                minutes: state.refresh_minutes || '--',
              })
            : t('device.stateFallback')}
        </InkText>
      </InkCard>

      <InkCard>
        <InkText style={styles.cardTitle}>{t('device.configTitle')}</InkText>
        <InkText dimmed style={styles.cardBody}>
          {config
            ? t('device.configBody', {
                city: config.city || 'Hangzhou',
                modes: configModesLabel || config.modes.join(', '),
                strategy: config.refreshStrategy || 'random',
              })
            : t('device.configLoading')}
        </InkText>
      </InkCard>

      <InkCard>
        <InkText style={styles.cardTitle}>{t('device.widgetTitle')}</InkText>
        <View style={styles.modeWrap}>
          {(config?.modes || []).map((mode) => (
            <InkButton
              key={mode}
              label={modeDisplayName(mode, locale, mode)}
              variant={selectedWidgetMode === mode ? 'primary' : 'secondary'}
              onPress={() => setSelectedWidgetMode(mode)}
            />
          ))}
        </View>
        <InkText dimmed style={styles.cardBody}>
          {widgetStatusText()}
        </InkText>
        {previewImageUri ? (
          <View style={styles.previewWrap}>
            <Image source={{ uri: previewImageUri }} style={styles.previewImage} resizeMode="contain" />
          </View>
        ) : null}
        <View style={styles.widgetActions}>
          <InkButton label={t('device.previewRefresh')} variant="secondary" onPress={handleRefreshWidget} />
          {isModeConfigurable(selectedWidgetMode) && (
            <InkButton
              label={t('device.modeSettingsBtn')}
              variant="secondary"
              onPress={() => router.push(`/device/${encodeURIComponent(mac || '')}/mode-settings?mode=${encodeURIComponent(selectedWidgetMode)}`)}
            />
          )}
          <InkButton label={t('device.shareImage')} variant="secondary" onPress={handleShareImage} />
        </View>
      </InkCard>

      <View style={styles.actionStack}>
        <InkButton
          label={applyPreviewMutation.isPending ? t('common.loading') : t('device.applyPreview')}
          variant="secondary"
          onPress={confirmApplyPreview}
        />
        <InkButton label={switchMutation.isPending ? t('common.loading') : t('device.switchMode')} variant="secondary" onPress={() => switchMutation.mutate()} />
        <InkButton label={t('device.editConfig')} variant="secondary" onPress={() => router.push(`/device/${encodeURIComponent(mac || '')}/config`)} />
        <InkButton label={t('device.manageMembers')} variant="secondary" onPress={() => router.push(`/device/${encodeURIComponent(mac || '')}/members`)} />
        <InkButton label={t('device.viewFirmware')} variant="secondary" onPress={() => router.push(`/device/${encodeURIComponent(mac || '')}/firmware`)} />
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  cardTitle: {
    fontWeight: '600',
    fontSize: 16,
  },
  cardBody: {
    marginTop: 8,
    lineHeight: 22,
  },
  actionStack: {
    gap: 12,
  },
  modeWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 12,
  },
  widgetActions: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 16,
  },
  previewWrap: {
    marginTop: 12,
    borderRadius: theme.radius.md,
    overflow: 'hidden',
    backgroundColor: theme.colors.surface,
  },
  previewImage: {
    width: '100%',
    aspectRatio: 400 / 300,
  },
});
