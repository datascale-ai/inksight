import { useEffect, useMemo, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { ClipboardCheck, Compass, Globe, History, Settings2 } from 'lucide-react-native';
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
import { useI18n } from '@/lib/i18n';
import { localizeCatalogMode } from '@/lib/mode-display';
import { theme } from '@/lib/theme';

function tf(t: (key: string, vars?: Record<string, string | number>) => string, key: string, fallback: string, vars?: Record<string, string | number>) {
  const resolved = t(key, vars);
  return resolved === key ? fallback : resolved;
}

export default function MeScreen() {
  const { locale, t, setLocale } = useI18n();
  const showToast = useToast();
  const user = useAuthStore((state) => state.user);
  const signOut = useAuthStore((state) => state.signOut);
  const token = useAuthStore((state) => state.token);
  const [history, setHistory] = useState<LocalHistoryItem[]>([]);
  const [favoriteCount, setFavoriteCount] = useState(0);
  const devicesQuery = useQuery({
    queryKey: ['me-devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });

  useEffect(() => {
    getLocalHistory().then((items) => setHistory(items.slice(0, 3)));
    getLocalFavorites().then((items) => setFavoriteCount(items.length));
  }, []);

  function handleLogout() {
    Alert.alert(
      tf(t, 'me.logoutConfirmTitle', 'Sign out'),
      tf(t, 'me.logoutConfirmMessage', 'Are you sure you want to sign out?'),
      [
        { text: tf(t, 'common.cancel', 'Cancel'), style: 'cancel' },
        {
          text: tf(t, 'me.logoutConfirm', 'Sign out'),
          style: 'destructive',
          onPress: () => signOut(),
        },
      ],
    );
  }

  async function handleLanguage(nextLocale: 'zh' | 'en') {
    if (nextLocale === locale) {
      return;
    }
    await setLocale(nextLocale);
    showToast(tf(t, 'me.languageChanged', 'Language updated'));
  }

  const summaryItems = useMemo(
    () => [
      { label: tf(t, 'me.summaryFavorites', 'Favorites'), value: String(favoriteCount) },
      { label: tf(t, 'me.summaryHistory', 'History'), value: String(history.length) },
      { label: tf(t, 'me.summaryDevices', 'Devices'), value: String(devicesQuery.data?.devices?.length || 0) },
    ],
    [favoriteCount, history.length, devicesQuery.data?.devices?.length, t],
  );

  type Entry = {
    title: string;
    subtitle: string;
    icon: typeof Globe;
    route?: string;
    onPress?: () => void;
  };

  const entries: Entry[] = [
    { title: tf(t, 'me.settings', 'Settings'), subtitle: tf(t, 'me.settingsDesc', 'Preferences, cache, and experiments'), icon: Settings2, route: '/settings' },
    { title: tf(t, 'me.onboarding', 'Onboarding'), subtitle: tf(t, 'me.onboardingDesc', 'Replay product intro and guidance'), icon: Compass, route: '/onboarding' },
    { title: tf(t, 'me.requests', 'Requests'), subtitle: tf(t, 'me.requestsDesc', 'Review device sharing requests'), icon: ClipboardCheck, route: '/device/requests' },
  ];

  return (
    <AppScreen
      header={
        <>
          <InkText serif style={styles.title}>{tf(t, 'me.title', 'Me')}</InkText>
          <InkText dimmed>{tf(t, 'me.subtitle', 'Account, preferences, language, and guidance.')}</InkText>
        </>
      }
    >
      <InkCard style={styles.heroCard}>
        <InkText style={styles.name}>{user?.username || tf(t, 'me.guest', 'Guest')}</InkText>
        <InkText dimmed style={styles.tagline}>
          {user ? tf(t, 'me.userTagline', 'Your reading account and devices') : tf(t, 'me.guestTagline', 'Sign in to sync devices and preferences')}
        </InkText>
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
              <InkChip label={tf(t, 'me.guestBenefitOne', 'Sync')} />
              <InkChip label={tf(t, 'me.guestBenefitTwo', 'Save')} />
              <InkChip label={tf(t, 'me.guestBenefitThree', 'Share')} />
            </View>
            <InkButton label={tf(t, 'me.login', 'Sign in / Register')} block onPress={() => router.push('/login')} style={styles.heroButton} />
          </>
        ) : (
          <View style={styles.row}>
            <InkButton label={tf(t, 'me.settings', 'Settings')} variant="secondary" onPress={() => router.push('/settings')} />
            <InkButton label={tf(t, 'me.logout', 'Sign out')} onPress={handleLogout} />
          </View>
        )}
      </InkCard>

      <InkCard>
        <View style={styles.entryRow}>
          <View style={styles.entryIcon}>
            <Globe size={18} color={theme.colors.brandInk} strokeWidth={theme.strokeWidth} />
          </View>
          <View style={styles.entryText}>
            <InkText style={styles.entryTitle}>{tf(t, 'me.language', 'Language')}</InkText>
            <InkText dimmed>{tf(t, 'me.languageDesc', 'Switch between Chinese and English')}</InkText>
          </View>
        </View>
        <View style={styles.languageButtons}>
          <InkButton
            label={tf(t, 'me.languageOptionZh', '中文')}
            block
            variant={locale === 'zh' ? 'primary' : 'secondary'}
            onPress={() => handleLanguage('zh')}
            style={styles.languageButton}
          />
          <InkButton
            label={tf(t, 'me.languageOptionEn', 'English')}
            block
            variant={locale === 'en' ? 'primary' : 'secondary'}
            onPress={() => handleLanguage('en')}
            style={styles.languageButton}
          />
        </View>
      </InkCard>

      <InkCard>
        <View style={styles.recentHeader}>
          <View style={styles.recentTitleRow}>
            <History size={18} color={theme.colors.brandInk} strokeWidth={theme.strokeWidth} />
            <InkText style={styles.entryTitle}>{tf(t, 'me.recentBrowsing', 'Recent browsing')}</InkText>
          </View>
          <Pressable onPress={() => router.push('/(tabs)/browse')}>
            <InkText style={styles.recentLink}>{tf(t, 'me.recentBrowsingLink', 'Open browse')}</InkText>
          </Pressable>
        </View>
        {history.length === 0 ? (
          <InkText dimmed>{tf(t, 'me.recentBrowsingEmpty', 'Your recent cards will show up here.')}</InkText>
        ) : (
          history.map((item) => (
            <Pressable
              key={item.id}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.mode_id)}?kind=content&segment=${encodeURIComponent('history')}&title=${encodeURIComponent(localizeCatalogMode({ mode_id: item.mode_id, display_name: item.display_name, description: '' }, locale).display_name)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(item.viewed_at)}`,
                )
              }
            >
              <View style={styles.recentItem}>
                <InkText style={styles.recentItemTitle}>{localizeCatalogMode({ mode_id: item.mode_id, display_name: item.display_name, description: '' }, locale).display_name}</InkText>
                <InkText dimmed style={styles.recentItemSummary}>{item.summary}</InkText>
              </View>
            </Pressable>
          ))
        )}
      </InkCard>

      {entries.map((entry) => {
        const { title, subtitle, icon: Icon, route } = entry;
        const handler = entry.onPress ?? (route ? () => router.push(route as never) : undefined);
        return (
          <Pressable
            key={title}
            onPress={handler}
            disabled={!handler}
            style={({ pressed }) => (pressed && handler ? styles.pressed : undefined)}
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
  languageButtons: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 14,
  },
  languageButton: {
    flex: 1,
  },
  pressed: {
    opacity: 0.85,
  },
});
