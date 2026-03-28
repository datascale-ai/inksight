import { type ComponentType, useEffect, useMemo, useState } from 'react';
import { Alert, Animated, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, Heart, Send, Share2, Sparkles } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { ModeIcon } from '@/components/content/ModeIcon';
import { ContentCardSkeleton } from '@/components/content/ContentCardSkeleton';
import { InkBottomSheet } from '@/components/ui/InkBottomSheet';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkText } from '@/components/ui/InkText';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { getTodayContent, type TodayHeaderMeta, type TodayItem } from '@/features/content/api';
import { appendLocalHistory, getCachedTodayContent, setCachedTodayContent } from '@/features/content/storage';
import { listUserDevices, favoriteDeviceContent, pushPreviewToDevice, type DeviceSummary } from '@/features/device/api';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';
import { shareTodayItem } from '@/features/sharing/share';
import { useFavoriteState } from '@/hooks/useFavoriteState';
import { useI18n, type I18nContextValue } from '@/lib/i18n';
import { localizeCatalogMode } from '@/lib/mode-display';
import { theme } from '@/lib/theme';

const fallbackModes = ['DAILY', 'WEATHER', 'POETRY'];

function tf(t: (key: string, vars?: Record<string, string | number>) => string, key: string, fallback: string, vars?: Record<string, string | number>) {
  const resolved = t(key, vars);
  return resolved === key ? fallback : resolved;
}

function firstText(value: unknown): string {
  if (typeof value === 'string') {
    return value.trim();
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const text = firstText(item);
      if (text) return text;
    }
  }
  if (value && typeof value === 'object') {
    for (const item of Object.values(value)) {
      const text = firstText(item);
      if (text) return text;
    }
  }
  return '';
}

function getItemDisplayName(item: TodayItem, locale: 'zh' | 'en') {
  return localizeCatalogMode({ mode_id: item.mode_id, display_name: item.display_name, description: '' }, locale).display_name;
}

function deriveItemTitle(item: TodayItem) {
  return (
    item.title ||
    firstText(item.content?.title) ||
    firstText(item.content?.event_title) ||
    firstText(item.content?.question) ||
    item.display_name
  );
}

function deriveRecommendation(item: TodayItem, headerMeta: TodayHeaderMeta, t: (key: string, vars?: Record<string, string | number>) => string) {
  if (item.recommendation_reason) {
    return item.recommendation_reason;
  }
  if (item.mode_id === 'WEATHER') {
    return `${headerMeta.weather_summary || deriveItemTitle(item)} ${headerMeta.season_label || ''}`.trim();
  }
  if (item.mode_id === 'POETRY') {
    return headerMeta.daily_keyword || tf(t, 'today.heroReasonFallback', 'A quiet line for today.');
  }
  return headerMeta.season_label || tf(t, 'today.heroReasonFallback', 'A thoughtful card worth opening today.');
}

function buildHeaderMeta(payload: Awaited<ReturnType<typeof getCachedTodayContent>>, locale: 'zh' | 'en'): TodayHeaderMeta {
  if (payload?.header_meta) {
    return payload.header_meta;
  }
  const date = payload?.date || {};
  const weather = payload?.weather || {};
  const formatter = new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });
  const dateLabel = formatter.format(new Date());
  const city = typeof weather.city === 'string' ? weather.city : '';
  const weatherSummary = [city, typeof weather.weather_str === 'string' ? weather.weather_str : '']
    .filter(Boolean)
    .join(' · ');
  const upcomingHoliday = typeof date.upcoming_holiday === 'string' ? date.upcoming_holiday : '';
  const daysUntilHoliday = typeof date.days_until_holiday === 'number' ? date.days_until_holiday : 0;
  const seasonLabel =
    upcomingHoliday && daysUntilHoliday > 0
      ? `${upcomingHoliday} ${locale === 'en' ? `in ${daysUntilHoliday} days` : `还有${daysUntilHoliday}天`}`
      : String(date.festival || date.month_cn || '');

  return {
    date_label: dateLabel,
    weather_summary: weatherSummary || '--',
    season_label: seasonLabel,
    daily_keyword: String(date.daily_word || ''),
  };
}

function ActionIconButton({
  icon,
  active = false,
  onPress,
}: {
  icon: ComponentType<{ size?: number; color?: string; strokeWidth?: number; fill?: string }>;
  active?: boolean;
  onPress: () => void;
}) {
  const Icon = icon;
  return (
    <Pressable onPress={onPress} style={[styles.iconButton, active ? styles.iconButtonActive : null]}>
      <Icon
        size={18}
        color={active ? theme.colors.accent : theme.colors.secondary}
        strokeWidth={theme.strokeWidth}
        fill={active ? theme.colors.accentSoft : 'transparent'}
      />
    </Pressable>
  );
}

function HeroActions({
  favorite,
  favoriteScale,
  onToggleFavorite,
  onShare,
  onPush,
}: {
  favorite: boolean;
  favoriteScale: Animated.Value;
  onToggleFavorite: () => void;
  onShare: () => void;
  onPush?: () => void;
}) {
  return (
    <View style={styles.heroActions}>
      <Pressable onPress={onToggleFavorite} style={[styles.iconButton, favorite ? styles.iconButtonActive : null]}>
        <Animated.View style={{ transform: [{ scale: favoriteScale }] }}>
          <Heart
            size={18}
            color={favorite ? theme.colors.accent : theme.colors.secondary}
            fill={favorite ? theme.colors.accentSoft : 'transparent'}
            strokeWidth={theme.strokeWidth}
          />
        </Animated.View>
      </Pressable>
      <ActionIconButton icon={Share2} onPress={onShare} />
      {onPush ? <ActionIconButton icon={Send} onPress={onPush} /> : null}
    </View>
  );
}

function TodayFeedCard({
  item,
  variant,
  token,
  devices,
  onOpenSheet,
  reason,
  locale,
  t,
}: {
  item: TodayItem;
  variant: 'hero' | 'secondary';
  token: string | null;
  devices: DeviceSummary[];
  onOpenSheet: (item: TodayItem, variant: 'detail' | 'actions') => void;
  reason: string;
  locale: I18nContextValue['locale'];
  t: I18nContextValue['t'];
}) {
  const { isFavorite, favoriteScale, toggle } = useFavoriteState(item);

  async function handleToggle() {
    const result = await toggle();
    if (result?.active && token && devices[0]?.mac) {
      favoriteDeviceContent(devices[0].mac, token, item.mode_id).catch(() => undefined);
    }
  }

  const sharedActions = {
    onToggleFavorite: handleToggle,
    onShare: () => shareTodayItem(item, { sourceLabel: tf(t, 'common.fromApp', 'From InkSight') }),
    onPush: token ? () => onOpenSheet(item, 'actions') : undefined,
  };
  const itemTitle = deriveItemTitle(item);

  if (variant === 'hero') {
    return (
      <InkCard style={styles.heroCard}>
        <View style={styles.heroTop}>
          <View style={styles.heroMeta}>
            <InkChip label={getItemDisplayName(item, locale)} active />
            <InkText dimmed style={styles.heroReason}>
              {reason}
            </InkText>
          </View>
          <HeroActions
            favorite={isFavorite}
            favoriteScale={favoriteScale}
            onToggleFavorite={sharedActions.onToggleFavorite}
            onShare={sharedActions.onShare}
            onPush={sharedActions.onPush}
          />
        </View>

        <Pressable onPress={() => onOpenSheet(item, 'detail')} onLongPress={() => onOpenSheet(item, 'actions')}>
          <InkText serif style={styles.heroSummary}>
            {item.summary || tf(t, 'today.summaryFallback', 'Keep one thing in view.')}
          </InkText>
          <View style={styles.heroFooter}>
            <View style={styles.heroFooterLeft}>
              <ModeIcon modeId={item.mode_id} color={theme.colors.brandInk} />
              <InkText style={styles.heroFooterLabel}>{itemTitle}</InkText>
            </View>
            <View style={styles.heroFooterRight}>
              <InkText dimmed style={styles.heroFooterLink}>{tf(t, 'today.heroOpen', 'Open')}</InkText>
              <ArrowRight size={16} color={theme.colors.accent} strokeWidth={theme.strokeWidth} />
            </View>
          </View>
        </Pressable>
      </InkCard>
    );
  }

  return (
    <InkCard style={styles.secondaryCard}>
      <Pressable onPress={() => onOpenSheet(item, 'detail')} onLongPress={() => onOpenSheet(item, 'actions')}>
        <View style={styles.secondaryHeader}>
          <View style={styles.secondaryTitleRow}>
            <ModeIcon modeId={item.mode_id} color={theme.colors.secondary} />
            <InkText style={styles.secondaryTitle}>{getItemDisplayName(item, locale)}</InkText>
          </View>
          <View style={styles.secondaryActions}>
            <HeroActions
              favorite={isFavorite}
              favoriteScale={favoriteScale}
              onToggleFavorite={sharedActions.onToggleFavorite}
              onShare={sharedActions.onShare}
              onPush={sharedActions.onPush}
            />
          </View>
        </View>
        <InkText serif style={styles.secondarySummary}>{item.summary || tf(t, 'today.summaryFallback', 'Keep one thing in view.')}</InkText>
        <InkText dimmed style={styles.secondaryReason}>{reason || itemTitle}</InkText>
      </Pressable>
    </InkCard>
  );
}

export default function TodayScreen() {
  const { locale, t } = useI18n();
  const showToast = useToast();
  const [cachedPayload, setCachedPayload] = useState<Awaited<ReturnType<typeof getCachedTodayContent>>>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [sheetVariant, setSheetVariant] = useState<'detail' | 'actions'>('detail');
  const [activeItem, setActiveItem] = useState<TodayItem | null>(null);
  const token = useAuthStore((state) => state.token);

  const query = useQuery({
    queryKey: ['today-content-v3'],
    queryFn: () => getTodayContent(fallbackModes),
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });
  const devicesQuery = useQuery({
    queryKey: ['today-devices', token],
    queryFn: () => listUserDevices(token || ''),
    enabled: Boolean(token),
  });

  useEffect(() => {
    getCachedTodayContent().then(setCachedPayload);
  }, []);

  useEffect(() => {
    if (query.data) {
      setCachedTodayContent(query.data).catch(() => undefined);
    }
  }, [query.data]);

  const payload = query.data || cachedPayload;
  const headerMeta = useMemo(() => buildHeaderMeta(payload, locale), [payload, locale]);
  const heroItem = payload?.hero_item || payload?.items?.[0] || null;
  const secondaryItems = (payload?.secondary_items?.length ? payload.secondary_items : payload?.items?.slice(1, 3)) || [];
  const renderedItems = [heroItem, ...secondaryItems].filter(Boolean) as TodayItem[];

  useEffect(() => {
    renderedItems.forEach((item) => appendLocalHistory(item).catch(() => undefined));
  }, [renderedItems]);

  async function handleRefresh() {
    await lightImpact();
    await query.refetch();
    await successFeedback();
  }

  function openSheet(item: TodayItem, variant: 'detail' | 'actions') {
    setActiveItem(item);
    setSheetVariant(variant);
    setSheetVisible(true);
  }

  async function handleSheetShare() {
    if (!activeItem) return;
    await lightImpact();
    await shareTodayItem(activeItem, { sourceLabel: tf(t, 'common.fromApp', 'From InkSight') });
  }

  async function handleSheetCopy() {
    if (!activeItem) return;
    await Clipboard.setStringAsync(activeItem.summary || '');
    showToast(tf(t, 'today.copied', 'Copied'), 'success');
  }

  function pickDevice(devices: DeviceSummary[]) {
    return new Promise<DeviceSummary | null>((resolve) => {
      if (devices.length === 0) {
        resolve(null);
        return;
      }
      if (devices.length === 1) {
        resolve(devices[0]);
        return;
      }
      Alert.alert(tf(t, 'common.pushToDevice', 'Push to device'), '', [
        ...devices.map((device) => ({
          text: device.nickname || device.mac,
          onPress: () => resolve(device),
        })),
        { text: tf(t, 'common.cancel', 'Cancel'), style: 'cancel' as const, onPress: () => resolve(null) },
      ]);
    });
  }

  async function handlePushToDevice(item = activeItem) {
    if (!item || !token) return;
    const devices = devicesQuery.data?.devices || [];
    const device = await pickDevice(devices);
    if (!device?.mac) {
      if (devices.length === 0) {
        Alert.alert(
          tf(t, 'today.deviceMissingTitle', 'No device available'),
          tf(t, 'today.deviceMissing', 'Sign in and bind at least one device first.'),
        );
      }
      return;
    }
    try {
      await pushPreviewToDevice(device.mac, token, item.preview_url, item.mode_id);
      await successFeedback();
      Alert.alert(
        tf(t, 'today.pushedTitle', 'Pushed'),
        tf(t, 'today.pushed', `${getItemDisplayName(item, locale)} pushed to ${device.mac}`, {
          title: getItemDisplayName(item, locale),
          mac: device.mac,
        }),
      );
    } catch (error) {
      Alert.alert(tf(t, 'today.pushFailed', 'Push failed'), error instanceof Error ? error.message : tf(t, 'today.pushFailed', 'Push failed'));
    }
  }

  return (
    <>
      <AppScreen
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={handleRefresh} tintColor={theme.colors.accent} />}
        header={
          <View>
            <InkText serif style={styles.title}>{tf(t, 'today.title', 'Today')}</InkText>
            <InkText dimmed style={styles.subtitle}>{tf(t, 'today.subtitle', 'Slow down and look at what is worth reading.')}</InkText>
          </View>
        }
      >
        <InkCard style={styles.heroHeaderCard}>
          <View style={styles.heroHeaderRow}>
            <Sparkles size={18} color={theme.colors.accent} strokeWidth={theme.strokeWidth} />
            <InkText style={styles.heroHeaderLabel}>{headerMeta.date_label}</InkText>
          </View>
          <View style={styles.heroMetaGrid}>
            <View style={styles.heroMetaCell}>
              <InkText dimmed style={styles.heroMetaCaption}>{tf(t, 'today.metaWeather', 'Weather')}</InkText>
              <InkText style={styles.heroMetaValue}>{headerMeta.weather_summary || '—'}</InkText>
            </View>
            <View style={styles.heroMetaCell}>
              <InkText dimmed style={styles.heroMetaCaption}>{tf(t, 'today.metaSeason', 'Season')}</InkText>
              <InkText style={styles.heroMetaValue}>{headerMeta.season_label || '—'}</InkText>
            </View>
            <View style={styles.heroMetaCell}>
              <InkText dimmed style={styles.heroMetaCaption}>{tf(t, 'today.metaKeyword', 'Keyword')}</InkText>
              <InkText style={styles.heroMetaValue}>{headerMeta.daily_keyword || '—'}</InkText>
            </View>
          </View>
        </InkCard>

        {(query.isLoading || query.isRefetching) && renderedItems.length === 0 ? (
          <>
            <ContentCardSkeleton />
            <ContentCardSkeleton />
            <ContentCardSkeleton />
          </>
        ) : null}

        {!query.isLoading && !heroItem && !cachedPayload && query.error ? (
          <InkCard style={styles.statusCard}>
            <InkText style={styles.statusTitle}>{tf(t, 'today.errorTitle', 'Unable to load today')}</InkText>
            <InkText dimmed style={styles.statusBody}>{tf(t, 'today.errorBody', 'The feed did not load. Try refreshing again.')}</InkText>
            <InkButton label={tf(t, 'common.refresh', 'Refresh')} block onPress={handleRefresh} style={styles.statusButton} />
          </InkCard>
        ) : null}

        {heroItem ? (
          <TodayFeedCard
            item={heroItem}
            variant="hero"
            token={token}
            devices={devicesQuery.data?.devices || []}
            onOpenSheet={openSheet}
            reason={deriveRecommendation(heroItem, headerMeta, t)}
            locale={locale}
            t={t}
          />
        ) : null}

        {secondaryItems.map((item) => (
          <TodayFeedCard
            key={`secondary-${item.mode_id}`}
            item={item}
            variant="secondary"
            token={token}
            devices={devicesQuery.data?.devices || []}
            onOpenSheet={openSheet}
            reason={deriveRecommendation(item, headerMeta, t)}
            locale={locale}
            t={t}
          />
        ))}

        {/* Removed: "Keep the flow moving" section per product requirement. */}

        {cachedPayload && !query.data ? (
          <InkCard style={styles.offlineCard}>
            <InkText style={styles.statusTitle}>{tf(t, 'today.offlineTitle', 'Offline content')}</InkText>
            <InkText dimmed style={styles.statusBody}>{tf(t, 'today.offlineBody', 'Showing the most recent cached feed until the network comes back.')}</InkText>
          </InkCard>
        ) : null}
      </AppScreen>

      <InkBottomSheet visible={sheetVisible} onClose={() => setSheetVisible(false)}>
        <InkText serif style={styles.sheetTitle}>
          {sheetVariant === 'actions'
            ? tf(t, 'today.actionsTitle', 'Actions')
            : tf(t, 'today.detailTitle', 'Detail')}
        </InkText>
        <InkText dimmed style={styles.sheetBody}>
          {sheetVariant === 'actions'
            ? tf(t, 'today.actionsBody', 'Share, copy, favorite, or push to your device.')
            : tf(t, 'today.detailSummary', `Summary: ${activeItem?.summary || '-'}`, { summary: activeItem?.summary || '-' })}
        </InkText>

        {activeItem ? (
          <InkCard style={styles.sheetCard}>
            <InkText style={styles.sheetMode}>{getItemDisplayName(activeItem, locale)}</InkText>
            <InkText dimmed style={styles.sheetText}>{deriveItemTitle(activeItem)}</InkText>
            <InkText dimmed style={styles.sheetText}>
              {deriveRecommendation(activeItem, headerMeta, t)}
            </InkText>
          </InkCard>
        ) : null}

        <View style={styles.sheetActions}>
          <InkButton label={tf(t, 'common.share', 'Share')} block onPress={handleSheetShare} />
          <InkButton label={tf(t, 'common.copy', 'Copy')} block variant="secondary" onPress={handleSheetCopy} />
          {token ? <InkButton label={tf(t, 'common.pushToDevice', 'Push to device')} block variant="secondary" onPress={() => handlePushToDevice()} /> : null}
          <InkButton label={tf(t, 'common.close', 'Close')} block variant="ghost" onPress={() => setSheetVisible(false)} />
        </View>
      </InkBottomSheet>
    </>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 14,
  },
  title: {
    fontSize: 28,
    fontWeight: '600',
  },
  subtitle: {
    marginTop: 4,
  },
  heroHeaderCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
  },
  heroHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  heroHeaderLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: theme.colors.brandInk,
  },
  heroMetaGrid: {
    marginTop: 14,
    gap: 10,
  },
  heroMetaCell: {
    gap: 4,
  },
  heroMetaCaption: {
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  heroMetaValue: {
    fontSize: 14,
    fontWeight: '600',
  },
  heroCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
  },
  heroTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 12,
  },
  heroMeta: {
    flex: 1,
    gap: 10,
  },
  heroReason: {
    lineHeight: 20,
  },
  heroActions: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
  },
  iconButton: {
    width: 36,
    height: 36,
    borderRadius: theme.radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.card,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  iconButtonActive: {
    backgroundColor: theme.colors.accentSoft,
    borderColor: theme.colors.heroBorder,
  },
  heroSummary: {
    marginTop: 18,
    fontSize: 29,
    lineHeight: 42,
    color: theme.colors.ink,
  },
  heroFooter: {
    marginTop: 18,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  heroFooterLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  heroFooterLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: theme.colors.brandInk,
  },
  heroFooterRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  heroFooterLink: {
    fontSize: 13,
  },
  secondaryCard: {
    backgroundColor: theme.colors.surface,
  },
  secondaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  secondaryTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flex: 1,
  },
  secondaryTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  secondaryActions: {
    marginLeft: 8,
  },
  secondarySummary: {
    marginTop: 12,
    fontSize: 20,
    lineHeight: 30,
  },
  secondaryReason: {
    marginTop: 10,
    lineHeight: 20,
  },
  statusCard: {
    backgroundColor: theme.colors.surface,
  },
  offlineCard: {
    backgroundColor: theme.colors.surface,
  },
  statusTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  statusBody: {
    marginTop: 8,
    lineHeight: 22,
  },
  statusButton: {
    marginTop: 14,
  },
  sheetTitle: {
    fontSize: 24,
    fontWeight: '600',
  },
  sheetBody: {
    lineHeight: 22,
  },
  sheetCard: {
    backgroundColor: theme.colors.hero,
    borderColor: theme.colors.heroBorder,
  },
  sheetMode: {
    fontSize: 16,
    fontWeight: '600',
  },
  sheetText: {
    marginTop: 8,
    lineHeight: 22,
  },
  sheetActions: {
    gap: 10,
  },
});
