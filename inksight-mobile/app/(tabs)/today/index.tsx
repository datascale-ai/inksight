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
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

const fallbackModes = ['DAILY', 'WEATHER', 'POETRY'];

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
}: {
  item: TodayItem;
  variant: 'hero' | 'secondary';
  token: string | null;
  devices: DeviceSummary[];
  onOpenSheet: (item: TodayItem, variant: 'detail' | 'actions') => void;
}) {
  const { t } = useI18n();
  const { isFavorite, favoriteScale, toggle } = useFavoriteState(item);

  async function handleToggle() {
    const result = await toggle();
    if (result?.active && token && devices[0]?.mac) {
      favoriteDeviceContent(devices[0].mac, token, item.mode_id).catch(() => undefined);
    }
  }

  const sharedActions = {
    onToggleFavorite: handleToggle,
    onShare: () => shareTodayItem(item, { sourceLabel: t('common.fromApp') }),
    onPush: token ? () => onOpenSheet(item, 'actions') : undefined,
  };

  if (variant === 'hero') {
    return (
      <InkCard style={styles.heroCard}>
        <View style={styles.heroTop}>
          <View style={styles.heroMeta}>
            <InkChip label={item.display_name} active />
            <InkText dimmed style={styles.heroReason}>
              {item.recommendation_reason || t('today.heroReasonFallback')}
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
            {item.summary || t('today.summaryFallback')}
          </InkText>
          <View style={styles.heroFooter}>
            <View style={styles.heroFooterLeft}>
              <ModeIcon modeId={item.mode_id} color={theme.colors.brandInk} />
              <InkText style={styles.heroFooterLabel}>{item.title || item.display_name}</InkText>
            </View>
            <View style={styles.heroFooterRight}>
              <InkText dimmed style={styles.heroFooterLink}>{t('today.heroOpen')}</InkText>
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
            <InkText style={styles.secondaryTitle}>{item.display_name}</InkText>
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
        <InkText serif style={styles.secondarySummary}>{item.summary || t('today.summaryFallback')}</InkText>
        <InkText dimmed style={styles.secondaryReason}>
          {item.recommendation_reason || item.title || item.display_name}
        </InkText>
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
    queryKey: ['today-content-v2'],
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
  const headerMeta = useMemo<TodayHeaderMeta>(
    () =>
      payload?.header_meta || {
        date_label: new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'zh-CN', {
          month: 'long',
          day: 'numeric',
          weekday: 'long',
        }).format(new Date()),
        weather_summary: payload?.weather?.weather_str || '--°C',
        season_label: String(payload?.date?.festival || payload?.date?.upcoming_holiday || ''),
        daily_keyword: String(payload?.date?.daily_word || ''),
      },
    [payload, locale],
  );

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
    await shareTodayItem(activeItem, { sourceLabel: t('common.fromApp') });
  }

  async function handleSheetCopy() {
    if (!activeItem) return;
    await Clipboard.setStringAsync(activeItem.summary || '');
    showToast(t('today.copied'), 'success');
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
      Alert.alert(t('common.pushToDevice'), '', [
        ...devices.map((device) => ({
          text: device.nickname || device.mac,
          onPress: () => resolve(device),
        })),
        { text: t('common.cancel'), style: 'cancel' as const, onPress: () => resolve(null) },
      ]);
    });
  }

  async function handlePushToDevice(item = activeItem) {
    if (!item || !token) return;
    const devices = devicesQuery.data?.devices || [];
    const device = await pickDevice(devices);
    if (!device?.mac) {
      if (devices.length === 0) {
        Alert.alert(t('today.deviceMissingTitle'), t('today.deviceMissing'));
      }
      return;
    }
    try {
      await pushPreviewToDevice(device.mac, token, item.preview_url, item.mode_id);
      await successFeedback();
      Alert.alert(t('today.pushedTitle'), t('today.pushed', { title: item.display_name, mac: device.mac }));
    } catch (error) {
      Alert.alert(t('today.pushFailed'), error instanceof Error ? error.message : t('today.pushFailed'));
    }
  }

  return (
    <>
      <AppScreen
        contentContainerStyle={styles.content}
        header={
          <View>
            <InkText serif style={styles.title}>{t('today.title')}</InkText>
            <InkText dimmed style={styles.subtitle}>{t('today.subtitle')}</InkText>
          </View>
        }
        refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={handleRefresh} tintColor={theme.colors.accent} />}
      >
        <InkCard style={styles.heroHeaderCard}>
          <View style={styles.heroHeaderRow}>
            <Sparkles size={18} color={theme.colors.accent} strokeWidth={theme.strokeWidth} />
            <InkText style={styles.heroHeaderLabel}>{headerMeta.date_label}</InkText>
          </View>
          <View style={styles.heroMetaGrid}>
            <View style={styles.heroMetaCell}>
              <InkText dimmed style={styles.heroMetaCaption}>{t('today.metaWeather')}</InkText>
              <InkText style={styles.heroMetaValue}>{headerMeta.weather_summary}</InkText>
            </View>
            <View style={styles.heroMetaCell}>
              <InkText dimmed style={styles.heroMetaCaption}>{t('today.metaSeason')}</InkText>
              <InkText style={styles.heroMetaValue}>{headerMeta.season_label || '—'}</InkText>
            </View>
            <View style={styles.heroMetaCell}>
              <InkText dimmed style={styles.heroMetaCaption}>{t('today.metaKeyword')}</InkText>
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
            <InkText style={styles.statusTitle}>{t('today.errorTitle')}</InkText>
            <InkText dimmed style={styles.statusBody}>{t('today.errorBody')}</InkText>
            <InkButton label={t('common.refresh')} block onPress={handleRefresh} style={styles.statusButton} />
          </InkCard>
        ) : null}

        {heroItem ? (
          <TodayFeedCard
            item={heroItem}
            variant="hero"
            token={token}
            devices={devicesQuery.data?.devices || []}
            onOpenSheet={openSheet}
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
          />
        ))}

        <InkCard style={styles.actionCard}>
          <InkText style={styles.actionTitle}>{t('today.actionTitle')}</InkText>
          <InkText dimmed style={styles.actionBody}>{t('today.actionBody')}</InkText>
          <View style={styles.actionStack}>
            {token ? (
              <InkButton
                label={t('today.pushPrimary')}
                block
                onPress={() => handlePushToDevice(heroItem)}
                disabled={!heroItem || !devicesQuery.data?.devices?.length}
              />
            ) : null}
            <InkButton
              label={t('today.openBrowse')}
              block
              variant="secondary"
              onPress={() => router.push('/browse')}
            />
          </View>
        </InkCard>

        {cachedPayload && !query.data ? (
          <InkCard style={styles.offlineCard}>
            <InkText style={styles.statusTitle}>{t('today.offlineTitle')}</InkText>
            <InkText dimmed style={styles.statusBody}>{t('today.offlineBody')}</InkText>
          </InkCard>
        ) : null}
      </AppScreen>

      <InkBottomSheet visible={sheetVisible} onClose={() => setSheetVisible(false)}>
        <InkText serif style={styles.sheetTitle}>
          {sheetVariant === 'actions' ? t('today.actionsTitle') : t('today.detailTitle')}
        </InkText>
        <InkText dimmed style={styles.sheetBody}>
          {sheetVariant === 'actions'
            ? t('today.actionsBody')
            : t('today.detailSummary', { summary: activeItem?.summary || '-' })}
        </InkText>

        {activeItem ? (
          <InkCard style={styles.sheetCard}>
            <InkText style={styles.sheetMode}>{activeItem.display_name}</InkText>
            {activeItem.title ? <InkText dimmed style={styles.sheetText}>{activeItem.title}</InkText> : null}
            <InkText dimmed style={styles.sheetText}>{activeItem.recommendation_reason || activeItem.summary}</InkText>
          </InkCard>
        ) : null}

        <View style={styles.sheetActions}>
          <InkButton label={t('common.share')} block onPress={handleSheetShare} />
          <InkButton label={t('common.copy')} block variant="secondary" onPress={handleSheetCopy} />
          {token ? <InkButton label={t('common.pushToDevice')} block variant="secondary" onPress={() => handlePushToDevice()} /> : null}
          <InkButton label={t('common.close')} block variant="ghost" onPress={() => setSheetVisible(false)} />
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
    backgroundColor: '#FFFCF7',
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
  actionCard: {
    backgroundColor: '#FFF8EF',
  },
  actionTitle: {
    fontSize: 17,
    fontWeight: '600',
  },
  actionBody: {
    marginTop: 8,
    lineHeight: 21,
  },
  actionStack: {
    gap: 10,
    marginTop: 14,
  },
  statusCard: {
    backgroundColor: '#FFF7F3',
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
