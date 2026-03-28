import { StyleSheet, View } from 'react-native';
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
import { theme } from '@/lib/theme';

function tf(t: (key: string, vars?: Record<string, string | number>) => string, key: string, fallback: string, vars?: Record<string, string | number>) {
  const resolved = t(key, vars);
  return resolved === key ? fallback : resolved;
}

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
      status={isOnline != null ? (isOnline ? tf(t, 'device.online', 'Online') : tf(t, 'device.offline', 'Offline')) : (device.status || tf(t, 'device.bound', 'Bound'))}
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
          <InkText serif style={styles.title}>{tf(t, 'device.title', 'Device')}</InkText>
          <InkText dimmed>{tf(t, 'device.subtitle', 'Manage devices, states, and provisioning.')}</InkText>
        </>
      }
    >
      {!token ? (
        <>
          <InkCard style={styles.heroCard}>
            <InkChip label={tf(t, 'device.previewChip', 'Preview')} active />
            <InkText style={styles.heroTitle}>{tf(t, 'device.previewTitle', 'Your device cockpit')}</InkText>
            <InkText dimmed style={styles.heroBody}>{tf(t, 'device.previewBody', 'Sign in to sync device status, provisioning, and collaborative access control.')}</InkText>
            <View style={styles.featureRow}>
              <InkChip label={tf(t, 'device.previewFeatureOne', 'Status')} />
              <InkChip label={tf(t, 'device.previewFeatureTwo', 'Provisioning')} />
              <InkChip label={tf(t, 'device.previewFeatureThree', 'Sharing')} />
            </View>
            <InkButton label={tf(t, 'device.loginSync', 'Sign in to sync')} onPress={() => router.push('/login')} />
          </InkCard>

          <InkCard>
            <InkText style={styles.sectionTitle}>{tf(t, 'device.openProvision', 'Pair device')}</InkText>
            <InkText dimmed style={styles.heroBody}>{tf(t, 'device.noDevicesDesc', 'Bind your first device by pair code or provisioning flow.')}</InkText>
            <InkButton
              label={tf(t, 'device.openProvision', 'Pair device')}
              variant="secondary"
              onPress={() => router.push('/device/provision')}
              style={styles.ctaSpacing}
            />
          </InkCard>
        </>
      ) : null}

      {token && latestDevice ? (
        <InkCard style={styles.summaryCard}>
          <InkText style={styles.sectionTitle}>{tf(t, 'device.summaryTitle', 'Latest device snapshot')}</InkText>
          <InkText dimmed style={styles.heroBody}>
            {tf(
              t,
              'device.summaryBody',
              `${latestDevice.nickname || latestDevice.mac} · ${latestStateQuery.data?.last_persona || '-'} · ${latestStateQuery.data?.is_online ? 'Online' : 'Offline'}`,
              {
                name: latestDevice.nickname || latestDevice.mac,
                mode: latestStateQuery.data?.last_persona || '-',
                status: latestStateQuery.data?.is_online ? tf(t, 'device.online', 'Online') : tf(t, 'device.offline', 'Offline'),
              },
            )}
          </InkText>
        </InkCard>
      ) : null}

      {token && devices.length === 0 && !query.isLoading ? (
        <InkCard>
          <InkText style={styles.sectionTitle}>{tf(t, 'device.noDevices', 'No devices')}</InkText>
          <InkText dimmed style={styles.heroBody}>{tf(t, 'device.noDevicesDesc', 'Bind your first InkSight device to get started.')}</InkText>
        </InkCard>
      ) : null}

      {token && devices.map((device) => (
        <DeviceListItem key={device.mac} device={device} token={token || ''} />
      ))}

      <InkButton label={tf(t, 'device.openProvision', 'Pair device')} variant="secondary" onPress={() => router.push('/device/provision')} />
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
    backgroundColor: theme.colors.surface,
  },
});
