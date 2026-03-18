import { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, useWindowDimensions, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Heart, Layers, Sparkles } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkEmptyState } from '@/components/ui/InkEmptyState';
import { InkText } from '@/components/ui/InkText';
import { ModeIcon } from '@/components/content/ModeIcon';
import { useAuthStore } from '@/features/auth/store';
import { getLocalFavorites } from '@/features/content/storage';
import { getDiscoverFeed } from '@/features/discover/api';
import { listUserDevices, getDeviceFavorites } from '@/features/device/api';
import { listModes } from '@/features/modes/api';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

const segments = ['recommended', 'modes', 'favorites'] as const;

type BrowseFavoriteItem = {
  title: string;
  summary: string;
  time: string;
};

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={styles.sectionHeader}>
      <InkText style={styles.sectionTitle}>{title}</InkText>
      {subtitle ? <InkText dimmed style={styles.sectionSubtitle}>{subtitle}</InkText> : null}
    </View>
  );
}

export default function BrowseScreen() {
  const { t } = useI18n();
  const { width: screenWidth } = useWindowDimensions();
  const GAP = 12;
  const PADDING = theme.spacing.lg;
  const cardWidth = (screenWidth - PADDING * 2 - GAP) / 2;
  const [segment, setSegment] = useState<(typeof segments)[number]>('recommended');
  const [localFavorites, setLocalFavorites] = useState<BrowseFavoriteItem[]>([]);
  const token = useAuthStore((state) => state.token);

  const discoverQuery = useQuery({
    queryKey: ['discover-feed'],
    queryFn: getDiscoverFeed,
    staleTime: 10 * 60 * 1000,
  });
  const modesQuery = useQuery({
    queryKey: ['mode-catalog-v2'],
    queryFn: listModes,
  });
  const devicesQuery = useQuery({
    queryKey: ['browse-devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });
  const activeMac = devicesQuery.data?.devices?.[0]?.mac;
  const favoritesQuery = useQuery({
    queryKey: ['device-favorites', activeMac, token],
    queryFn: () => getDeviceFavorites(activeMac || '', token || ''),
    enabled: Boolean(activeMac && token),
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    getLocalFavorites().then((items) =>
      setLocalFavorites(
        items.map((item) => ({
          title: item.display_name,
          summary: item.summary,
          time: item.saved_at,
        })),
      ),
    );
  }, [segment]);

  const favoriteItems = useMemo(() => {
    if (!token) return localFavorites;
    return (favoritesQuery.data?.favorites || []).map((item) => ({
      title: String(item.mode_id || ''),
      summary: String(item.content?.text || item.content?.quote || item.content?.summary || t('browse.favoriteFallback')),
      time: item.time,
    }));
  }, [token, localFavorites, favoritesQuery.data, t]);

  const isRefreshing =
    discoverQuery.isRefetching ||
    modesQuery.isRefetching ||
    favoritesQuery.isRefetching;

  const handleRefresh = useCallback(async () => {
    await lightImpact();
    if (segment === 'recommended') {
      await discoverQuery.refetch();
    } else if (segment === 'modes') {
      await modesQuery.refetch();
    } else if (token) {
      await favoritesQuery.refetch();
    } else {
      getLocalFavorites().then((items) =>
        setLocalFavorites(
          items.map((item) => ({
            title: item.display_name,
            summary: item.summary,
            time: item.saved_at,
          })),
        ),
      );
    }
    await successFeedback();
  }, [segment, discoverQuery, modesQuery, favoritesQuery, token]);

  return (
    <AppScreen
      refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={handleRefresh} tintColor={theme.colors.accent} />}
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
            <Pressable
              key={item}
              onPress={() => setSegment(item)}
              style={[styles.segmentButton, selected ? styles.segmentSelected : null]}
            >
              <InkText style={selected ? styles.segmentTextSelected : styles.segmentText}>
                {t(`browse.segment.${item}`)}
              </InkText>
            </Pressable>
          );
        })}
      </View>

      {segment === 'recommended' ? (
        <>
          <InkCard style={styles.recommendIntroCard}>
            <View style={styles.recommendIntroRow}>
              <Sparkles size={18} color={theme.colors.accent} strokeWidth={theme.strokeWidth} />
              <InkText style={styles.recommendIntroTitle}>{t('browse.recommendIntroTitle')}</InkText>
            </View>
            <InkText dimmed style={styles.recommendIntroBody}>{t('browse.recommendIntroBody')}</InkText>
            <View style={styles.chipsRow}>
              {(discoverQuery.data?.scene_chips || []).map((chip) => (
                <InkChip key={chip.id} label={chip.label} />
              ))}
            </View>
          </InkCard>

          {(discoverQuery.data?.editorial_sections || []).map((section) => (
            <View key={section.id} style={styles.sectionBlock}>
              <SectionHeader title={section.title} subtitle={section.subtitle} />
              {section.items.map((item) => (
                <Pressable
                  key={`${section.id}-${item.mode_id}`}
                  onPress={() =>
                    router.push(
                      `/browse/${encodeURIComponent(item.mode_id)}?kind=mode&title=${encodeURIComponent(item.display_name)}&summary=${encodeURIComponent(item.description || item.display_name)}`,
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
                          <InkText style={styles.editorialTitle}>{item.display_name}</InkText>
                          <InkText dimmed style={styles.editorialDesc}>
                            {item.description || item.mode_id}
                          </InkText>
                        </View>
                      </View>
                      {item.badge ? <InkChip label={item.badge} active /> : null}
                    </View>
                  </InkCard>
                </Pressable>
              ))}
            </View>
          ))}

          <View style={styles.sectionBlock}>
            <SectionHeader title={t('browse.featuredModes')} subtitle={t('browse.featuredModesDesc')} />
            <View style={styles.grid}>
              {(discoverQuery.data?.featured_modes || []).map((mode) => (
                <Pressable
                  key={`featured-${mode.mode_id}`}
                  style={{ width: cardWidth }}
                  onPress={() =>
                    router.push(
                      `/browse/${encodeURIComponent(mode.mode_id)}?kind=mode&title=${encodeURIComponent(mode.display_name)}&summary=${encodeURIComponent(mode.description || mode.display_name)}`,
                    )
                  }
                >
                  <InkCard style={styles.modeCard}>
                    <View style={styles.modeIconWrap}>
                      <ModeIcon modeId={mode.mode_id} />
                    </View>
                    <InkText style={styles.modeTitle}>{mode.display_name}</InkText>
                    <InkText dimmed style={styles.modeSummary}>{mode.description || mode.mode_id}</InkText>
                  </InkCard>
                </Pressable>
              ))}
            </View>
          </View>

          {(discoverQuery.data?.cta_links || []).map((item) => (
            <InkCard key={item.id}>
              <InkText style={styles.listTitle}>{item.title}</InkText>
              <InkText dimmed style={styles.listSummary}>{item.description}</InkText>
              <Pressable onPress={() => router.push(item.route as never)}>
                <InkText style={styles.catalogLink}>{t('browse.moreModesLink')}</InkText>
              </Pressable>
            </InkCard>
          ))}
        </>
      ) : null}

      {segment === 'modes' ? (
        <View style={styles.grid}>
          {(modesQuery.data?.modes || []).map((mode) => (
            <Pressable
              key={mode.mode_id}
              style={{ width: cardWidth }}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(mode.mode_id)}?kind=mode&title=${encodeURIComponent(mode.display_name)}&summary=${encodeURIComponent(mode.description || mode.display_name)}`,
                )
              }
            >
              <InkCard style={styles.modeCard}>
                <View style={styles.modeIconWrap}>
                  <ModeIcon modeId={mode.mode_id} />
                </View>
                <InkText style={styles.modeTitle}>{mode.display_name}</InkText>
                <InkText dimmed style={styles.modeSummary}>{mode.description || mode.mode_id}</InkText>
              </InkCard>
            </Pressable>
          ))}
        </View>
      ) : null}

      {segment === 'favorites' ? (
        <View style={styles.list}>
          {!token ? (
            <InkCard>
              <InkText dimmed>{t('browse.localFallback')}</InkText>
            </InkCard>
          ) : null}
          {favoriteItems.length === 0 ? (
            <InkEmptyState
              icon={Heart}
              title={t('browse.emptyFavorites')}
              subtitle={t('browse.emptyFavoritesDesc')}
            />
          ) : null}
          {favoriteItems.map((item) => (
            <Pressable
              key={`${item.title}-${item.time}`}
              onPress={() =>
                router.push(
                  `/browse/${encodeURIComponent(item.title)}?kind=content&segment=${encodeURIComponent('favorites')}&title=${encodeURIComponent(item.title)}&summary=${encodeURIComponent(item.summary)}&time=${encodeURIComponent(item.time)}`,
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

      {segment === 'modes' && !(modesQuery.data?.modes || []).length ? (
        <InkEmptyState icon={Layers} title={t('browse.emptyModes')} subtitle={t('browse.emptyModesDesc')} />
      ) : null}
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
    backgroundColor: theme.colors.surface,
    borderRadius: 16,
    padding: 4,
    borderWidth: 1,
    borderColor: theme.colors.border,
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
    color: theme.colors.brandInk,
  },
  recommendIntroCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
  },
  recommendIntroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  recommendIntroTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: theme.colors.brandInk,
  },
  recommendIntroBody: {
    marginTop: 8,
    lineHeight: 22,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 14,
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
    backgroundColor: '#FFFCF7',
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
    backgroundColor: '#FFFCF7',
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
    marginTop: 12,
    color: theme.colors.accent,
    fontWeight: '600',
  },
  favoriteFallback: {
    color: theme.colors.secondary,
  },
});
