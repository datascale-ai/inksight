import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { DeviceCard } from '@/components/device/DeviceCard';
import { listUserDevices, getDeviceState, type DeviceSummary } from '@/features/device/api';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';

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

  return (
    <AppScreen
      header={
        <>
          <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>{t('device.title')}</InkText>
          <InkText dimmed>{t('device.subtitle')}</InkText>
        </>
      }
    >

      {!token ? (
        <InkCard>
          <InkText style={{ fontSize: 15, fontWeight: '600', marginBottom: 8 }}>{t('device.loginRequired')}</InkText>
          <InkText dimmed>{t('device.loginRequiredDesc')}</InkText>
          <InkButton label={t('device.loginSync')} onPress={() => router.push('/login')} style={{ marginTop: 16 }} />
        </InkCard>
      ) : devices.length === 0 && !query.isLoading ? (
        <InkCard>
          <InkText style={{ fontSize: 15, fontWeight: '600', marginBottom: 8 }}>{t('device.noDevices')}</InkText>
          <InkText dimmed>{t('device.noDevicesDesc')}</InkText>
        </InkCard>
      ) : null}

      {devices.map((device) => (
        <DeviceListItem key={device.mac} device={device} token={token || ''} />
      ))}

      <InkButton label={t('device.openProvision')} variant="secondary" onPress={() => router.push('/device/provision')} />
    </AppScreen>
  );
}
