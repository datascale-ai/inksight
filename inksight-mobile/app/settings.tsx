import { useEffect, useState } from 'react';
import { Alert, Pressable, StyleSheet, Switch, View } from 'react-native';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkBottomSheet } from '@/components/ui/InkBottomSheet';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkChip } from '@/components/ui/InkChip';
import { InkText } from '@/components/ui/InkText';
import { useAuthStore } from '@/features/auth/store';
import { getCachedTodayContent } from '@/features/content/storage';
import { listModes } from '@/features/modes/api';
import { syncLocalDailyNotification } from '@/features/notifications/local';
import { getStoredNotificationStatus, registerPushNotifications, unregisterPushNotifications } from '@/features/notifications/api';
import { getPreferences, updatePreferences } from '@/features/preferences/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

const HOURS = ['06:00', '07:00', '08:00', '09:00', '10:00', '12:00', '18:00', '20:00'];

export default function SettingsScreen() {
  const { locale: activeLocale, setLocale: saveLocale, t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [picker, setPicker] = useState<'time' | 'widget' | null>(null);
  const query = useQuery({
    queryKey: ['preferences', token],
    queryFn: () => getPreferences(token || ''),
    enabled: Boolean(token),
  });
  const modesQuery = useQuery({
    queryKey: ['settings-modes'],
    queryFn: listModes,
  });

  const prefs = query.data;
  const [pushEnabled, setPushEnabled] = useState(false);
  const [pushTime, setPushTime] = useState('08:00');
  const [widgetMode, setWidgetMode] = useState('STOIC');
  const [locale, setLocaleState] = useState<'zh' | 'en'>('zh');
  const [pushModes, setPushModes] = useState<string[]>(['DAILY']);
  const [pushTokenLabel, setPushTokenLabel] = useState('');

  useEffect(() => {
    if (!prefs) return;
    setPushEnabled(prefs.push_enabled);
    setPushTime(prefs.push_time);
    setWidgetMode(prefs.widget_mode);
    setLocaleState((prefs.locale as 'zh' | 'en') || activeLocale);
    setPushModes(prefs.push_modes);
  }, [prefs, activeLocale]);

  useEffect(() => {
    getStoredNotificationStatus().then((record) => {
      setPushTokenLabel(record?.push_token ? t('settings.registered', { platform: record.platform }) : t('settings.unregistered'));
    });
  }, [t]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const result = await updatePreferences(token || '', {
        push_enabled: pushEnabled,
        push_time: pushTime,
        widget_mode: widgetMode.toUpperCase(),
        push_modes: pushModes,
        locale,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || prefs?.timezone || 'Asia/Shanghai',
      });
      if (pushEnabled) {
        await registerPushNotifications(token || '', pushTime);
      } else {
        await unregisterPushNotifications(token || '');
      }
      const cachedToday = await getCachedTodayContent();
      const preferredItem =
        cachedToday?.items.find((item) => pushModes.includes(item.mode_id)) ||
        cachedToday?.items[0] ||
        null;
      await syncLocalDailyNotification({
        enabled: pushEnabled,
        pushTime,
        item: preferredItem,
        title: t('settings.notificationTitle'),
        body: t('settings.notificationBody'),
      });
      await saveLocale(locale);
      return result;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences', token] });
      getStoredNotificationStatus().then((record) => {
        setPushTokenLabel(record?.push_token ? t('settings.registered', { platform: record.platform }) : t('settings.unregistered'));
      });
      Alert.alert(t('common.saved'), t('settings.savedBody'));
    },
    onError: (error) => Alert.alert(t('settings.saveFailed'), error instanceof Error ? error.message : t('settings.saveFailed')),
  });

  function togglePushMode(modeId: string) {
    setPushModes((current) => (current.includes(modeId) ? current.filter((item) => item !== modeId) : [...current, modeId]));
  }

  return (
    <>
      <AppScreen>
        <InkText serif style={styles.title}>{t('settings.title')}</InkText>
        <InkText dimmed>{t('settings.subtitle')}</InkText>

        <InkCard style={styles.sectionCard}>
          <InkText style={styles.sectionTitle}>{t('settings.notifications')}</InkText>
          <View style={styles.row}>
            <View style={styles.rowText}>
              <InkText style={styles.rowTitle}>{t('settings.enablePush')}</InkText>
              <InkText dimmed>{t('settings.registration', { status: pushTokenLabel })}</InkText>
            </View>
            <Switch value={pushEnabled} onValueChange={setPushEnabled} />
          </View>
          <Pressable style={styles.selectionCard} onPress={() => setPicker('time')}>
            <InkText dimmed>{t('settings.pushTimeLabel')}</InkText>
            <InkText style={styles.selectionValue}>{pushTime}</InkText>
          </Pressable>
          <View style={styles.modeWrap}>
            {(modesQuery.data?.modes || []).slice(0, 8).map((mode) => (
              <InkChip
                key={mode.mode_id}
                label={mode.display_name}
                active={pushModes.includes(mode.mode_id)}
                onPress={() => togglePushMode(mode.mode_id)}
              />
            ))}
          </View>
        </InkCard>

        <InkCard style={styles.sectionCard}>
          <InkText style={styles.sectionTitle}>{t('settings.widgetAndLocale')}</InkText>
          <Pressable style={styles.selectionCard} onPress={() => setPicker('widget')}>
            <InkText dimmed>{t('settings.widgetModeLabel')}</InkText>
            <InkText style={styles.selectionValue}>{widgetMode}</InkText>
          </Pressable>
          <View style={styles.modeWrap}>
            <InkChip label="ZH" active={locale === 'zh'} onPress={() => setLocaleState('zh')} />
            <InkChip label="EN" active={locale === 'en'} onPress={() => setLocaleState('en')} />
          </View>
          <InkText dimmed style={styles.helperText}>
            {prefs ? t('settings.localeTimezone', { locale, timezone: prefs.timezone }) : t('settings.notLoggedIn')}
          </InkText>
        </InkCard>

        <InkCard style={styles.sectionCard}>
          <InkText style={styles.sectionTitle}>{t('settings.aboutTitle')}</InkText>
          <InkText dimmed style={styles.helperText}>{t('settings.aboutBody')}</InkText>
        </InkCard>

        <InkButton
          label={saveMutation.isPending ? t('common.loading') : t('common.save')}
          block
          onPress={() => saveMutation.mutate()}
          disabled={!token || saveMutation.isPending}
        />
      </AppScreen>

      <InkBottomSheet visible={picker !== null} onClose={() => setPicker(null)}>
        <InkText serif style={styles.sheetTitle}>
          {picker === 'time' ? t('settings.pushTimeLabel') : t('settings.widgetModeLabel')}
        </InkText>
        <View style={styles.sheetOptions}>
          {picker === 'time'
            ? HOURS.map((time) => (
                <InkButton
                  key={time}
                  label={time}
                  block
                  variant={pushTime === time ? 'primary' : 'secondary'}
                  onPress={() => {
                    setPushTime(time);
                    setPicker(null);
                  }}
                />
              ))
            : (modesQuery.data?.modes || []).slice(0, 10).map((mode) => (
                <InkButton
                  key={mode.mode_id}
                  label={mode.display_name}
                  block
                  variant={widgetMode === mode.mode_id ? 'primary' : 'secondary'}
                  onPress={() => {
                    setWidgetMode(mode.mode_id);
                    setPicker(null);
                  }}
                />
              ))}
        </View>
      </InkBottomSheet>
    </>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 28,
    fontWeight: '600',
  },
  sectionCard: {
    gap: 14,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  rowText: {
    flex: 1,
    gap: 4,
  },
  rowTitle: {
    fontSize: 15,
    fontWeight: '600',
  },
  selectionCard: {
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 6,
  },
  selectionValue: {
    fontSize: 16,
    fontWeight: '600',
  },
  modeWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  helperText: {
    lineHeight: 21,
  },
  sheetTitle: {
    fontSize: 24,
    fontWeight: '600',
  },
  sheetOptions: {
    gap: 10,
  },
});
