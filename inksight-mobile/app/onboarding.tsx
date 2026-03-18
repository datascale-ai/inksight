import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { Cpu, PenSquare, Sparkles } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkButton } from '@/components/ui/InkButton';
import { InkChip } from '@/components/ui/InkChip';
import { InkText } from '@/components/ui/InkText';
import { setOnboardingSeen } from '@/lib/storage';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function OnboardingScreen() {
  const { t } = useI18n();
  const slides = [
    {
      title: t('onboarding.slide1Title'),
      summary: t('onboarding.slide1Summary'),
      cta: t('onboarding.slide1Cta'),
      preview: (
        <InkCard style={styles.previewHero}>
          <InkChip label={t('onboarding.previewTodayChip')} active />
          <InkText serif style={styles.previewHeroText}>{t('onboarding.previewTodayQuote')}</InkText>
          <InkText dimmed style={styles.previewHeroMeta}>{t('onboarding.previewTodayMeta')}</InkText>
        </InkCard>
      ),
    },
    {
      title: t('onboarding.slide2Title'),
      summary: t('onboarding.slide2Summary'),
      cta: t('onboarding.slide2Cta'),
      preview: (
        <InkCard style={styles.previewDevice}>
          <View style={styles.devicePreviewHeader}>
            <View style={styles.previewIconCircle}>
              <Cpu size={20} color={theme.colors.brandInk} strokeWidth={theme.strokeWidth} />
            </View>
            <View style={styles.previewDeviceText}>
              <InkText style={styles.previewDeviceTitle}>{t('onboarding.previewDeviceTitle')}</InkText>
              <InkText dimmed>{t('onboarding.previewDeviceBody')}</InkText>
            </View>
          </View>
          <InkButton label={t('common.pushToDevice')} block />
        </InkCard>
      ),
    },
    {
      title: t('onboarding.slide3Title'),
      summary: t('onboarding.slide3Summary'),
      cta: t('onboarding.slide3Cta'),
      preview: (
        <InkCard style={styles.previewCreate}>
          <View style={styles.previewCreateHeader}>
            <View style={styles.previewIconCircle}>
              <Sparkles size={20} color={theme.colors.brandInk} strokeWidth={theme.strokeWidth} />
            </View>
            <InkText style={styles.previewDeviceTitle}>{t('onboarding.previewCreateTitle')}</InkText>
          </View>
          <View style={styles.promptPanel}>
            <InkText dimmed>{t('onboarding.previewCreatePrompt')}</InkText>
          </View>
          <View style={styles.createFooter}>
            <PenSquare size={16} color={theme.colors.accent} strokeWidth={theme.strokeWidth} />
            <InkText style={styles.createFooterText}>{t('onboarding.previewCreateFooter')}</InkText>
          </View>
        </InkCard>
      ),
    },
  ];
  const [index, setIndex] = useState(0);
  const slide = slides[index];
  const isLast = index === slides.length - 1;

  async function finish() {
    await setOnboardingSeen(true);
    router.replace('/(tabs)/today');
  }

  async function handleNext() {
    if (!isLast) {
      setIndex((current) => current + 1);
      return;
    }
    await finish();
  }

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('onboarding.title')}</InkText>
      <InkText dimmed style={styles.subtitle}>{t('onboarding.subtitle')}</InkText>

      {slide.preview}

      <InkCard style={styles.storyCard}>
        <InkText serif style={styles.slideTitle}>{slide.title}</InkText>
        <InkText dimmed style={styles.slideSummary}>{slide.summary}</InkText>
        <InkChip label={slide.cta} active />
      </InkCard>

      <View style={styles.indicators}>
        {slides.map((item, current) => (
          <View key={item.title} style={[styles.dot, current === index ? styles.dotActive : null]} />
        ))}
      </View>

      <View style={styles.actions}>
        {!isLast ? <InkButton label={t('onboarding.skip')} variant="secondary" onPress={finish} /> : null}
        <InkButton label={isLast ? t('onboarding.start') : t('onboarding.next')} onPress={handleNext} />
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
  previewHero: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
    minHeight: 260,
    justifyContent: 'space-between',
  },
  previewHeroText: {
    marginTop: 28,
    fontSize: 28,
    lineHeight: 42,
  },
  previewHeroMeta: {
    marginTop: 18,
  },
  previewDevice: {
    gap: 18,
    minHeight: 240,
    justifyContent: 'space-between',
  },
  devicePreviewHeader: {
    flexDirection: 'row',
    gap: 12,
  },
  previewIconCircle: {
    width: 44,
    height: 44,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  previewDeviceText: {
    flex: 1,
  },
  previewDeviceTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 6,
  },
  previewCreate: {
    gap: 16,
    minHeight: 240,
  },
  previewCreateHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  promptPanel: {
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    padding: theme.spacing.md,
    minHeight: 92,
    justifyContent: 'center',
  },
  createFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  createFooterText: {
    color: theme.colors.accent,
    fontWeight: '600',
  },
  storyCard: {
    gap: 14,
  },
  slideTitle: {
    fontSize: 24,
    lineHeight: 34,
  },
  slideSummary: {
    fontSize: 15,
    lineHeight: 24,
  },
  indicators: {
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.tertiary,
  },
  dotActive: {
    width: 28,
    backgroundColor: theme.colors.accent,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
});
