import { useState } from 'react';
import { Alert, StyleSheet, TextInput, View } from 'react-native';
import { useMutation } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { buildStaticModeDefinition, previewCustomMode, saveCustomMode } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function ModeEditorScreen() {
  const { t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const [modeId, setModeId] = useState('MOBILE_NOTE');
  const [displayName, setDisplayName] = useState('Mobile Note');
  const [description, setDescription] = useState('Created from the Expo editor');
  const [text, setText] = useState('Stay with one thing.');

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!token) {
        throw new Error(t('editor.previewLoginError'));
      }
      return previewCustomMode(
        token,
        buildStaticModeDefinition({ modeId, displayName, description, text }),
      );
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!token) {
        throw new Error(t('editor.saveLoginError'));
      }
      return saveCustomMode(
        token,
        buildStaticModeDefinition({ modeId, displayName, description, text }),
      );
    },
    onSuccess: (result) => {
      Alert.alert(t('common.saved'), t('editor.saveBody', { modeId: result.mode_id }));
    },
    onError: (error) => {
      Alert.alert(t('editor.saveFailed'), error instanceof Error ? error.message : t('editor.saveFailed'));
    },
  });

  function runPreview() {
    previewMutation.mutate(undefined, {
      onError: (error) => {
        Alert.alert(t('editor.previewFailed'), error instanceof Error ? error.message : t('editor.previewFailed'));
      },
    });
  }

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('editor.title')}</InkText>
      <InkText dimmed>{t('editor.subtitle')}</InkText>

      <InkCard>
        <InkText style={styles.label}>{t('editor.modeId')}</InkText>
        <TextInput value={modeId} onChangeText={setModeId} autoCapitalize="characters" style={styles.input} />
        <InkText style={styles.label}>{t('editor.displayName')}</InkText>
        <TextInput value={displayName} onChangeText={setDisplayName} style={styles.input} />
        <InkText style={styles.label}>{t('editor.description')}</InkText>
        <TextInput value={description} onChangeText={setDescription} style={styles.input} />
        <InkText style={styles.label}>{t('editor.body')}</InkText>
        <TextInput value={text} onChangeText={setText} multiline style={[styles.input, styles.multiline]} />
        <InkText style={styles.label}>{t('editor.preview')}</InkText>
        <View style={styles.preview}>
          <InkText serif style={styles.previewText}>
            {previewMutation.data?.preview_text || text || t('editor.previewDefault')}
          </InkText>
        </View>
        <View style={styles.buttonRow}>
          <InkButton
            label={previewMutation.isPending ? t('editor.previewRunning') : t('editor.previewAction')}
            variant="secondary"
            onPress={runPreview}
            disabled={previewMutation.isPending}
          />
          <InkButton
            label={saveMutation.isPending ? t('editor.saveRunning') : t('editor.saveAction')}
            onPress={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          />
        </View>
        {!token ? (
          <InkText dimmed style={styles.hint}>{t('editor.loginRequired')}</InkText>
        ) : null}
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
    marginTop: 12,
    marginBottom: 8,
    fontWeight: '600',
  },
  input: {
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    padding: theme.spacing.md,
    color: theme.colors.ink,
  },
  multiline: {
    minHeight: 110,
    textAlignVertical: 'top',
  },
  preview: {
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    padding: theme.spacing.lg,
    marginBottom: 16,
  },
  previewText: {
    fontSize: 24,
    lineHeight: 36,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 12,
  },
  hint: {
    marginTop: 12,
    lineHeight: 20,
  },
});
