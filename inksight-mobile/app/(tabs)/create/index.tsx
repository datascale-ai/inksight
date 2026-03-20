import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { Sparkles, LayoutTemplate, PenSquare } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function CreateScreen() {
  const { t } = useI18n();
  const options = [
    { title: t('create.option.aiTitle'), desc: t('create.option.aiDesc'), icon: Sparkles, route: '/create/generate' },
    { title: t('create.option.templateTitle'), desc: t('create.option.templateDesc'), icon: LayoutTemplate, route: '/create/editor' },
    { title: t('create.option.blankTitle'), desc: t('create.option.blankDesc'), icon: PenSquare, route: '/create/editor' },
  ];

  return (
    <AppScreen
      header={
        <View>
          <InkText serif style={styles.title}>{t('create.title')}</InkText>
          <InkText dimmed style={styles.subtitle}>{t('create.subtitle')}</InkText>
        </View>
      }
    >

      {options.map(({ title, desc, icon: Icon, route }) => (
        <InkCard key={title} onTouchEnd={() => router.push(route as never)}>
          <View style={styles.optionRow}>
            <View style={styles.optionIcon}>
              <Icon color={theme.colors.ink} size={18} strokeWidth={theme.strokeWidth} />
            </View>
            <View style={styles.optionText}>
              <InkText style={styles.optionTitle}>{title}</InkText>
              <InkText dimmed style={styles.optionDesc}>{desc}</InkText>
            </View>
          </View>
        </InkCard>
      ))}

      <InkCard>
        <InkText style={styles.previewTitle}>{t('create.previewTitle')}</InkText>
        <InkText dimmed style={styles.previewText}>{t('create.previewText')}</InkText>
        <View style={styles.previewPanel}>
          <InkText serif style={styles.previewSerif}>{t('create.previewQuote')}</InkText>
        </View>
        <View style={styles.previewActions}>
          <InkButton label={t('create.openEditor')} block onPress={() => router.push('/create/editor')} />
          <InkButton label={t('create.aiGenerate')} block variant="secondary" onPress={() => router.push('/create/generate')} />
        </View>
      </InkCard>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  subtitle: {
    marginTop: 4,
  },
  optionRow: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
  },
  optionIcon: {
    width: 42,
    height: 42,
    borderRadius: 999,
    backgroundColor: theme.colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  optionText: {
    flex: 1,
  },
  optionTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  optionDesc: {
    marginTop: 4,
    lineHeight: 21,
  },
  previewTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  previewText: {
    marginTop: 8,
    lineHeight: 21,
  },
  previewPanel: {
    marginVertical: 16,
    borderRadius: theme.radius.md,
    padding: theme.spacing.lg,
    backgroundColor: theme.colors.surface,
  },
  previewSerif: {
    fontSize: 24,
    lineHeight: 38,
  },
  previewActions: {
    gap: 12,
  },
});
