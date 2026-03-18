import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { DeviceCard } from '@/components/device/DeviceCard';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkText } from '@/components/ui/InkText';
import { getDeviceState, listUserDevices, type DeviceSummary } from '@/features/device/api';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';
import { StyleSheet, View } from 'react-native';
import { theme } from '@/lib/theme';

function DeviceListItem({ device, token }: { device: DeviceSummary; token: string }) {
  const { t } = useI18n();
  const stateQuery = useQuery({
    queryKey: ['device-state', device.mac, token],
    queryFn: () => getDeviceState(device.mac, token),
    staleTime: 60 * 1000,
  });
  const state = stateQuery.data;
  const batteryText = state?.battery_pct != null ? `${state.battery_pct}%` : undefined;
  const isOnline = state?.is_online;

  return (
    <DeviceCard
      title={device.nickname || device.mac}
      subtitle={device.mac}
      status={isOnline != null ? (isOnline ? t('device.online') : t('device.offline')) : (device.status || t('device.bound'))}
      battery={batteryText}
      online={isOnline}
      onPress={() => router.push(`/device/${encodeURIComponent(device.mac)}`)}
    />
  );
}

export default function DeviceScreen() {
  const { t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const query = useQuery({
    queryKey: ['devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });
  const devices = query.data?.devices || [];
  const latestDevice = devices[0];
  const latestStateQuery = useQuery({
    queryKey: ['device-latest-state', latestDevice?.mac, token],
    queryFn: () => getDeviceState(latestDevice?.mac || '', token || ''),
    enabled: Boolean(token && latestDevice?.mac),
    staleTime: 60 * 1000,
  });

  return (
    <AppScreen
      header={
        <>
          <InkText serif style={styles.title}>{t('device.title')}</InkText>
          <InkText dimmed>{t('device.subtitle')}</InkText>
        </>
      }
    >
      {!token ? (
        <>
          <InkCard style={styles.heroCard}>
            <InkChip label={t('device.previewChip')} active />
            <InkText style={styles.heroTitle}>{t('device.previewTitle')}</InkText>
            <InkText dimmed style={styles.heroBody}>{t('device.previewBody')}</InkText>
            <View style={styles.featureRow}>
              <InkChip label={t('device.previewFeatureOne')} />
              <InkChip label={t('device.previewFeatureTwo')} />
              <InkChip label={t('device.previewFeatureThree')} />
            </View>
            <InkButton label={t('device.loginSync')} onPress={() => router.push('/login')} />
          </InkCard>

          <InkCard>
            <InkText style={styles.sectionTitle}>{t('device.openProvision')}</InkText>
            <InkText dimmed style={styles.heroBody}>{t('device.noDevicesDesc')}</InkText>
            <InkButton label={t('device.openProvision')} variant="secondary" onPress={() => router.push('/device/provision')} style={styles.ctaSpacing} />
          </InkCard>
        </>
      ) : null}

      {token && latestDevice ? (
        <InkCard style={styles.summaryCard}>
          <InkText style={styles.sectionTitle}>{t('device.summaryTitle')}</InkText>
          <InkText dimmed style={styles.heroBody}>
            {t('device.summaryBody', {
              name: latestDevice.nickname || latestDevice.mac,
              mode: latestStateQuery.data?.last_persona || '-',
              status: latestStateQuery.data?.is_online ? t('device.online') : t('device.offline'),
            })}
          </InkText>
        </InkCard>
      ) : null}

      {token && devices.length === 0 && !query.isLoading ? (
        <InkCard>
          <InkText style={styles.sectionTitle}>{t('device.noDevices')}</InkText>
          <InkText dimmed style={styles.heroBody}>{t('device.noDevicesDesc')}</InkText>
        </InkCard>
      ) : null}

      {token && devices.map((device) => (
        <DeviceListItem key={device.mac} device={device} token={token || ''} />
      ))}

      <InkButton label={t('device.openProvision')} variant="secondary" onPress={() => router.push('/device/provision')} />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 28,
    fontWeight: '600',
  },
  heroCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
    gap: 14,
  },
  heroTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  heroBody: {
    lineHeight: 22,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  featureRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  ctaSpacing: {
    marginTop: 14,
  },
  summaryCard: {
    backgroundColor: '#FFFCF7',
  },
});
