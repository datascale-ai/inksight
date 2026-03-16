import { useEffect, useState } from 'react';
import { Alert, StyleSheet, TextInput, View } from 'react-native';
import { useMutation } from '@tanstack/react-query';
import { router } from 'expo-router';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { previewCustomMode, saveCustomMode, generateMode, type CustomModeDefinition } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function AIGenerateScreen() {
  const { t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const [description, setDescription] = useState('');
  const [generatedMode, setGeneratedMode] = useState<CustomModeDefinition | null>(null);
  const [previewText, setPreviewText] = useState('');

  useEffect(() => {
    if (!description) {
      setDescription(t('generate.defaultPrompt'));
    }
  }, [description, t]);

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!token) {
        throw new Error(t('generate.loginRequired'));
      }
      return generateMode(token, { description });
    },
    onSuccess: async (result) => {
      setGeneratedMode(result);
      if (!token) {
        return;
      }
      try {
        const preview = await previewCustomMode(token, result);
        setPreviewText(preview.preview_text);
      } catch {
        setPreviewText('');
      }
    },
    onError: (error) => {
      Alert.alert(t('generate.generateFailed'), error instanceof Error ? error.message : t('generate.generateFailed'));
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!token || !generatedMode) {
        throw new Error(t('generate.saveRequireMode'));
      }
      return saveCustomMode(token, generatedMode);
    },
    onSuccess: (result) => {
      Alert.alert(t('generate.saveSuccess'), t('generate.saveBody', { modeId: result.mode_id }));
      router.push('/create/editor');
    },
    onError: (error) => {
      Alert.alert(t('generate.saveFailed'), error instanceof Error ? error.message : t('generate.saveFailed'));
    },
  });

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('generate.title')}</InkText>
      <InkText dimmed>{t('generate.subtitle')}</InkText>

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
        <InkText dimmed>{t('generate.resultName', { name: generatedMode?.display_name || t('generate.resultEmpty') })}</InkText>
        <InkText dimmed>{t('generate.resultModeId', { modeId: generatedMode?.mode_id || '-' })}</InkText>
        <View style={styles.preview}>
          <InkText serif style={styles.previewText}>
            {previewText || generatedMode?.content?.static_data?.text || t('generate.resultEmpty')}
          </InkText>
        </View>
        <InkButton
          label={saveMutation.isPending ? t('generate.saveRunning') : t('generate.saveAction')}
          block
          variant="secondary"
          onPress={() => saveMutation.mutate()}
          disabled={!generatedMode || saveMutation.isPending}
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
    padding: theme.spacing.lg,
  },
  previewText: {
    fontSize: 22,
    lineHeight: 34,
  },
});
