import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { Alert } from 'react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { getLatestFirmwareRelease, getOTAStatus, triggerOTA, cancelOTA } from '@/features/device/api';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

type OTAStage = 'idle' | 'checking' | 'flashing' | 'success' | 'error';

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 120000;

export default function DeviceFirmwareScreen() {
  const { t } = useI18n();
  const { mac } = useLocalSearchParams<{ mac: string }>();
  const { token } = useAuthStore();

  // ── Firmware release query ────────────────────────────────
  const releaseQuery = useQuery({
    queryKey: ['firmware-latest'],
    queryFn: getLatestFirmwareRelease,
    refetchInterval: false,
  });
  const latest = releaseQuery.data?.latest;

  // ── OTA state ─────────────────────────────────────────────
  const [otaStage, setOtaStage] = useState<OTAStage>('idle');
  const [otaProgress, setOtaProgress] = useState(0);
  const [otaResult, setOtaResult] = useState('');
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollStartRef = useRef<number>(0);

  // ── Stage label ────────────────────────────────────────────
  const stageLabel = (() => {
    if (otaResult === 'downloading' || (otaStage === 'flashing' && otaProgress < 50)) {
      return t('firmware.ota.downloading');
    }
    if (otaResult === 'flashing' || (otaStage === 'flashing' && otaProgress >= 50)) {
      return t('firmware.ota.flashing');
    }
    if (otaStage === 'success') {
      return t('firmware.ota.success');
    }
    if (otaStage === 'error') {
      const reason = otaResult.replace('failed:', '');
      return t('firmware.ota.error', { reason });
    }
    return '';
  })();

  // ── Poll OTA status ────────────────────────────────────────
  const pollOTAStatus = useCallback(async () => {
    if (!mac || !token) return;
    const elapsed = Date.now() - pollStartRef.current;

    try {
      const status = await getOTAStatus(mac, token);

      if (status.ota_result === 'success') {
        setOtaProgress(100);
        setOtaStage('success');
        clearPollTimer();
        return;
      }

      if (status.ota_result.startsWith('failed:')) {
        setOtaResult(status.ota_result);
        setOtaStage('error');
        clearPollTimer();
        return;
      }

      setOtaProgress(status.ota_progress ?? 0);
      setOtaResult(status.ota_result ?? '');

      if (status.ota_result === 'downloading' || status.ota_result === 'flashing') {
        setOtaStage('flashing');
      }

      // Timeout
      if (elapsed >= POLL_TIMEOUT_MS) {
        setOtaStage('error');
        setOtaResult('failed:timeout');
        clearPollTimer();
        return;
      }
    } catch {
      // Network error during poll, keep polling
    }

    pollTimerRef.current = setTimeout(pollOTAStatus, POLL_INTERVAL_MS);
  }, [mac, token]);  // eslint-disable-line react-hooks/exhaustive-deps

  const clearPollTimer = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => clearPollTimer();
  }, []);

  // ── Start OTA ──────────────────────────────────────────────
  const handleFlash = async () => {
    if (!latest?.download_url || !latest?.version || !mac || !token) return;

    // Fresh device status check before attempting flash
    let status;
    try {
      status = await getOTAStatus(mac!, token!);
    } catch {
      Alert.alert(t('firmware.ota.errorTitle'), t('firmware.ota.failed'));
      return;
    }

    if (!status.is_online) {
      Alert.alert(
        t('firmware.ota.notOnlineTitle'),
        t('firmware.ota.notOnlineBody'),
      );
      return;
    }

    if (status.runtime_mode !== 'active') {
      Alert.alert(
        t('firmware.ota.notActiveTitle'),
        t('firmware.ota.notActiveBody'),
      );
      return;
    }

    Alert.alert(
      t('firmware.ota.confirmTitle'),
      t('firmware.ota.confirmBody', { version: latest.version, mac: mac ?? '' }),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('firmware.ota.confirmFlash'),
          onPress: async () => {
            setOtaStage('checking');
            setOtaProgress(0);
            setOtaResult('');

            try {
              const result = await triggerOTA(mac!, latest.download_url!, latest.version!, token!);

              if (!result.ok) {
                Alert.alert(t('firmware.ota.errorTitle'), result.message || t('firmware.ota.failed'));
                setOtaStage('idle');
                return;
              }

              setOtaStage('flashing');
              pollStartRef.current = Date.now();
              pollTimerRef.current = setTimeout(pollOTAStatus, POLL_INTERVAL_MS);
            } catch (err) {
              const msg = err instanceof Error ? err.message : t('firmware.ota.failed');
              Alert.alert(t('firmware.ota.errorTitle'), msg);
              setOtaStage('idle');
            }
          },
        },
      ],
    );
  };

  // ── Cancel OTA ────────────────────────────────────────────
  const handleCancel = async () => {
    if (!mac || !token) return;
    Alert.alert(t('firmware.ota.cancelTitle'), t('firmware.ota.cancelBody'), [
      { text: t('common.cancel'), style: 'cancel' },
      {
        text: t('firmware.ota.cancelConfirm'),
        style: 'destructive',
        onPress: async () => {
          clearPollTimer();
          try {
            await cancelOTA(mac!, token!);
          } catch {
            // Ignore cancel errors
          }
          setOtaStage('idle');
          setOtaProgress(0);
          setOtaResult('');
        },
      },
    ]);
  };

  // ── Render ─────────────────────────────────────────────────

  return (
    <AppScreen>
      <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>
        {t('firmware.title')}
      </InkText>
      <InkText dimmed>
        {mac ? t('firmware.deviceSubtitle', { mac }) : t('firmware.subtitle')}
      </InkText>

      {/* Firmware info card */}
      <InkCard>
        <InkText style={{ fontSize: 16, fontWeight: '600' }}>
          {latest?.version
            ? t('firmware.latest', { version: latest.version })
            : t('firmware.loading')}
        </InkText>
        <InkText dimmed style={{ marginTop: 8, lineHeight: 24 }}>
          {latest
            ? t('firmware.detail', {
                publishedAt: latest.published_at || '-',
                chip: latest.chip_family || '-',
                asset: latest.asset_name || '-',
              })
            : t('firmware.unavailable')}
        </InkText>

        {/* OTA status card (shown during flashing) */}
        {(otaStage === 'flashing' || otaStage === 'success' || otaStage === 'error') && (
          <View style={styles.otaStatusCard}>
            <View style={styles.otaRow}>
              <InkText style={{ fontSize: 14, fontWeight: '600' }}>
                {otaStage === 'success'
                  ? t('firmware.ota.success')
                  : otaStage === 'error'
                  ? t('firmware.ota.failed')
                  : stageLabel}
              </InkText>
              <InkText dimmed style={{ fontSize: 14 }}>
                {otaProgress}%
              </InkText>
            </View>

            {/* Progress bar */}
            <View style={styles.progressBarOuter}>
              <View
                style={[
                  styles.progressBarInner,
                  {
                    width: `${Math.min(100, otaProgress)}%`,
                    backgroundColor:
                      otaStage === 'success'
                        ? theme.colors.success
                        : otaStage === 'error'
                        ? theme.colors.danger
                        : theme.colors.accent,
                  },
                ]}
              />
            </View>

            {otaStage === 'flashing' && (
              <ActivityIndicator size="small" style={{ marginTop: 8 }} />
            )}
          </View>
        )}
      </InkCard>

      {/* Buttons */}
      {otaStage === 'idle' && (
        <>
          <InkButton
            label={releaseQuery.isFetching ? t('common.loading') : t('firmware.refresh')}
            block
            onPress={() => releaseQuery.refetch()}
          />

          <InkButton
            label={t('firmware.ota.flash')}
            block
            variant="secondary"
            disabled={otaStage !== 'idle' || !latest?.download_url || !latest?.version || !token}
            onPress={handleFlash}
          />
        </>
      )}

      {otaStage === 'checking' && (
        <View style={styles.centerRow}>
          <ActivityIndicator size="small" />
          <InkText dimmed style={{ marginLeft: 8 }}>{t('firmware.ota.connecting')}</InkText>
        </View>
      )}

      {(otaStage === 'flashing' || otaStage === 'success' || otaStage === 'error') && (
        <View style={styles.buttonGroup}>
          {otaStage === 'error' && (
            <InkButton
              label={t('firmware.ota.retry')}
              block
              variant="secondary"
              onPress={() => setOtaStage('idle')}
            />
          )}
          {otaStage === 'success' && (
            <InkButton
              label={t('common.done')}
              block
              onPress={() => setOtaStage('idle')}
            />
          )}
          {(otaStage === 'flashing') && (
            <InkButton
              label={t('firmware.ota.cancel')}
              block
              variant="secondary"
              onPress={handleCancel}
            />
          )}
        </View>
      )}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  otaStatusCard: {
    marginTop: 16,
    paddingTop: 16,
        borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  otaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressBarOuter: {
    height: 8,
    backgroundColor: theme.colors.surface,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarInner: {
    height: '100%',
    borderRadius: 4,
  },
  centerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
  },
  buttonGroup: {
    gap: 8,
  },
});
