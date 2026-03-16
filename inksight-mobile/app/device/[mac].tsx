import { useEffect, useState } from 'react';
import { Alert, StyleSheet, View } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { getDeviceConfig, getDeviceShareImageUrl, getDeviceState, refreshDevice, switchDeviceMode } from '@/features/device/api';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';
import { shareRemoteImage } from '@/features/sharing/share';
import { getWidgetData } from '@/features/widgets/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function DeviceDetailScreen() {
  const { t } = useI18n();
  const { mac } = useLocalSearchParams<{ mac: string }>();
  const token = useAuthStore((state) => state.token);
  const showToast = useToast();
  const [selectedWidgetMode, setSelectedWidgetMode] = useState('STOIC');
  const [lastWidgetRefreshAt, setLastWidgetRefreshAt] = useState(0);

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

  const state = stateQuery.data;
  const config = configQuery.data;
  const widget = widgetQuery.data;

  const refreshMutation = useMutation({
    mutationFn: async () => refreshDevice(mac || '', token || ''),
    onSuccess: async (result) => {
      await successFeedback();
      showToast(result.message, 'success');
    },
    onError: (error) => Alert.alert(t('common.refresh'), error instanceof Error ? error.message : t('common.refresh')),
  });
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
    await widgetQuery.refetch();
  }

  async function handleShareImage() {
    if (!mac) {
      return;
    }
    try {
      const shareUrl = getDeviceShareImageUrl(mac);
      if (!token) {
        throw new Error(t('device.shareMissing'));
      }
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
                modes: config.modes.join(', '),
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
              label={mode}
              variant={selectedWidgetMode === mode ? 'primary' : 'secondary'}
              onPress={() => setSelectedWidgetMode(mode)}
            />
          ))}
        </View>
        <InkText dimmed style={styles.cardBody}>
          {widget
            ? `${widget.display_name} · ${String(widget.content?.text || widget.content?.summary || widget.content?.quote || '-')}`
            : t('device.widgetFallback')}
        </InkText>
        <View style={styles.widgetActions}>
          <InkButton label={t('device.previewRefresh')} variant="secondary" onPress={handleRefreshWidget} />
          <InkButton label={t('device.shareImage')} variant="secondary" onPress={handleShareImage} />
        </View>
      </InkCard>

      <View style={styles.actionStack}>
        <InkButton label={refreshMutation.isPending ? t('common.loading') : t('device.refreshNow')} onPress={() => refreshMutation.mutate()} />
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
});
