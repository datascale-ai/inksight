import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, useWindowDimensions, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Clock, Heart, Layers } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkEmptyState } from '@/components/ui/InkEmptyState';
import { ModeIcon } from '@/components/content/ModeIcon';
import { theme } from '@/lib/theme';
import { useAuthStore } from '@/features/auth/store';
import { getLocalFavorites, getLocalHistory } from '@/features/content/storage';
import { listUserDevices, getDeviceFavorites, getDeviceHistory } from '@/features/device/api';
import { listModes } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';

const segments = ['history', 'favorites', 'modes'] as const;

export default function BrowseScreen() {
  const { t } = useI18n();
  const { width: screenWidth } = useWindowDimensions();
  const COLUMNS = 3;
  const GAP = 10;
  const PADDING = theme.spacing.lg;
  const modeCardWidth = (screenWidth - PADDING * 2 - GAP * (COLUMNS - 1)) / COLUMNS;
  const [segment, setSegment] = useState<(typeof segments)[number]>('history');
  const [localFavorites, setLocalFavorites] = useState<Awaited<ReturnType<typeof getLocalFavorites>>>([]);
  const [localHistory, setLocalHistory] = useState<Awaited<ReturnType<typeof getLocalHistory>>>([]);
  const token = useAuthStore((state) => state.token);
  const devicesQuery = useQuery({
    queryKey: ['browse-devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });
  const activeMac = devicesQuery.data?.devices?.[0]?.mac;

  const modesQuery = useQuery({
    queryKey: ['mode-catalog'],
    queryFn: listModes,
  });
  const historyQuery = useQuery({
    queryKey: ['device-history', activeMac, token],
    queryFn: () => getDeviceHistory(activeMac || '', token || ''),
    enabled: Boolean(activeMac && token),
    staleTime: 5 * 60 * 1000,
  });
  const favoritesQuery = useQuery({
    queryKey: ['device-favorites', activeMac, token],
    queryFn: () => getDeviceFavorites(activeMac || '', token || ''),
    enabled: Boolean(activeMac && token),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    getLocalFavorites().then(setLocalFavorites);
    getLocalHistory().then(setLocalHistory);
  }, [segment]);

  const items = useMemo(() => {
    if (segment === 'modes') {
      return (modesQuery.data?.modes || []).map((item) => ({
        title: item.mode_id,
        summary: item.description || item.display_name,
        time: item.source === 'custom' ? 'custom' : 'builtin',
      }));
    }
    if (segment === 'favorites') {
      if (!token) {
        return localFavorites.map((item) => ({
          title: item.display_name,
          summary: item.summary,
          time: item.saved_at,
        }));
      }
      return (favoritesQuery.data?.favorites || []).map((item) => ({
        title: item.mode_id,
        summary: String(item.content?.text || item.content?.quote || item.content?.summary || 'favorited content'),
        time: item.time,
      }));
    }
    if (!token) {
      return localHistory.map((item) => ({
        title: item.display_name,
        summary: item.summary,
        time: item.viewed_at,
      }));
    }
    return (historyQuery.data?.history || []).map((item) => ({
      title: item.mode_id,
      summary: String(item.content?.text || item.content?.quote || item.content?.summary || 'history content'),
      time: item.time,
    }));
  }, [segment, token, modesQuery.data, favoritesQuery.data, historyQuery.data, localFavorites, localHistory]);

  const isRefreshing = modesQuery.isRefetching || historyQuery.isRefetching || favoritesQuery.isRefetching;

  const handleRefresh = useCallback(async () => {
    await lightImpact();
    if (segment === 'modes') {
      await modesQuery.refetch();
    } else if (segment === 'favorites') {
      if (token) await favoritesQuery.refetch();
      else getLocalFavorites().then(setLocalFavorites);
    } else {
      if (token) await historyQuery.refetch();
      else getLocalHistory().then(setLocalHistory);
    }
    await successFeedback();
  }, [segment, token, modesQuery, favoritesQuery, historyQuery]);

  return (
    <AppScreen
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} tintColor={theme.colors.ink} />}
      header={
        <View>
          <InkText serif style={styles.title}>{t('browse.title')}</InkText>
          <InkText dimmed style={styles.subtitle}>{t('browse.subtitle')}</InkText>
        </View>
      }
    >

      <View style={styles.segmentWrap}>
        {segments.map((item) => {
          const selected = item === segment;
          return (
            <Pressable key={item} onPress={() => setSegment(item)} style={[styles.segmentButton, selected ? styles.segmentSelected : null]}>
              <InkText style={selected ? styles.segmentTextSelected : styles.segmentText}>{t(`browse.segment.${item}`)}</InkText>
            </Pressable>
          );
        })}
      </View>

      {segment === 'modes' ? (
        <View style={styles.grid}>
          {items.length === 0 ? (
            <InkEmptyState icon={Layers} title={t('browse.emptyModes')} subtitle={t('browse.emptyModesDesc')} />
          ) : null}
          {items.map((item) => (
            <Pressable
              key={item.title}
              style={{ width: modeCardWidth }}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.title)}?kind=mode&title=${encodeURIComponent(item.title)}&summary=${encodeURIComponent(item.summary)}`,
                )
              }
            >
              <InkCard style={styles.modeCard}>
                <View style={styles.modeIcon}>
                  <ModeIcon modeId={item.title} />
                </View>
                <InkText style={styles.modeTitle}>{item.title}</InkText>
                <InkText dimmed style={styles.modeSummary}>{item.summary}</InkText>
              </InkCard>
            </Pressable>
          ))}
        </View>
      ) : (
        <View style={styles.list}>
          {!token ? (
            <InkCard>
              <InkText dimmed>{t('browse.localFallback')}</InkText>
            </InkCard>
          ) : null}
          {items.length === 0 ? (
            <InkEmptyState
              icon={segment === 'favorites' ? Heart : Clock}
              title={t(segment === 'favorites' ? 'browse.emptyFavorites' : 'browse.emptyHistory')}
              subtitle={t(segment === 'favorites' ? 'browse.emptyFavoritesDesc' : 'browse.emptyHistoryDesc')}
            />
          ) : null}
          {items.map((item) => (
            <Pressable
              key={`${segment}-${item.title}-${item.time}`}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.title)}?kind=content&segment=${encodeURIComponent(segment)}&title=${encodeURIComponent(item.title)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(item.time)}`,
                )
              }
            >
              <InkCard style={styles.listCard}>
                <InkText style={styles.listTitle}>{item.title}</InkText>
                <InkText dimmed style={styles.listSummary}>{item.summary}</InkText>
                <InkText dimmed style={styles.listTime}>{item.time}</InkText>
              </InkCard>
            </Pressable>
          ))}
        </View>
      )}

      <InkCard>
        <InkText style={styles.listTitle}>{t('browse.moreModes')}</InkText>
        <InkText dimmed style={styles.listSummary}>{t('browse.moreModesDesc')}</InkText>
        <Pressable onPress={() => router.push('/browse/modes')}>
          <InkText style={styles.catalogLink}>{t('browse.moreModesLink')}</InkText>
        </Pressable>
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
  segmentWrap: {
    flexDirection: 'row',
    backgroundColor: theme.colors.border,
    borderRadius: 14,
    padding: 4,
  },
  segmentButton: {
    flex: 1,
    alignItems: 'center',
    borderRadius: 12,
    paddingVertical: 10,
  },
  segmentSelected: {
    backgroundColor: theme.colors.card,
  },
  segmentText: {
    color: theme.colors.secondary,
  },
  segmentTextSelected: {
    fontWeight: '600',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  modeCard: {
    width: '100%',
    alignItems: 'center',
    paddingHorizontal: 6,
  },
  modeIcon: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 999,
    backgroundColor: theme.colors.surface,
  },
  modeTitle: {
    marginTop: 10,
    fontSize: 12,
    fontWeight: '600',
  },
  modeSummary: {
    marginTop: 4,
    fontSize: 11,
    textAlign: 'center',
  },
  list: {
    gap: 12,
  },
  listCard: {
    gap: 6,
  },
  listTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  listSummary: {
    lineHeight: 22,
  },
  listTime: {
    fontSize: 12,
  },
  catalogLink: {
    marginTop: 12,
    color: theme.colors.accent,
    fontWeight: '600',
  },
});
