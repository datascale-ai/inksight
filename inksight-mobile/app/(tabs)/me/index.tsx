import { useEffect, useMemo, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { Bell, ClipboardCheck, Compass, Globe, History, Settings2 } from 'lucide-react-native';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkText } from '@/components/ui/InkText';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { getLocalFavorites, getLocalHistory, type LocalHistoryItem } from '@/features/content/storage';
import { listUserDevices } from '@/features/device/api';
import { getNotificationTime, setNotificationTime } from '@/lib/storage';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function MeScreen() {
  const { t, setLocale } = useI18n();
  const showToast = useToast();
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  const token = useAuthStore((state) => state.token);
  const [notifTime, setNotifTime] = useState('08:00');
  const [history, setHistory] = useState<LocalHistoryItem[]>([]);
  const [favoriteCount, setFavoriteCount] = useState(0);
  const devicesQuery = useQuery({
    queryKey: ['me-devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });

  useEffect(() => {
    getNotificationTime().then(setNotifTime);
    getLocalHistory().then((items) => setHistory(items.slice(0, 3)));
    getLocalFavorites().then((items) => setFavoriteCount(items.length));
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

  const summaryItems = useMemo(
    () => [
      { label: t('me.summaryFavorites'), value: String(favoriteCount) },
      { label: t('me.summaryHistory'), value: String(history.length) },
      { label: t('me.summaryDevices'), value: String(devicesQuery.data?.devices?.length || 0) },
    ],
    [favoriteCount, history.length, devicesQuery.data?.devices?.length, t],
  );

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
      <InkCard style={styles.heroCard}>
        <InkText style={styles.name}>{user?.username || t('me.guest')}</InkText>
        <InkText dimmed style={styles.tagline}>{user ? t('me.userTagline') : t('me.guestTagline')}</InkText>
        <View style={styles.summaryRow}>
          {summaryItems.map((item) => (
            <View key={item.label} style={styles.summaryItem}>
              <InkText style={styles.summaryValue}>{item.value}</InkText>
              <InkText dimmed style={styles.summaryLabel}>{item.label}</InkText>
            </View>
          ))}
        </View>
        {!user ? (
          <>
            <View style={styles.chipsRow}>
              <InkChip label={t('me.guestBenefitOne')} />
              <InkChip label={t('me.guestBenefitTwo')} />
              <InkChip label={t('me.guestBenefitThree')} />
            </View>
            <InkButton label={t('me.login')} block onPress={() => router.push('/login')} style={styles.heroButton} />
          </>
        ) : (
          <View style={styles.row}>
            <InkButton label={t('me.settings')} variant="secondary" onPress={() => router.push('/settings')} />
            <InkButton label={t('me.logout')} onPress={handleLogout} />
          </View>
        )}
      </InkCard>

      <InkCard>
        <View style={styles.recentHeader}>
          <View style={styles.recentTitleRow}>
            <History size={18} color={theme.colors.brandInk} strokeWidth={theme.strokeWidth} />
            <InkText style={styles.entryTitle}>{t('me.recentBrowsing')}</InkText>
          </View>
          <Pressable onPress={() => router.push('/browse')}>
            <InkText style={styles.recentLink}>{t('me.recentBrowsingLink')}</InkText>
          </Pressable>
        </View>
        {history.length === 0 ? (
          <InkText dimmed>{t('me.recentBrowsingEmpty')}</InkText>
        ) : (
          history.map((item) => (
            <Pressable
              key={item.id}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.mode_id)}?kind=content&segment=${encodeURIComponent('history')}&title=${encodeURIComponent(item.display_name)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(item.viewed_at)}`,
                )
              }
            >
              <View style={styles.recentItem}>
                <InkText style={styles.recentItemTitle}>{item.display_name}</InkText>
                <InkText dimmed style={styles.recentItemSummary}>{item.summary}</InkText>
              </View>
            </Pressable>
          ))
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
                  <Icon size={18} color={theme.colors.brandInk} strokeWidth={theme.strokeWidth} />
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
    fontSize: 28,
    fontWeight: '600',
  },
  heroCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
  },
  name: {
    fontSize: 18,
    fontWeight: '600',
  },
  tagline: {
    marginTop: 6,
  },
  summaryRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 16,
  },
  summaryItem: {
    flex: 1,
    borderRadius: theme.radius.md,
    backgroundColor: 'rgba(255,255,255,0.7)',
    paddingVertical: 12,
    paddingHorizontal: 10,
  },
  summaryValue: {
    fontSize: 20,
    fontWeight: '700',
    color: theme.colors.brandInk,
  },
  summaryLabel: {
    marginTop: 4,
    fontSize: 12,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 16,
  },
  heroButton: {
    marginTop: 16,
  },
  row: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 16,
  },
  recentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
    alignItems: 'center',
    marginBottom: 10,
  },
  recentTitleRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  recentLink: {
    color: theme.colors.accent,
    fontWeight: '600',
  },
  recentItem: {
    paddingTop: 10,
    paddingBottom: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.colors.border,
  },
  recentItemTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  recentItemSummary: {
    marginTop: 6,
    lineHeight: 20,
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
    backgroundColor: theme.colors.accentSoft,
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
