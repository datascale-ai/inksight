import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { BookOpen, Monitor, Smartphone } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useI18n } from '@/lib/i18n';
import { setOnboardingSeen } from '@/lib/storage';
import { theme } from '@/lib/theme';

export default function OnboardingScreen() {
  const { t } = useI18n();
  const slides = [
    { title: t('onboarding.slide1Title'), summary: t('onboarding.slide1Summary'), icon: BookOpen },
    { title: t('onboarding.slide2Title'), summary: t('onboarding.slide2Summary'), icon: Smartphone },
    { title: t('onboarding.slide3Title'), summary: t('onboarding.slide3Summary'), icon: Monitor },
  ];
  const [index, setIndex] = useState(0);
  const slide = slides[index];
  const isLast = index === slides.length - 1;

  async function handleNext() {
    if (!isLast) {
      setIndex((current) => current + 1);
      return;
    }
    await setOnboardingSeen(true);
    router.replace('/(tabs)/today');
  }

  async function handleSkip() {
    await setOnboardingSeen(true);
    router.replace('/(tabs)/today');
  }

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('onboarding.title')}</InkText>
      <InkText dimmed>{t('onboarding.subtitle')}</InkText>

      <InkCard style={styles.heroCard}>
        <View style={styles.iconCircle}>
          <slide.icon size={48} color={theme.colors.ink} strokeWidth={1.4} />
        </View>
        <InkText serif style={styles.slideTitle}>{slide.title}</InkText>
        <InkText dimmed style={styles.slideSummary}>{slide.summary}</InkText>
      </InkCard>

      <View style={styles.indicators}>
        {slides.map((item, current) => (
          <View key={item.title} style={[styles.dot, current === index ? styles.dotActive : null]} />
        ))}
      </View>

      <View style={styles.actions}>
        {!isLast ? <InkButton label={t('onboarding.skip')} variant="secondary" onPress={handleSkip} /> : null}
        <InkButton label={isLast ? t('onboarding.start') : t('onboarding.next')} onPress={handleNext} />
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  heroCard: {
    minHeight: 280,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconCircle: {
    width: 96,
    height: 96,
    borderRadius: 999,
    backgroundColor: theme.colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: theme.spacing.lg,
  },
  slideTitle: {
    fontSize: 28,
    lineHeight: 40,
    textAlign: 'center',
  },
  slideSummary: {
    marginTop: 16,
    fontSize: 16,
    lineHeight: 26,
    textAlign: 'center',
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
    backgroundColor: theme.colors.ink,
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
});
