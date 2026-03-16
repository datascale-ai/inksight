import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { Alert, Linking } from 'react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { getLatestFirmwareRelease, validateFirmwareUrl } from '@/features/device/api';
import { useI18n } from '@/lib/i18n';

export default function DeviceFirmwareScreen() {
  const { t } = useI18n();
  const { mac } = useLocalSearchParams<{ mac: string }>();
  const query = useQuery({
    queryKey: ['firmware-latest'],
    queryFn: getLatestFirmwareRelease,
  });
  const latest = query.data?.latest;

  async function handleValidate() {
    if (!latest?.download_url) {
      return;
    }
    try {
      await validateFirmwareUrl(latest.download_url);
      Alert.alert(t('firmware.validateTitle'), t('firmware.validateOk'));
    } catch (error) {
      Alert.alert(t('firmware.validateTitle'), error instanceof Error ? error.message : t('firmware.validateTitle'));
    }
  }

  return (
    <AppScreen>
      <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>{t('firmware.title')}</InkText>
      <InkText dimmed>{mac ? t('firmware.deviceSubtitle', { mac }) : t('firmware.subtitle')}</InkText>

      <InkCard>
        <InkText style={{ fontSize: 16, fontWeight: '600' }}>{latest?.version ? t('firmware.latest', { version: latest.version }) : t('firmware.loading')}</InkText>
        <InkText dimmed style={{ marginTop: 8, lineHeight: 24 }}>
          {latest
            ? t('firmware.detail', {
                publishedAt: latest.published_at || '-',
                chip: latest.chip_family || '-',
                asset: latest.asset_name || '-',
              })
            : t('firmware.unavailable')}
        </InkText>
        {latest?.download_url ? <InkText dimmed style={{ marginTop: 8 }}>{latest.download_url}</InkText> : null}
      </InkCard>

      <InkButton label={query.isFetching ? t('common.loading') : t('firmware.refresh')} block onPress={() => query.refetch()} />
      <InkButton label={t('firmware.validate')} block variant="secondary" onPress={handleValidate} disabled={!latest?.download_url} />
      <InkButton label={t('firmware.open')} block variant="secondary" onPress={() => latest?.download_url && Linking.openURL(latest.download_url)} disabled={!latest?.download_url} />
    </AppScreen>
  );
}
