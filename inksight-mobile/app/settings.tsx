import { useEffect, useState } from 'react';
import { Alert, StyleSheet, Switch, TextInput, View } from 'react-native';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { getCachedTodayContent } from '@/features/content/storage';
import { useI18n } from '@/lib/i18n';
import { listModes } from '@/features/modes/api';
import { syncLocalDailyNotification } from '@/features/notifications/local';
import { getStoredNotificationStatus, registerPushNotifications, unregisterPushNotifications } from '@/features/notifications/api';
import { getPreferences, updatePreferences } from '@/features/preferences/api';
import { theme } from '@/lib/theme';

export default function SettingsScreen() {
  const { locale: activeLocale, setLocale: saveLocale, t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
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
  }, [prefs]);

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
    <AppScreen>
      <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>{t('settings.title')}</InkText>
      <InkText dimmed>{t('settings.subtitle')}</InkText>

      <InkCard>
        <InkText style={{ fontWeight: '600', fontSize: 16 }}>{t('settings.notifications')}</InkText>
        <View style={styles.row}>
          <InkText dimmed>{t('settings.enablePush')}</InkText>
          <Switch value={pushEnabled} onValueChange={setPushEnabled} />
        </View>
        <TextInput value={pushTime} onChangeText={setPushTime} style={styles.input} />
        <InkText dimmed>
          {prefs ? t('settings.currentModes', { modes: pushModes.join(', ') || '-' }) : t('settings.notLoggedIn')}
        </InkText>
        <InkText dimmed style={{ marginTop: 8 }}>{t('settings.registration', { status: pushTokenLabel })}</InkText>
      </InkCard>

      <InkCard>
        <InkText style={{ fontWeight: '600', fontSize: 16 }}>{t('settings.pushModes')}</InkText>
        <View style={styles.modeWrap}>
          {(modesQuery.data?.modes || []).slice(0, 8).map((mode) => {
            const active = pushModes.includes(mode.mode_id);
            return (
              <InkButton
                key={mode.mode_id}
                label={mode.mode_id}
                variant={active ? 'primary' : 'secondary'}
                onPress={() => togglePushMode(mode.mode_id)}
              />
            );
          })}
        </View>
      </InkCard>

      <InkCard>
        <InkText style={{ fontWeight: '600', fontSize: 16 }}>{t('settings.widgetAndLocale')}</InkText>
        <TextInput value={widgetMode} onChangeText={setWidgetMode} style={styles.input} autoCapitalize="characters" />
        <View style={styles.modeWrap}>
          <InkButton label="ZH" variant={locale === 'zh' ? 'primary' : 'secondary'} onPress={() => setLocaleState('zh')} />
          <InkButton label="EN" variant={locale === 'en' ? 'primary' : 'secondary'} onPress={() => setLocaleState('en')} />
        </View>
        <InkText dimmed style={{ marginTop: 8 }}>
          {prefs ? t('settings.localeTimezone', { locale, timezone: prefs.timezone }) : t('settings.notLoggedIn')}
        </InkText>
      </InkCard>

      <InkButton
        label={saveMutation.isPending ? t('common.loading') : t('common.save')}
        block
        onPress={() => saveMutation.mutate()}
        disabled={!token || saveMutation.isPending}
      />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    marginBottom: 12,
  },
  input: {
    height: 50,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 16,
    marginVertical: 12,
    color: theme.colors.ink,
  },
  modeWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginTop: 12,
  },
});
