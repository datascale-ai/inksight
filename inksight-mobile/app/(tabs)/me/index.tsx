import { useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { Bell, ClipboardCheck, Compass, Globe, Settings2 } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';
import { getNotificationTime, setNotificationTime } from '@/lib/storage';
import { theme } from '@/lib/theme';

export default function MeScreen() {
  const { t, locale, setLocale } = useI18n();
  const showToast = useToast();
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  const [notifTime, setNotifTime] = useState('08:00');

  useEffect(() => {
    getNotificationTime().then(setNotifTime);
  }, []);

  function handleLogout() {
    Alert.alert(
      t('me.logoutConfirmTitle'),
      t('me.logoutConfirmMessage'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('me.logoutConfirm'),
          style: 'destructive',
          onPress: () => signOut(),
        },
      ],
    );
  }

  function handleLanguage() {
    Alert.alert(
      t('me.languagePickerTitle'),
      undefined,
      [
        {
          text: 'English',
          onPress: async () => {
            await setLocale('en');
            showToast(t('me.languageChanged'));
          },
        },
        {
          text: '中文',
          onPress: async () => {
            await setLocale('zh');
            showToast(t('me.languageChanged'));
          },
        },
        { text: t('common.cancel'), style: 'cancel' },
      ],
    );
  }

  function handleNotificationTime() {
    const hours = ['06:00', '07:00', '08:00', '09:00', '10:00', '12:00', '18:00', '20:00'];
    Alert.alert(
      t('me.notificationTimeTitle'),
      undefined,
      [
        ...hours.map((time) => ({
          text: time === notifTime ? `${time} ✓` : time,
          onPress: async () => {
            await setNotificationTime(time);
            setNotifTime(time);
            showToast(t('me.notificationTimeChanged'));
          },
        })),
        { text: t('common.cancel'), style: 'cancel' as const },
      ],
    );
  }

  const entries = [
    { title: t('me.notifications'), subtitle: `${t('me.notificationsDescPrefix')} ${notifTime}`, icon: Bell, onPress: handleNotificationTime },
    { title: t('me.language'), subtitle: t('me.languageDesc'), icon: Globe, onPress: handleLanguage },
    { title: t('me.settings'), subtitle: t('me.settingsDesc'), icon: Settings2, route: '/settings' },
    { title: t('me.onboarding'), subtitle: t('me.onboardingDesc'), icon: Compass, route: '/onboarding' },
    { title: t('me.requests'), subtitle: t('me.requestsDesc'), icon: ClipboardCheck, route: '/device/requests' },
  ];

  return (
    <AppScreen
      header={
        <>
          <InkText serif style={styles.title}>{t('me.title')}</InkText>
          <InkText dimmed>{t('me.subtitle')}</InkText>
        </>
      }
    >

      <InkCard>
        <InkText style={styles.name}>{user?.username || t('me.guest')}</InkText>
        <InkText dimmed style={styles.tagline}>{user ? t('me.userTagline') : t('me.guestTagline')}</InkText>
        {user ? (
          <View style={styles.row}>
            <InkButton label={t('me.settings')} variant="secondary" onPress={() => router.push('/settings')} />
            <InkButton label={t('me.logout')} onPress={handleLogout} />
          </View>
        ) : (
          <InkButton label={t('me.login')} block onPress={() => router.push('/login')} />
        )}
      </InkCard>

      {entries.map(({ title, subtitle, icon: Icon, route, onPress }) => {
        const handler = onPress ?? (route ? () => router.push(route as never) : undefined);
        return (
          <Pressable
            key={title}
            onPress={handler}
            disabled={!handler}
            style={({ pressed }) => pressed && handler ? styles.pressed : undefined}
          >
            <InkCard>
              <View style={styles.entryRow}>
                <View style={styles.entryIcon}>
                  <Icon size={18} color={theme.colors.ink} strokeWidth={theme.strokeWidth} />
                </View>
                <View style={styles.entryText}>
                  <InkText style={styles.entryTitle}>{title}</InkText>
                  <InkText dimmed>{subtitle}</InkText>
                </View>
              </View>
            </InkCard>
          </Pressable>
        );
      })}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  name: {
    fontSize: 18,
    fontWeight: '600',
  },
  tagline: {
    marginTop: 6,
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
  },
  entryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  entryIcon: {
    width: 40,
    height: 40,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.surface,
  },
  entryText: {
    flex: 1,
  },
  entryTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
  pressed: {
    opacity: 0.85,
  },
});
