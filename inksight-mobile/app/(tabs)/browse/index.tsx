import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Pressable, RefreshControl, StyleSheet, useWindowDimensions, View } from 'react-native';
import { router } from 'expo-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock, Heart, Trash2 } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkEmptyState } from '@/components/ui/InkEmptyState';
import { InkText } from '@/components/ui/InkText';
import { ModeIcon } from '@/components/content/ModeIcon';
import { theme } from '@/lib/theme';
import { useAuthStore } from '@/features/auth/store';
import { getTodayContent } from '@/features/content/api';
import { getLocalFavorites, getLocalHistory } from '@/features/content/storage';
import { listUserDevices, getDeviceFavorites, getDeviceHistory } from '@/features/device/api';
import { listModes, deleteCustomMode } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { localizeCatalogMode } from '@/lib/mode-display';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';

const segments = ['modes', 'history', 'favorites'] as const;

const FEATURED_MODE_IDS = ['DAILY', 'WEATHER', 'BRIEFING', 'POETRY', 'ARTWALL', 'ALMANAC'];

function tf(t: (key: string, vars?: Record<string, string | number>) => string, key: string, fallback: string, vars?: Record<string, string | number>) {
  const resolved = t(key, vars);
  return resolved === key ? fallback : resolved;
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.sectionHeader}>
      <InkText style={styles.sectionTitle}>{title}</InkText>
      {subtitle ? <InkText dimmed style={styles.sectionSubtitle}>{subtitle}</InkText> : null}
    </View>
  );
}

export default function BrowseScreen() {
  const { locale, t } = useI18n();
  const { width: screenWidth } = useWindowDimensions();
  const GAP = 12;
  const PADDING = theme.spacing.lg;
  const cardWidth = (screenWidth - PADDING * 2 - GAP) / 2;
  const [segment, setSegment] = useState<(typeof segments)[number]>('modes');
  const [localFavorites, setLocalFavorites] = useState<Awaited<ReturnType<typeof getLocalFavorites>>>([]);
  const [localHistory, setLocalHistory] = useState<Awaited<ReturnType<typeof getLocalHistory>>>([]);
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();

  const todayQuery = useQuery({
    queryKey: ['browse-recommended-today'],
    queryFn: () => getTodayContent(['DAILY', 'POETRY', 'WEATHER']),
    staleTime: 10 * 60 * 1000,
  });
  const devicesQuery = useQuery({
    queryKey: ['browse-devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });
  const activeMac = devicesQuery.data?.devices?.[0]?.mac;
  const deviceNicknames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const d of devicesQuery.data?.devices || []) {
      map[d.mac] = d.nickname || d.mac;
    }
    return map;
  }, [devicesQuery.data]);
  const modesQuery = useQuery({
    queryKey: ['mode-catalog', token],
    queryFn: () => listModes({ token: token || undefined }),
  });

  const deleteMutation = useMutation({
    mutationFn: ({ modeId, mac }: { modeId: string; mac?: string }) => deleteCustomMode(token || '', modeId, mac),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mode-catalog'] });
      queryClient.invalidateQueries({ queryKey: ['browse-modes-catalog'] });
      modesQuery.refetch();
    },
    onError: (err: Error) => {
      Alert.alert(tf(t, 'browse.deleteFailed', 'Delete failed'), err.message);
    },
  });

  function confirmDeleteMode(modeId: string, displayName: string, mac?: string) {
    Alert.alert(
      tf(t, 'browse.deleteConfirmTitle', 'Delete mode'),
      tf(t, 'browse.deleteConfirmMessage', 'Are you sure you want to delete "{name}"?', { name: displayName }),
      [
        { text: tf(t, 'common.cancel', 'Cancel'), style: 'cancel' },
        { text: tf(t, 'browse.deleteAction', 'Delete'), style: 'destructive', onPress: () => deleteMutation.mutate({ modeId, mac }) },
      ],
    );
  }

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

  const historyItems = useMemo(() => {
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
  }, [token, localHistory, historyQuery.data]);

  const favoriteItems = useMemo(() => {
    if (!token) {
      return localFavorites.map((item) => ({
        title: item.display_name,
        summary: item.summary,
        time: item.saved_at,
      }));
    }
    return (favoritesQuery.data?.favorites || []).map((item) => ({
      title: item.mode_id,
      summary: String(item.content?.text || item.content?.quote || item.content?.summary || tf(t, 'browse.favoriteFallback', 'favorited content')),
      time: item.time,
    }));
  }, [token, localFavorites, favoritesQuery.data, t]);

  const modeItems = modesQuery.data?.modes || [];
  const featuredModes = FEATURED_MODE_IDS
    .map((id) => modeItems.find((m) => m.mode_id === id))
    .filter(Boolean) as typeof modeItems;
  const customModes = modeItems.filter((mode) => mode.source === 'custom').slice(0, 4);
  const recommendedItems = todayQuery.data?.items || [];

  function modeDisplayName(modeId: string) {
    return localizeCatalogMode({ mode_id: modeId, display_name: modeId, description: '' }, locale).display_name;
  }

  function localizeMode(mode: { mode_id: string; display_name: string; description: string }) {
    return localizeCatalogMode(mode, locale);
  }

  function localizedTitle(mode: { mode_id: string; display_name: string; description: string }) {
    const l = localizeCatalogMode(mode, locale);
    return encodeURIComponent(l.display_name);
  }

  function localizedSummary(mode: { mode_id: string; display_name: string; description: string }) {
    const l = localizeCatalogMode(mode, locale);
    return encodeURIComponent(l.description || l.display_name);
  }

  const isRefreshing =
    todayQuery.isRefetching ||
    modesQuery.isRefetching ||
    historyQuery.isRefetching ||
    favoritesQuery.isRefetching;

  const handleRefresh = useCallback(async () => {
    await lightImpact();
    if (segment === 'modes') {
      await Promise.all([todayQuery.refetch(), modesQuery.refetch()]);
    } else if (segment === 'favorites') {
      if (token) await favoritesQuery.refetch();
      else getLocalFavorites().then(setLocalFavorites);
    } else {
      if (token) await historyQuery.refetch();
      else getLocalHistory().then(setLocalHistory);
    }
    await successFeedback();
  }, [segment, token, todayQuery, modesQuery, favoritesQuery, historyQuery]);

  return (
    <AppScreen
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} tintColor={theme.colors.accent} />}
      header={
        <View>
          <InkText serif style={styles.title}>{tf(t, 'browse.title', 'Browse')}</InkText>
          <InkText dimmed style={styles.subtitle}>{tf(t, 'browse.subtitle', 'Discover modes, history, favorites, and recommended content.')}</InkText>
        </View>
      }
    >
      <View style={styles.segmentWrap}>
        {segments.map((item) => {
          const selected = item === segment;
          return (
            <Pressable
              key={item}
              onPress={() => setSegment(item)}
              style={[styles.segmentButton, selected ? styles.segmentSelected : null]}
            >
              <InkText style={selected ? styles.segmentTextSelected : styles.segmentText}>
                {tf(t, `browse.segment.${item}`, item)}
              </InkText>
            </Pressable>
          );
        })}
      </View>

      {segment === 'modes' ? (
        <>
          <View style={styles.sectionBlock}>
            <SectionHeader title={tf(t, 'browse.section.today', 'Today suggestions')} />
            {recommendedItems.map((item) => (
              <Pressable
                key={`recommended-${item.mode_id}`}
                onPress={() =>
                  router.push(
                    `/browse/${encodeURIComponent(item.mode_id)}?kind=content&title=${encodeURIComponent(localizeCatalogMode({ mode_id: item.mode_id, display_name: item.display_name, description: '' }, locale).display_name)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(todayQuery.data?.generated_at || '')}`,
                  )
                }
              >
                <InkCard style={styles.editorialCard}>
                  <View style={styles.editorialTop}>
                    <View style={styles.editorialTitleRow}>
                      <View style={styles.modeIconWrap}>
                        <ModeIcon modeId={item.mode_id} color={theme.colors.brandInk} />
                      </View>
                      <View style={styles.editorialText}>
                        <InkText style={styles.editorialTitle}>{localizeCatalogMode({ mode_id: item.mode_id, display_name: item.display_name, description: '' }, locale).display_name}</InkText>
                        <InkText dimmed style={styles.editorialDesc}>{item.summary}</InkText>
                      </View>
                    </View>
                    <InkChip label={item.mode_id} active />
                  </View>
                </InkCard>
              </Pressable>
            ))}
          </View>

          <View style={styles.sectionBlock}>
            <SectionHeader title={tf(t, 'browse.featuredModes', 'Featured modes')} />
            <View style={styles.grid}>
              {featuredModes.map((mode) => (
                <Pressable
                  key={`featured-${mode.mode_id}`}
                  style={{ width: cardWidth }}
                  onPress={() =>
                    router.push(
                      `/browse/${encodeURIComponent(mode.mode_id)}?kind=mode&title=${localizedTitle(mode)}&summary=${localizedSummary(mode)}`,
                    )
                  }
                >
                  <InkCard style={styles.modeCard}>
                    <View style={styles.modeIconWrap}>
                      <ModeIcon modeId={mode.mode_id} />
                    </View>
                    <InkText style={styles.modeTitle}>{localizeMode(mode).display_name}</InkText>
                    <InkText dimmed style={styles.modeSummary}>{localizeMode(mode).description || mode.mode_id}</InkText>
                  </InkCard>
                </Pressable>
              ))}
            </View>
          </View>

          {customModes.length > 0 ? (
            <View style={styles.sectionBlock}>
              <SectionHeader title={tf(t, 'browse.customModes', 'Custom modes')} />
              {customModes.map((mode) => (
                <InkCard key={`custom-${mode.mode_id}-${mode.mac || ''}`} style={styles.editorialCard}>
                  <View style={styles.editorialTop}>
                    <Pressable
                      style={styles.editorialTitleRow}
                      onPress={() =>
                        router.push(
                          `/browse/${encodeURIComponent(mode.mode_id)}?kind=mode&title=${localizedTitle(mode)}&summary=${localizedSummary(mode)}`,
                        )
                      }
                    >
                      <View style={styles.modeIconWrap}>
                        <ModeIcon modeId={mode.mode_id} color={theme.colors.brandInk} />
                      </View>
                      <View style={styles.editorialText}>
                        <InkText style={styles.editorialTitle}>{localizeMode(mode).display_name}</InkText>
                        <InkText dimmed style={styles.editorialDesc}>
                          {mode.mac ? (deviceNicknames[mode.mac] || mode.mac) : (localizeMode(mode).description || mode.mode_id)}
                        </InkText>
                      </View>
                    </Pressable>
                    <View style={styles.customActions}>
                      <InkChip label={tf(t, 'browse.customBadge', 'Custom')} />
                      <Pressable
                        hitSlop={8}
                        onPress={() => confirmDeleteMode(mode.mode_id, localizeMode(mode).display_name, mode.mac)}
                      >
                        <Trash2 size={18} color={theme.colors.secondary} />
                      </Pressable>
                    </View>
                  </View>
                </InkCard>
              ))}
            </View>
          ) : null}
        </>
      ) : null}

      {segment === 'history' ? (
        <View style={styles.list}>
          {!token ? (
            <InkCard>
              <InkText dimmed>{tf(t, 'browse.localFallback', 'When not signed in, this area shows local cached history and favorites.')}</InkText>
            </InkCard>
          ) : null}
          {historyItems.length === 0 ? (
            <InkEmptyState icon={Clock} title={tf(t, 'browse.emptyHistory', 'No history yet')} subtitle={tf(t, 'browse.emptyHistoryDesc', 'Cards you open will appear here.')} />
          ) : null}
          {historyItems.map((item) => (
            <Pressable
              key={`${segment}-${item.title}-${item.time}`}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.title)}?kind=content&title=${encodeURIComponent(item.title)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(item.time)}`,
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
      ) : null}

      {segment === 'favorites' ? (
        <View style={styles.list}>
          {!token ? (
            <InkCard>
              <InkText dimmed>{tf(t, 'browse.localFallback', 'When not signed in, this area shows local cached history and favorites.')}</InkText>
            </InkCard>
          ) : null}
          {favoriteItems.length === 0 ? (
            <InkEmptyState icon={Heart} title={tf(t, 'browse.emptyFavorites', 'No favorites yet')} subtitle={tf(t, 'browse.emptyFavoritesDesc', 'Long press a card on Today to save it.')} />
          ) : null}
          {favoriteItems.map((item) => (
            <Pressable
              key={`${item.title}-${item.time}`}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.title)}?kind=content&title=${encodeURIComponent(item.title)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(item.time)}`,
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
      ) : null}

      <Pressable onPress={() => router.push('/browse/modes')}>
        <InkCard>
          <InkText style={styles.catalogLink}>{tf(t, 'browse.moreModes', 'More modes')}</InkText>
        </InkCard>
      </Pressable>
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
  segmentWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    backgroundColor: theme.colors.surface,
    borderRadius: 16,
    padding: 4,
    borderWidth: 1,
    borderColor: theme.colors.border,
    gap: 4,
  },
  segmentButton: {
    flexGrow: 1,
    alignItems: 'center',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 8,
  },
  segmentSelected: {
    backgroundColor: theme.colors.card,
  },
  segmentText: {
    color: theme.colors.secondary,
  },
  segmentTextSelected: {
    fontWeight: '600',
    color: theme.colors.brandInk,
  },
  sectionBlock: {
    gap: 10,
  },
  sectionHeader: {
    gap: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  sectionSubtitle: {
    lineHeight: 20,
  },
  editorialCard: {
    backgroundColor: theme.colors.surface,
  },
  editorialTop: {
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  editorialTitleRow: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'center',
    flex: 1,
  },
  editorialText: {
    flex: 1,
  },
  editorialTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  editorialDesc: {
    marginTop: 4,
    lineHeight: 20,
  },
  customActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  modeCard: {
    width: '100%',
    minHeight: 166,
  },
  modeIconWrap: {
    width: 42,
    height: 42,
    borderRadius: theme.radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.surface,
  },
  modeTitle: {
    marginTop: 14,
    fontSize: 15,
    fontWeight: '600',
  },
  modeSummary: {
    marginTop: 8,
    lineHeight: 20,
    fontSize: 13,
  },
  list: {
    gap: 12,
  },
  listCard: {
    backgroundColor: theme.colors.surface,
  },
  listTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  listSummary: {
    marginTop: 8,
    lineHeight: 22,
  },
  listTime: {
    marginTop: 10,
    fontSize: 12,
  },
  catalogLink: {
    color: theme.colors.accent,
    fontWeight: '600',
  },
});
