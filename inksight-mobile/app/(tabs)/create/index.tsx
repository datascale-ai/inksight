import { Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { LayoutTemplate, PenSquare, Sparkles } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkText } from '@/components/ui/InkText';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function CreateScreen() {
  const { t } = useI18n();
  const inspirations = [
    {
      title: t('create.inspirationOneTitle'),
      body: t('create.inspirationOneBody'),
      badge: t('create.inspirationOneBadge'),
    },
    {
      title: t('create.inspirationTwoTitle'),
      body: t('create.inspirationTwoBody'),
      badge: t('create.inspirationTwoBadge'),
    },
    {
      title: t('create.inspirationThreeTitle'),
      body: t('create.inspirationThreeBody'),
      badge: t('create.inspirationThreeBadge'),
    },
  ];
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
      <View style={styles.section}>
        <InkText style={styles.sectionTitle}>{t('create.inspirationTitle')}</InkText>
        {inspirations.map((item) => (
          <InkCard key={item.title} style={styles.inspirationCard}>
            <InkChip label={item.badge} active />
            <InkText serif style={styles.inspirationBody}>{item.body}</InkText>
            <InkText style={styles.inspirationTitle}>{item.title}</InkText>
          </InkCard>
        ))}
      </View>

      <View style={styles.section}>
        <InkText style={styles.sectionTitle}>{t('create.quickStartTitle')}</InkText>
        {options.map(({ title, desc, icon: Icon, route }) => (
          <Pressable key={title} onPress={() => router.push(route as never)}>
            <InkCard style={styles.optionCard}>
              <View style={styles.optionRow}>
                <View style={styles.optionIcon}>
                  <Icon color={theme.colors.brandInk} size={18} strokeWidth={theme.strokeWidth} />
                </View>
                <View style={styles.optionText}>
                  <InkText style={styles.optionTitle}>{title}</InkText>
                  <InkText dimmed style={styles.optionDesc}>{desc}</InkText>
                </View>
              </View>
            </InkCard>
          </Pressable>
        ))}
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 28,
    fontWeight: '600',
  },
  subtitle: {
    marginTop: 4,
  },
  section: {
    gap: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  inspirationCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
    gap: 14,
  },
  inspirationBody: {
    fontSize: 24,
    lineHeight: 36,
  },
  inspirationTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: theme.colors.brandInk,
  },
  optionCard: {
    backgroundColor: '#FFFCF7',
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
    backgroundColor: theme.colors.accentSoft,
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
});
