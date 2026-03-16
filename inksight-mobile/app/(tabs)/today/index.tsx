import { useEffect, useMemo, useState } from 'react';
import { Alert, RefreshControl, StyleSheet, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { ModeCard } from '@/components/content/ModeCard';
import { ContentCardSkeleton } from '@/components/content/ContentCardSkeleton';
import { InkBottomSheet } from '@/components/ui/InkBottomSheet';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { getTodayContent, type TodayItem } from '@/features/content/api';
import { appendLocalHistory, getCachedTodayContent, setCachedTodayContent } from '@/features/content/storage';
import { listUserDevices, favoriteDeviceContent, pushPreviewToDevice, type DeviceSummary } from '@/features/device/api';
import { lightImpact, successFeedback } from '@/features/feedback/haptics';
import { shareTodayItem } from '@/features/sharing/share';
import { useFavoriteState } from '@/hooks/useFavoriteState';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

const modes = ['POETRY', 'DAILY', 'WEATHER'];

function variantFor(modeId: string): 'poetry' | 'daily' | 'weather' {
  if (modeId === 'POETRY') return 'poetry';
  if (modeId === 'WEATHER') return 'weather';
  return 'daily';
}

/* ── Per-item card wrapper (isolates hooks) ── */
function TodayItemCard({
  item,
  onOpenSheet,
  token,
  devices,
}: {
  item: TodayItem;
  onOpenSheet: (item: TodayItem, variant: 'detail' | 'actions') => void;
  token: string | null;
  devices: DeviceSummary[];
}) {
  const { t } = useI18n();
  const { isFavorite, favoriteScale, toggle } = useFavoriteState(item);

  async function handleToggle() {
    const result = await toggle();
    if (result?.active && token && devices[0]?.mac) {
      favoriteDeviceContent(devices[0].mac, token, item.mode_id).catch(() => undefined);
    }
  }

  return (
    <ModeCard
      item={item}
      variant={variantFor(item.mode_id)}
      favorite={isFavorite}
      favoriteScale={favoriteScale}
      onToggleFavorite={handleToggle}
      onShare={() => shareTodayItem(item, { sourceLabel: t('common.fromApp') })}
      onPress={() => onOpenSheet(item, 'detail')}
      onLongPress={() => onOpenSheet(item, 'actions')}
    />
  );
}

/* ── Main screen ── */
export default function TodayScreen() {
  const { locale, t } = useI18n();
  const showToast = useToast();
  const [cachedPayload, setCachedPayload] = useState<Awaited<ReturnType<typeof getCachedTodayContent>>>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [sheetVariant, setSheetVariant] = useState<'detail' | 'actions'>('detail');
  const [activeItem, setActiveItem] = useState<TodayItem | null>(null);
  const token = useAuthStore((state) => state.token);

  const query = useQuery({
    queryKey: ['today-content', modes],
    queryFn: () => getTodayContent(modes),
    staleTime: 30 * 60 * 1000,
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
  const items = payload?.items || [];

  // Record history for all items once loaded
  useEffect(() => {
    items.forEach((item) => appendLocalHistory(item).catch(() => undefined));
  }, [items]);

  const dateLabel = useMemo(
    () =>
      new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'zh-CN', {
        month: 'long',
        day: 'numeric',
        weekday: 'long',
      }).format(new Date()),
    [locale],
  );

  const lunarLabel = useMemo(() => {
    const d = payload?.date;
    if (!d) return '';
    const daily = typeof d.daily_word === 'string' ? d.daily_word : '';
    const holiday = typeof d.upcoming_holiday === 'string' && typeof d.days_until_holiday === 'number'
      ? `${d.upcoming_holiday}还有${d.days_until_holiday}天`
      : '';
    return [daily, holiday].filter(Boolean).join(' · ');
  }, [payload]);

  async function handleRefresh() {
    await lightImpact();
    await query.refetch();
    await successFeedback();
  }

  function openDetailSheet(item: TodayItem, variant: 'detail' | 'actions') {
    setActiveItem(item);
    setSheetVariant(variant);
    setSheetVisible(true);
  }

  /* ── Sheet actions (operate on activeItem) ── */
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
      if (devices.length === 0) { resolve(null); return; }
      if (devices.length === 1) { resolve(devices[0]); return; }
      Alert.alert(t('common.pushToDevice'), '', [
        ...devices.map((device) => ({
          text: device.nickname || device.mac,
          onPress: () => resolve(device),
        })),
        { text: t('common.cancel'), style: 'cancel' as const, onPress: () => resolve(null) },
      ]);
    });
  }

  async function handlePushToDevice() {
    if (!activeItem || !token) return;
    const devices = devicesQuery.data?.devices || [];
    const device = await pickDevice(devices);
    if (!device?.mac) {
      if (devices.length === 0) Alert.alert(t('today.deviceMissingTitle'), t('today.deviceMissing'));
      return;
    }
    try {
      await pushPreviewToDevice(device.mac, token, activeItem.preview_url, activeItem.mode_id);
      await successFeedback();
      Alert.alert(t('today.pushedTitle'), t('today.pushed', { title: activeItem.display_name, mac: device.mac }));
    } catch (error) {
      Alert.alert(t('today.pushFailed'), error instanceof Error ? error.message : t('today.pushFailed'));
    }
  }

  return (
    <>
      <AppScreen
        contentContainerStyle={styles.content}
        scroll
        header={
          <View>
            <InkText serif style={styles.title}>{t('today.title')}</InkText>
            <InkText dimmed style={styles.subtitle}>{dateLabel}</InkText>
            {lunarLabel ? <InkText dimmed style={styles.lunarLabel}>{lunarLabel}</InkText> : null}
          </View>
        }
        refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={handleRefresh} tintColor={theme.colors.ink} />}
      >

        {(query.isLoading || query.isRefetching) && items.length === 0 ? (
          <>
            <ContentCardSkeleton />
            <ContentCardSkeleton />
            <ContentCardSkeleton />
          </>
        ) : null}

        {items.map((todayItem) => (
          <TodayItemCard
            key={todayItem.mode_id}
            item={todayItem}
            onOpenSheet={openDetailSheet}
            token={token}
            devices={devicesQuery.data?.devices || []}
          />
        ))}

        {token ? (
          <InkButton
            label={t('common.pushToDevice')}
            block
            variant="secondary"
            onPress={() => {
              if (items[0]) {
                setActiveItem(items[0]);
                handlePushToDevice();
              }
            }}
            disabled={!devicesQuery.data?.devices?.length || items.length === 0}
          />
        ) : null}

        {cachedPayload && !query.data ? (
          <InkCard>
            <InkText style={styles.sectionTitle}>{t('today.offlineTitle')}</InkText>
            <InkText dimmed>{t('today.offlineBody')}</InkText>
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
            <InkText dimmed style={styles.detailText}>{t('today.detailMode', { mode: activeItem.mode_id })}</InkText>
            <InkText dimmed style={styles.detailText}>{t('today.detailSummary', { summary: activeItem.summary })}</InkText>
          </InkCard>
        ) : null}

        <View style={styles.sheetActions}>
          <InkButton label={t('common.share')} block onPress={handleSheetShare} />
          <InkButton label={t('common.copy')} block variant="secondary" onPress={handleSheetCopy} />
          {token ? <InkButton label={t('common.pushToDevice')} block variant="secondary" onPress={handlePushToDevice} /> : null}
          <InkButton label={t('common.close')} block variant="ghost" onPress={() => setSheetVisible(false)} />
        </View>
      </InkBottomSheet>
    </>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: theme.spacing.md,
  },
  title: {
    fontSize: 34,
  },
  subtitle: {
    marginTop: 4,
    fontSize: 14,
  },
  lunarLabel: {
    marginTop: 2,
    fontSize: 13,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  sheetTitle: {
    fontSize: 28,
    fontWeight: '600',
  },
  sheetBody: {
    lineHeight: 22,
  },
  sheetCard: {
    gap: 8,
  },
  detailText: {
    lineHeight: 22,
  },
  sheetActions: {
    gap: 10,
  },
});
