import { useState } from 'react';
import { Alert, StyleSheet, TextInput } from 'react-native';
import { useMutation } from '@tanstack/react-query';
import { router } from 'expo-router';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { useAuthStore } from '@/features/auth/store';
import { claimDevice } from '@/features/device/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function ProvisionScreen() {
  const { t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const [pairCode, setPairCode] = useState('');
  const [mac, setMac] = useState('');
  const mutation = useMutation({
    mutationFn: async () => claimDevice(token || '', { pair_code: pairCode.trim() }),
    onSuccess: (result) => {
      Alert.alert(t('device.provisionSuccessTitle'), t('device.provisionSuccess', { mac: result.mac || '-' }));
      router.replace('/(tabs)/device');
    },
    onError: (error) => Alert.alert(t('device.provisionError'), error instanceof Error ? error.message : t('device.provisionError')),
  });

  return (
    <AppScreen>
      <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>{t('device.provisionTitle')}</InkText>
      <InkText dimmed>{t('device.provisionSubtitle')}</InkText>

      <InkCard>
        <InkText style={{ fontWeight: '600', fontSize: 16 }}>{t('device.provisionGuide')}</InkText>
        <InkText dimmed style={{ marginTop: 8 }}>{t('device.provisionStep1')}</InkText>
        <InkText dimmed>{t('device.provisionStep2')}</InkText>
      </InkCard>

      <InkCard>
        <InkText style={styles.label}>{t('device.provisionPairCode')}</InkText>
        <TextInput value={pairCode} onChangeText={setPairCode} placeholder={t('device.provisionPairCode')} style={styles.input} autoCapitalize="characters" />
        <InkText style={styles.label}>{t('device.provisionMacOptional')}</InkText>
        <TextInput value={mac} onChangeText={setMac} placeholder={t('device.provisionMacOptional')} style={styles.input} autoCapitalize="characters" />
        <InkButton
          label={mutation.isPending ? t('common.loading') : t('device.provisionSubmit')}
          block
          onPress={() => mutation.mutate()}
          disabled={!token || !pairCode.trim() || mutation.isPending}
        />
        <InkButton
          label={t('device.provisionOpenByMac')}
          block
          variant="secondary"
          onPress={() => {
            const value = mac.trim().toUpperCase();
            if (!value) return;
            router.push(`/device/${encodeURIComponent(value)}`);
          }}
          disabled={!mac.trim()}
          style={{ marginTop: 12 }}
        />
      </InkCard>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  label: {
    marginBottom: 8,
    fontWeight: '600',
  },
  input: {
    height: 50,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 16,
    marginBottom: 14,
    color: theme.colors.ink,
  },
});
