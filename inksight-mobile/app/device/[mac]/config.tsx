import { useEffect, useState } from 'react';
import { Alert, StyleSheet, TextInput, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { getDeviceConfig, saveDeviceConfig } from '@/features/device/api';
import { useI18n } from '@/lib/i18n';
import { modeDisplayName } from '@/lib/mode-display';
import { listModes } from '@/features/modes/api';
import { theme } from '@/lib/theme';

export default function DeviceConfigScreen() {
  const { locale, t } = useI18n();
  const { mac } = useLocalSearchParams<{ mac: string }>();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const configQuery = useQuery({
    queryKey: ['edit-device-config', mac, token],
    queryFn: () => getDeviceConfig(mac || '', token || ''),
    enabled: Boolean(mac && token),
  });
  const modesQuery = useQuery({
    queryKey: ['mode-catalog-config'],
    queryFn: listModes,
  });

  const [nickname, setNickname] = useState('');
  const [city, setCity] = useState('Hangzhou');
  const [refreshInterval, setRefreshInterval] = useState('60');
  const [selectedModes, setSelectedModes] = useState<string[]>(['DAILY']);

  useEffect(() => {
    if (!configQuery.data) return;
    setNickname(configQuery.data.nickname || '');
    setCity(configQuery.data.city || 'Hangzhou');
    setRefreshInterval(String(configQuery.data.refreshInterval || 60));
    setSelectedModes(configQuery.data.modes || ['DAILY']);
  }, [configQuery.data]);

  const saveMutation = useMutation({
    mutationFn: async () =>
      saveDeviceConfig(token || '', {
        mac: mac || '',
        nickname,
        city,
        modes: selectedModes,
        refreshInterval: Number(refreshInterval) || 60,
        refreshStrategy: configQuery.data?.refreshStrategy || 'random',
        language: configQuery.data?.language || 'zh',
        contentTone: configQuery.data?.contentTone || 'neutral',
        llmProvider: configQuery.data?.llmProvider || 'deepseek',
        llmModel: configQuery.data?.llmModel || 'deepseek-chat',
      }),
    onSuccess: () => {
      if (mac) {
        queryClient.invalidateQueries({ queryKey: ['device-state', mac] });
        queryClient.invalidateQueries({ queryKey: ['device-config', mac] });
        queryClient.invalidateQueries({ queryKey: ['device-widget', mac] });
      }
      queryClient.invalidateQueries({ queryKey: ['edit-device-config', mac, token] });
      Alert.alert(t('common.saved'), t('settings.savedBody'));
    },
    onError: (error) => Alert.alert(t('settings.saveFailed'), error instanceof Error ? error.message : t('settings.saveFailed')),
  });

  function toggleMode(modeId: string) {
    setSelectedModes((current) =>
      current.includes(modeId) ? current.filter((item) => item !== modeId) : [...current, modeId],
    );
  }

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('nav.deviceConfig')}</InkText>
      <InkText dimmed>{t('device.configTitle')}</InkText>

      <InkCard>
        <InkText style={styles.label}>{t('device.configNickname')}</InkText>
        <TextInput value={nickname} onChangeText={setNickname} style={styles.input} />
        <InkText style={styles.label}>{t('device.configCity')}</InkText>
        <TextInput value={city} onChangeText={setCity} style={styles.input} />
        <InkText style={styles.label}>{t('device.configRefreshInterval')}</InkText>
        <TextInput value={refreshInterval} onChangeText={setRefreshInterval} keyboardType="number-pad" style={styles.input} />
      </InkCard>

      <InkCard>
        <InkText style={styles.label}>{t('browse.segment.modes')}</InkText>
        <View style={styles.modeWrap}>
          {(modesQuery.data?.modes || []).map((mode) => {
            const active = selectedModes.includes(mode.mode_id);
            return (
              <InkButton
                key={mode.mode_id}
                label={modeDisplayName(mode.mode_id, locale, mode.display_name)}
                variant={active ? 'primary' : 'secondary'}
                onPress={() => toggleMode(mode.mode_id)}
              />
            );
          })}
        </View>
      </InkCard>

      <InkButton
        label={saveMutation.isPending ? t('common.loading') : t('common.save')}
        block
        onPress={() => saveMutation.mutate()}
        disabled={saveMutation.isPending || selectedModes.length === 0}
      />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
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
  modeWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
});
