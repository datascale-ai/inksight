import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Image, StyleSheet, TextInput, View } from 'react-native';
import { useMutation, useQuery } from '@tanstack/react-query';
import { router, useLocalSearchParams } from 'expo-router';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { previewCustomModeImage, saveCustomMode, generateMode, listModes, type CustomModeDefinition } from '@/features/modes/api';
import { listUserDevices, type DeviceSummary } from '@/features/device/api';
import { useI18n, tf } from '@/lib/i18n';
import { theme } from '@/lib/theme';

function queryParamToDecodedString(value: string | string[] | undefined): string | null {
  if (value == null || value === '') return null;
  const s = Array.isArray(value) ? value[0] : value;
  if (!s) return null;
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

function pickDevice(
  devices: DeviceSummary[],
  translate: (key: string, vars?: Record<string, string | number | null | undefined>) => string,
) {
  return new Promise<DeviceSummary | null>((resolve) => {
    if (devices.length === 0) {
      resolve(null);
      return;
    }
    if (devices.length === 1) {
      resolve(devices[0]);
      return;
    }
    Alert.alert(
      tf(translate, 'generate.selectDevice', 'Save to device'),
      tf(translate, 'generate.selectDeviceHint', 'Choose which device to save this mode to'),
      [
        ...devices.map((device) => ({
          text: device.nickname || device.mac,
          onPress: () => resolve(device),
        })),
        { text: tf(translate, 'common.cancel', 'Cancel'), style: 'cancel' as const, onPress: () => resolve(null) },
      ],
    );
  });
}

export default function AIGenerateScreen() {
  const { t } = useI18n();
  const params = useLocalSearchParams<{ template?: string | string[] }>();
  const token = useAuthStore((state) => state.token);
  const templateModeId = queryParamToDecodedString(params.template);
  const [description, setDescription] = useState('');
  const [generatedMode, setGeneratedMode] = useState<CustomModeDefinition | null>(null);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  /** 生成接口已返回但 PNG 预览仍在拉取时为 true（isPending 此时已为 false）。 */
  const [previewLoading, setPreviewLoading] = useState(false);
  const [initialized, setInitialized] = useState(false);

  // Fetch template mode to prefill prompt
  const templateQuery = useQuery({
    queryKey: ['generate-template', templateModeId],
    queryFn: listModes,
    enabled: Boolean(templateModeId && !initialized),
  });

  useEffect(() => {
    if (initialized) return;
    if (!templateModeId) {
      setDescription(t('generate.defaultPrompt'));
      setInitialized(true);
      return;
    }
    if (templateQuery.data) {
      const found = templateQuery.data.modes.find((m) => m.mode_id === templateModeId);
      if (found) {
        setDescription(t('generate.templatePrompt', { name: found.display_name, desc: found.description }));
      } else {
        setDescription(t('generate.defaultPrompt'));
      }
      setInitialized(true);
      return;
    }
    if (templateQuery.isError || !templateModeId) {
      setDescription(t('generate.defaultPrompt'));
      setInitialized(true);
    }
  }, [templateModeId, templateQuery.data, templateQuery.isError, initialized, t]);

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!token) {
        throw new Error(t('generate.loginRequired'));
      }
      return generateMode(token, { description });
    },
    onSuccess: async (modeDef) => {
      setGeneratedMode(modeDef);
      setPreviewUri(null);
      setPreviewError(null);
      if (!token) return;
      setPreviewLoading(true);
      try {
        const uri = await previewCustomModeImage(token, modeDef);
        setPreviewUri(uri);
      } catch (err) {
        console.error('Preview image failed:', err);
        setPreviewError(err instanceof Error ? err.message : t('generate.previewFailed'));
      } finally {
        setPreviewLoading(false);
      }
    },
    onError: (error) => {
      Alert.alert(t('generate.generateFailed'), error instanceof Error ? error.message : t('generate.generateFailed'));
    },
  });

  const devicesQuery = useQuery({
    queryKey: ['user-devices'],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!token || !generatedMode) {
        throw new Error(t('generate.saveRequireMode'));
      }
      const devices = devicesQuery.data?.devices || [];
      const device = await pickDevice(devices, t);
      if (!device?.mac) {
        if (devices.length === 0) {
          throw new Error(t('generate.noDevices'));
        }
        return;
      }
      return saveCustomMode(token, generatedMode, device.mac);
    },
    onSuccess: (result) => {
      if (!result) return;
      Alert.alert(t('generate.saveSuccess'), t('generate.saveBody', { modeId: result.mode_id }));
      router.replace('/(tabs)/browse');
    },
    onError: (error) => {
      Alert.alert(t('generate.saveFailed'), error instanceof Error ? error.message : t('generate.saveFailed'));
    },
  });

  const isTemplateMode = Boolean(templateModeId);

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('generate.title')}</InkText>
      <InkText dimmed>
        {isTemplateMode
          ? t('generate.subtitleTemplate', { template: templateModeId })
          : t('generate.subtitle')}
      </InkText>

      <InkCard>
        <InkText style={styles.label}>{t('generate.promptLabel')}</InkText>
        <TextInput
          value={description}
          onChangeText={setDescription}
          multiline
          style={styles.input}
          textAlignVertical="top"
        />
        <InkButton
          label={generateMutation.isPending ? t('generate.generateRunning') : t('generate.generateAction')}
          block
          onPress={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        />
      </InkCard>

      <InkCard>
        <InkText style={styles.label}>{t('generate.resultTitle')}</InkText>
        {generatedMode ? (
          <>
            <InkText dimmed>{t('generate.resultName', { name: generatedMode.display_name })}</InkText>
            <InkText dimmed>{t('generate.resultModeId', { modeId: generatedMode.mode_id })}</InkText>
            {generatedMode.description?.trim() ? (
              <InkText dimmed style={{ marginTop: 8 }}>{generatedMode.description.trim()}</InkText>
            ) : null}
          </>
        ) : (
          <InkText dimmed>{t('generate.resultHint')}</InkText>
        )}
        <View style={styles.preview}>
          {generateMutation.isPending || previewLoading ? (
            <View style={styles.previewPlaceholder}>
              <ActivityIndicator color={theme.colors.ink} />
              <InkText dimmed style={styles.previewLoadingText}>{t('generate.previewRunning')}</InkText>
            </View>
          ) : previewUri ? (
            <Image
              source={{ uri: previewUri }}
              style={styles.previewImage}
              resizeMode="contain"
            />
          ) : previewError ? (
            <View style={styles.previewPlaceholder}>
              <InkText dimmed>{previewError}</InkText>
            </View>
          ) : generatedMode ? (
            <View style={styles.previewPlaceholder}>
              <InkText dimmed>{t('generate.previewFallback')}</InkText>
            </View>
          ) : (
            <View style={styles.previewPlaceholder}>
              <InkText dimmed>{t('generate.resultEmpty')}</InkText>
            </View>
          )}
        </View>
        <InkButton
          label={saveMutation.isPending ? t('generate.saveRunning') : t('generate.saveAction')}
          block
          variant="secondary"
          onPress={() => saveMutation.mutate()}
          disabled={!generatedMode || saveMutation.isPending || devicesQuery.isFetching}
        />
      </InkCard>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  label: {
    marginBottom: 10,
    fontWeight: '600',
  },
  input: {
    minHeight: 150,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    padding: theme.spacing.md,
    marginBottom: 16,
    color: theme.colors.ink,
  },
  preview: {
    marginVertical: 16,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    overflow: 'hidden',
  },
  previewImage: {
    width: '100%',
    aspectRatio: 400 / 300,
    backgroundColor: theme.colors.surface,
  },
  previewPlaceholder: {
    padding: theme.spacing.xl,
    alignItems: 'center',
    gap: 12,
  },
  previewLoadingText: {
    marginTop: 4,
  },
});
