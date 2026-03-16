import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkText } from '@/components/ui/InkText';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';
import { getOnboardingSeen } from '@/lib/storage';

export default function IndexScreen() {
  const { t } = useI18n();
  const hydrated = useAuthStore((state) => state.hydrated);
  const [onboardingSeen, setOnboardingState] = useState<boolean | null>(null);

  useEffect(() => {
    getOnboardingSeen().then(setOnboardingState);
  }, []);

  if (!hydrated || onboardingSeen === null) {
    return (
      <AppScreen>
        <InkText serif style={{ fontSize: 28, fontWeight: '600' }}>InkSight</InkText>
        <InkText dimmed>{t('app.booting')}</InkText>
      </AppScreen>
    );
  }

  return <Redirect href={onboardingSeen ? '/(tabs)/today' : '/onboarding'} />;
}
