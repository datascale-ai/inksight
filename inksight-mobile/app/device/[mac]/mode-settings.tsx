import { useEffect, useState } from 'react';
import { Alert, Image, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as ImagePicker from 'expo-image-picker';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useToast } from '@/components/ui/InkToastProvider';
import { useAuthStore } from '@/features/auth/store';
import { getDeviceConfig, saveDeviceConfig, uploadImage } from '@/features/device/api';
import { listModes, type ModeCatalogItem } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { modeDisplayName } from '@/lib/mode-display';
import { theme } from '@/lib/theme';

type CountdownEvent = { name: string; date: string; type?: string };
type Reminder = { month: string; day: string; text: string };
type VocabDeck = { id: string; labelKey: string; fallback: string };

const DEFAULT_PERIODS = ['08:00-09:30', '10:00-11:30', '14:00-15:30', '16:00-17:30'];
const DEFAULT_COURSES: Record<string, string> = {
  '0-0': '高等数学/A201', '0-2': '线性代数/A201',
  '1-1': '大学英语/B305', '1-3': '体育/操场',
  '2-0': '数据结构/C102', '2-2': '计算机网络/C102',
  '3-1': '概率论/A201', '3-3': '毛概/D405',
  '4-0': '操作系统/C102',
};
const WEEKDAYS = 5;
const DEFAULT_VOCAB_DECK_ID = 'primary_en';
const DEFAULT_VOCAB_DAILY_LIMIT = 30;
const VOCAB_DECKS: VocabDeck[] = [
  { id: 'primary_en', labelKey: 'ms.vocabDeckPrimary', fallback: 'Primary English' },
  { id: 'middle_school_en', labelKey: 'ms.vocabDeckMiddle', fallback: 'Middle School English' },
  { id: 'high_school_en', labelKey: 'ms.vocabDeckHigh', fallback: 'High School English' },
  { id: 'cet4_en', labelKey: 'ms.vocabDeckCet4', fallback: 'CET-4' },
  { id: 'cet6_en', labelKey: 'ms.vocabDeckCet6', fallback: 'CET-6' },
  { id: 'ielts_en', labelKey: 'ms.vocabDeckIelts', fallback: 'IELTS' },
  { id: 'toefl_en', labelKey: 'ms.vocabDeckToefl', fallback: 'TOEFL' },
  { id: 'core_en', labelKey: 'ms.vocabDeckCore', fallback: 'Core English' },
];

function clampVocabDailyLimit(raw: string) {
  const parsed = parseInt(raw, 10);
  if (Number.isNaN(parsed)) return DEFAULT_VOCAB_DAILY_LIMIT;
  return Math.max(1, Math.min(200, parsed));
}

export default function ModeSettingsScreen() {
  const { locale, t } = useI18n();
  const params = useLocalSearchParams<{ mac: string; mode: string }>();
  const mac = params.mac;
  const modeId = (params.mode || '').toUpperCase();
  const token = useAuthStore((s) => s.token);
  const showToast = useToast();
  const queryClient = useQueryClient();

  const configQuery = useQuery({
    queryKey: ['device-config-ms', mac, token],
    queryFn: () => getDeviceConfig(mac || '', token || ''),
    enabled: Boolean(mac && token),
  });
  const modesQuery = useQuery({
    queryKey: ['mode-catalog-ms'],
    queryFn: () => listModes({ token: token || undefined, mac: mac || undefined }),
  });

  const existing = configQuery.data?.modeOverrides?.[modeId] ?? {};

  // --- WEATHER ---
  const [city, setCity] = useState('');
  const [forecastDays, setForecastDays] = useState('3');

  // --- MEMO ---
  const [memoText, setMemoText] = useState('');

  // --- COUNTDOWN ---
  const [countdownEvents, setCountdownEvents] = useState<CountdownEvent[]>([]);

  // --- CALENDAR ---
  const [reminders, setReminders] = useState<Reminder[]>([]);

  // --- TIMETABLE ---
  const [ttStyle, setTtStyle] = useState<'daily' | 'weekly'>('weekly');
  const [periods, setPeriods] = useState<string[]>([...DEFAULT_PERIODS]);
  const [courseGrid, setCourseGrid] = useState<Record<string, string>>({ ...DEFAULT_COURSES });

  // --- Generic schema fields ---
  const [schemaValues, setSchemaValues] = useState<Record<string, string>>({});

  // --- MY_ADAPTIVE ---
  const [adaptiveImageUrls, setAdaptiveImageUrls] = useState<string[]>([]);
  const [adaptiveUploading, setAdaptiveUploading] = useState(false);

  // --- VOCAB_REVIEW ---
  const [vocabDeckId, setVocabDeckId] = useState(DEFAULT_VOCAB_DECK_ID);
  const [vocabDailyLimit, setVocabDailyLimit] = useState(String(DEFAULT_VOCAB_DAILY_LIMIT));

  useEffect(() => {
    if (!configQuery.data) return;
    const ov = configQuery.data.modeOverrides?.[modeId] ?? {};

    if (modeId === 'WEATHER') {
      setCity(String(ov.city ?? ''));
      setForecastDays(String(ov.forecast_days ?? 3));
    } else if (modeId === 'MEMO') {
      setMemoText(String(ov.memo_text ?? ''));
    } else if (modeId === 'COUNTDOWN') {
      const evts = Array.isArray(ov.countdownEvents) ? ov.countdownEvents : [];
      setCountdownEvents(evts.map((e: Record<string, unknown>) => ({
        name: String(e.name ?? ''),
        date: String(e.date ?? ''),
        type: String(e.type ?? 'countdown'),
      })));
    } else if (modeId === 'CALENDAR') {
      const rem = (ov.reminders && typeof ov.reminders === 'object' && !Array.isArray(ov.reminders))
        ? ov.reminders as Record<string, string>
        : {};
      setReminders(Object.entries(rem).map(([k, v]) => {
        const parts = k.split('-');
        return { month: String(parseInt(parts[0] ?? '0', 10) || ''), day: String(parseInt(parts[1] ?? '0', 10) || ''), text: String(v) };
      }));
    } else if (modeId === 'TIMETABLE') {
      const p = Array.isArray(ov.periods) ? ov.periods.map(String) : [];
      const c = (ov.courses && typeof ov.courses === 'object' && !Array.isArray(ov.courses))
        ? ov.courses as Record<string, string>
        : {};
      if (p.length > 0 || Object.keys(c).length > 0) {
        setTtStyle(ov.style === 'weekly' ? 'weekly' : 'daily');
        setPeriods(p);
        setCourseGrid(c);
      }
    } else if (modeId === 'MY_ADAPTIVE') {
      const urls = ov.image_urls;
      if (Array.isArray(urls) && urls.length > 0) {
        setAdaptiveImageUrls(urls.filter((u: unknown) => typeof u === 'string' && (u as string).trim()) as string[]);
      } else if (typeof ov.image_url === 'string' && (ov.image_url as string).trim()) {
        setAdaptiveImageUrls([ov.image_url as string]);
      } else {
        setAdaptiveImageUrls([]);
      }
    } else if (modeId === 'VOCAB_REVIEW') {
      setVocabDeckId(String(ov.deck_id || DEFAULT_VOCAB_DECK_ID));
      setVocabDailyLimit(String(ov.daily_limit || DEFAULT_VOCAB_DAILY_LIMIT));
    } else {
      const sv: Record<string, string> = {};
      for (const [k, v] of Object.entries(ov)) {
        sv[k] = String(v ?? '');
      }
      setSchemaValues(sv);
    }
  }, [configQuery.data, modeId]);

  function buildOverride(): Record<string, unknown> {
    const base: Record<string, unknown> = {};
    if (modeId === 'WEATHER') {
      if (city.trim()) base.city = city.trim();
      const fd = parseInt(forecastDays, 10);
      if (!isNaN(fd) && fd >= 1 && fd <= 7) base.forecast_days = fd;
    } else if (modeId === 'MEMO') {
      base.memo_text = memoText;
    } else if (modeId === 'COUNTDOWN') {
      base.countdownEvents = countdownEvents.filter((e) => e.name.trim() && e.date.trim());
    } else if (modeId === 'CALENDAR') {
      const rem: Record<string, string> = {};
      for (const r of reminders) {
        const m = parseInt(r.month.trim(), 10);
        const d = parseInt(r.day.trim(), 10);
        if (!isNaN(m) && !isNaN(d) && r.text.trim()) rem[`${m}-${d}`] = r.text.trim();
      }
      base.reminders = rem;
    } else if (modeId === 'TIMETABLE') {
      base.style = ttStyle;
      base.periods = periods.filter((p) => p.trim());
      const c: Record<string, string> = {};
      for (const [k, v] of Object.entries(courseGrid)) {
        if (v.trim()) c[k] = v.trim();
      }
      base.courses = c;
    } else if (modeId === 'MY_ADAPTIVE') {
      base.image_urls = [...adaptiveImageUrls];
      base.image_url = adaptiveImageUrls[0] || '';
    } else if (modeId === 'VOCAB_REVIEW') {
      const dailyLimit = clampVocabDailyLimit(vocabDailyLimit);
      base.deck_id = VOCAB_DECKS.some((deck) => deck.id === vocabDeckId) ? vocabDeckId : DEFAULT_VOCAB_DECK_ID;
      base.daily_limit = dailyLimit;
      base.new_cards_per_day = dailyLimit;
    } else {
      for (const [k, v] of Object.entries(schemaValues)) {
        if (v.trim()) base[k] = v.trim();
      }
    }
    return base;
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const cfg = configQuery.data;
      if (!cfg) throw new Error('No config');
      const allOverrides = { ...(cfg.modeOverrides || {}) };
      allOverrides[modeId] = buildOverride();
      return saveDeviceConfig(token || '', {
        mac: mac || '',
        nickname: cfg.nickname,
        city: cfg.city,
        modes: cfg.modes,
        refreshInterval: cfg.refreshInterval,
        refreshStrategy: cfg.refreshStrategy,
        language: cfg.language,
        contentTone: cfg.contentTone,
        llmProvider: cfg.llmProvider,
        llmModel: cfg.llmModel,
        modeOverrides: allOverrides,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['device-config', mac] });
      queryClient.invalidateQueries({ queryKey: ['device-config-ms', mac] });
      queryClient.invalidateQueries({ queryKey: ['edit-device-config', mac] });
      queryClient.invalidateQueries({ queryKey: ['device-widget', mac] });
      showToast(t('device.modeSettingsSaved'), 'success');
      router.back();
    },
    onError: (err) => Alert.alert(t('device.modeSettingsSaveFailed'), err instanceof Error ? err.message : ''),
  });

  const handlePickAdaptiveImage = async () => {
    if (adaptiveImageUrls.length >= 6) {
      Alert.alert(t('ms.adaptiveMaxReached'));
      return;
    }
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert(t('ms.adaptiveSelectPhoto'));
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: false,
      quality: 0.9,
    });
    if (result.canceled || !result.assets || result.assets.length === 0) return;
    const asset = result.assets[0];
    setAdaptiveUploading(true);
    try {
      const url = await uploadImage(
        asset.uri,
        asset.mimeType || 'image/jpeg',
        asset.fileName || 'photo.jpg',
      );
      setAdaptiveImageUrls((prev) => (prev.length >= 6 ? prev : [...prev, url]));
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('ms.adaptiveUploadFailed');
      Alert.alert(t('ms.adaptiveUploadFailed'), msg);
    } finally {
      setAdaptiveUploading(false);
    }
  };

  const modeLabel = modeDisplayName(modeId, locale, modeId);

  // --- schema-based fields for generic modes ---
  const catalogItem = modesQuery.data?.modes?.find((m: ModeCatalogItem) => m.mode_id === modeId);
  const schema = catalogItem?.settings_schema ?? [];

  function renderWeather() {
    return (
      <InkCard>
        <InkText style={styles.label}>{t('ms.city')}</InkText>
        <TextInput
          style={styles.input}
          value={city}
          onChangeText={setCity}
          placeholder={t('ms.cityPlaceholder')}
          placeholderTextColor={theme.colors.tertiary}
        />
        <InkText style={styles.label}>{t('ms.forecastDays')}</InkText>
        <TextInput
          style={styles.input}
          value={forecastDays}
          onChangeText={setForecastDays}
          keyboardType="number-pad"
          placeholder="1-7"
          placeholderTextColor={theme.colors.tertiary}
        />
      </InkCard>
    );
  }

  function renderMemo() {
    return (
      <InkCard>
        <InkText style={styles.label}>{t('ms.memoText')}</InkText>
        <TextInput
          style={[styles.input, styles.textarea]}
          value={memoText}
          onChangeText={setMemoText}
          multiline
          numberOfLines={6}
          placeholder={t('ms.memoTextPlaceholder')}
          placeholderTextColor={theme.colors.tertiary}
        />
      </InkCard>
    );
  }

  function renderCountdown() {
    return (
      <InkCard>
        <InkText style={styles.label}>{t('ms.countdownEvents')}</InkText>
        {countdownEvents.map((evt, i) => (
          <View key={i} style={styles.listRow}>
            <TextInput
              style={[styles.input, styles.flex1]}
              value={evt.name}
              onChangeText={(v) => {
                const copy = [...countdownEvents];
                copy[i] = { ...evt, name: v };
                setCountdownEvents(copy);
              }}
              placeholder={t('ms.eventName')}
              placeholderTextColor={theme.colors.tertiary}
            />
            <TextInput
              style={[styles.input, styles.flex1]}
              value={evt.date}
              onChangeText={(v) => {
                const copy = [...countdownEvents];
                copy[i] = { ...evt, date: v };
                setCountdownEvents(copy);
              }}
              placeholder={t('ms.eventDate')}
              placeholderTextColor={theme.colors.tertiary}
            />
            <Pressable onPress={() => setCountdownEvents(countdownEvents.filter((_, idx) => idx !== i))}>
              <InkText style={styles.removeBtn}>{t('ms.remove')}</InkText>
            </Pressable>
          </View>
        ))}
        <InkButton
          label={t('ms.addEvent')}
          variant="ghost"
          onPress={() => setCountdownEvents([...countdownEvents, { name: '', date: '', type: 'countdown' }])}
        />
      </InkCard>
    );
  }

  function renderCalendar() {
    return (
      <InkCard>
        <InkText style={styles.label}>{t('ms.reminders')}</InkText>
        <InkText dimmed style={{ fontSize: 12, marginBottom: 10 }}>{t('ms.reminderHint')}</InkText>
        {reminders.map((r, i) => (
          <View key={i} style={styles.reminderRow}>
            <View style={styles.dateGroup}>
              <TextInput
                style={[styles.input, styles.dateInput]}
                value={r.month}
                onChangeText={(v) => {
                  const copy = [...reminders];
                  copy[i] = { ...r, month: v.replace(/\D/g, '').slice(0, 2) };
                  setReminders(copy);
                }}
                placeholder={t('ms.month')}
                placeholderTextColor={theme.colors.tertiary}
                keyboardType="number-pad"
                maxLength={2}
              />
              <InkText dimmed>-</InkText>
              <TextInput
                style={[styles.input, styles.dateInput]}
                value={r.day}
                onChangeText={(v) => {
                  const copy = [...reminders];
                  copy[i] = { ...r, day: v.replace(/\D/g, '').slice(0, 2) };
                  setReminders(copy);
                }}
                placeholder={t('ms.day')}
                placeholderTextColor={theme.colors.tertiary}
                keyboardType="number-pad"
                maxLength={2}
              />
            </View>
            <TextInput
              style={[styles.input, styles.flex1]}
              value={r.text}
              onChangeText={(v) => {
                const copy = [...reminders];
                copy[i] = { ...r, text: v };
                setReminders(copy);
              }}
              placeholder={t('ms.reminderText')}
              placeholderTextColor={theme.colors.tertiary}
            />
            <Pressable onPress={() => setReminders(reminders.filter((_, idx) => idx !== i))}>
              <InkText style={styles.removeBtn}>{t('ms.remove')}</InkText>
            </Pressable>
          </View>
        ))}
        <InkButton
          label={t('ms.addReminder')}
          variant="ghost"
          onPress={() => setReminders([...reminders, { month: '', day: '', text: '' }])}
        />
      </InkCard>
    );
  }

  function loadTimetableTemplate() {
    setPeriods([...DEFAULT_PERIODS]);
    setCourseGrid({ ...DEFAULT_COURSES });
    setTtStyle('weekly');
  }

  function renderTimetable() {
    const allDayLabels = Array.from({ length: WEEKDAYS }, (_, i) => t(`ms.day${i}`));
    const todayIdx = new Date().getDay();
    const todayDayIdx = todayIdx === 0 ? 6 : todayIdx - 1;
    const visibleDays = ttStyle === 'weekly'
      ? Array.from({ length: WEEKDAYS }, (_, i) => i)
      : [Math.min(todayDayIdx, WEEKDAYS - 1)];

    return (
      <>
        <InkCard>
          <View style={styles.rowBetween}>
            <InkText style={styles.label}>{t('ms.timetableStyle')}</InkText>
            <InkButton label={t('ms.loadTemplate')} variant="ghost" onPress={loadTimetableTemplate} />
          </View>
          <View style={styles.row}>
            <InkButton
              label={t('ms.timetableStyleDaily')}
              variant={ttStyle === 'daily' ? 'primary' : 'secondary'}
              onPress={() => setTtStyle('daily')}
            />
            <InkButton
              label={t('ms.timetableStyleWeekly')}
              variant={ttStyle === 'weekly' ? 'primary' : 'secondary'}
              onPress={() => setTtStyle('weekly')}
            />
          </View>
        </InkCard>

        <InkCard>
          <InkText style={styles.label}>{t('ms.periods')}</InkText>
          {periods.map((p, i) => (
            <View key={i} style={styles.listRow}>
              <TextInput
                style={[styles.input, styles.flex1]}
                value={p}
                onChangeText={(v) => {
                  const copy = [...periods];
                  copy[i] = v;
                  setPeriods(copy);
                }}
                placeholder={t('ms.periodPlaceholder')}
                placeholderTextColor={theme.colors.tertiary}
              />
              <Pressable onPress={() => setPeriods(periods.filter((_, idx) => idx !== i))}>
                <InkText style={styles.removeBtn}>{t('ms.remove')}</InkText>
              </Pressable>
            </View>
          ))}
          <InkButton
            label={t('ms.addPeriod')}
            variant="ghost"
            onPress={() => setPeriods([...periods, ''])}
          />
        </InkCard>

        <InkCard>
          <InkText style={styles.label}>{t('ms.courses')}</InkText>
          <View style={styles.gridHeader}>
            <View style={styles.gridPeriodCol} />
            {visibleDays.map((di) => (
              <InkText key={di} dimmed style={styles.gridDayLabel}>{allDayLabels[di]}</InkText>
            ))}
          </View>
          {periods.map((period, pi) => (
            <View key={pi} style={styles.gridRow}>
              <InkText dimmed style={styles.gridPeriodLabel} numberOfLines={1}>{period}</InkText>
              {visibleDays.map((di) => {
                const key = `${di}-${pi}`;
                return (
                  <TextInput
                    key={key}
                    style={ttStyle === 'daily' ? styles.gridCellWide : styles.gridCell}
                    value={courseGrid[key] ?? ''}
                    onChangeText={(v) => setCourseGrid((prev) => ({ ...prev, [key]: v }))}
                    placeholder="-"
                    placeholderTextColor={theme.colors.border}
                    numberOfLines={1}
                  />
                );
              })}
            </View>
          ))}
        </InkCard>
      </>
    );
  }

  function renderGenericSchema() {
    if (schema.length === 0) return null;
    return (
      <InkCard>
        {schema.map((field: Record<string, unknown>) => {
          const key = String(field.key ?? '');
          const label = String(field.label ?? key);
          const type = String(field.type ?? 'text');
          const placeholder = String(field.placeholder ?? '');
          const val = schemaValues[key] ?? String(field.default ?? '');
          return (
            <View key={key} style={{ marginBottom: 12 }}>
              <InkText style={styles.label}>{label}</InkText>
              <TextInput
                style={[styles.input, type === 'textarea' ? styles.textarea : null]}
                value={val}
                onChangeText={(v) => setSchemaValues((prev) => ({ ...prev, [key]: v }))}
                placeholder={placeholder}
                placeholderTextColor={theme.colors.tertiary}
                keyboardType={type === 'number' ? 'number-pad' : 'default'}
                multiline={type === 'textarea'}
                numberOfLines={type === 'textarea' ? 4 : 1}
              />
            </View>
          );
        })}
      </InkCard>
    );
  }

  function renderAdaptive() {
    return (
      <InkCard>
        <InkText style={styles.label}>{t('ms.adaptiveTitle')}</InkText>
        <InkText dimmed style={{ fontSize: 12, marginBottom: 10 }}>{t('ms.adaptiveHint')}</InkText>
        <View style={styles.adaptiveGrid}>
          {adaptiveImageUrls.map((url, i) => (
            <View key={`${url}-${i}`} style={styles.adaptiveItem}>
              <Image source={{ uri: url }} style={styles.adaptiveImg} />
              <Pressable
                style={styles.adaptiveRemoveBtn}
                onPress={() => setAdaptiveImageUrls((prev) => prev.filter((_, idx) => idx !== i))}
              >
                <InkText style={styles.adaptiveRemoveText}>✕</InkText>
              </Pressable>
              <View style={styles.adaptiveIndex}>
                <InkText style={styles.adaptiveIndexText}>{i + 1}</InkText>
              </View>
            </View>
          ))}
          {adaptiveImageUrls.length < 6 && (
            <Pressable
              style={styles.adaptiveAddBtn}
              onPress={handlePickAdaptiveImage}
              disabled={adaptiveUploading}
            >
              {adaptiveUploading ? (
                <InkText dimmed style={{ fontSize: 12 }}>{t('ms.adaptiveUploading')}</InkText>
              ) : (
                <>
                  <InkText style={styles.adaptiveAddIcon}>+</InkText>
                  <InkText dimmed style={{ fontSize: 10 }}>{t('ms.adaptiveAdd')}</InkText>
                </>
              )}
            </Pressable>
          )}
        </View>
      </InkCard>
    );
  }

  function renderVocabReview() {
    return (
      <InkCard>
        <InkText style={styles.label}>{t('ms.vocabDeck')}</InkText>
        <InkText dimmed style={styles.helpText}>{t('ms.vocabHint')}</InkText>
        <View style={styles.deckGrid}>
          {VOCAB_DECKS.map((deck) => {
            const active = vocabDeckId === deck.id;
            return (
              <InkButton
                key={deck.id}
                label={t(deck.labelKey) === deck.labelKey ? deck.fallback : t(deck.labelKey)}
                variant={active ? 'primary' : 'secondary'}
                onPress={() => setVocabDeckId(deck.id)}
                style={styles.deckButton}
              />
            );
          })}
        </View>

        <View style={styles.fieldGap}>
          <InkText style={styles.label}>{t('ms.vocabDailyGoal')}</InkText>
          <TextInput
            style={styles.input}
            value={vocabDailyLimit}
            onChangeText={(v) => setVocabDailyLimit(v.replace(/\D/g, '').slice(0, 3))}
            onBlur={() => setVocabDailyLimit(String(clampVocabDailyLimit(vocabDailyLimit)))}
            keyboardType="number-pad"
            placeholder="30"
            placeholderTextColor={theme.colors.tertiary}
          />
        </View>

        <InkButton
          label={t('ms.vocabSaveDefault')}
          variant="ghost"
          onPress={() => {
            setVocabDeckId(DEFAULT_VOCAB_DECK_ID);
            setVocabDailyLimit(String(DEFAULT_VOCAB_DAILY_LIMIT));
          }}
        />
      </InkCard>
    );
  }

  const hasCustomEditor = ['WEATHER', 'MEMO', 'COUNTDOWN', 'CALENDAR', 'TIMETABLE', 'MY_ADAPTIVE', 'VOCAB_REVIEW'].includes(modeId);

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('device.modeSettings')}</InkText>
      <InkText dimmed>{modeLabel}</InkText>

      {modeId === 'WEATHER' && renderWeather()}
      {modeId === 'MEMO' && renderMemo()}
      {modeId === 'COUNTDOWN' && renderCountdown()}
      {modeId === 'CALENDAR' && renderCalendar()}
      {modeId === 'TIMETABLE' && renderTimetable()}
      {modeId === 'MY_ADAPTIVE' && renderAdaptive()}
      {modeId === 'VOCAB_REVIEW' && renderVocabReview()}
      {!hasCustomEditor && (schema.length > 0 ? renderGenericSchema() : (
        <InkCard><InkText dimmed>{t('device.modeSettingsNoSchema')}</InkText></InkCard>
      ))}

      <InkButton
        label={saveMutation.isPending ? t('common.loading') : t('common.save')}
        block
        onPress={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
      />
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  label: {
    marginBottom: 8,
    fontWeight: '600',
  },
  input: {
    height: 50,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 16,
    marginBottom: 10,
    color: theme.colors.ink,
  },
  textarea: {
    height: 120,
    textAlignVertical: 'top',
    paddingTop: 12,
  },
  row: {
    flexDirection: 'row',
    gap: 10,
  },
  fieldGap: {
    marginTop: 14,
  },
  helpText: {
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 12,
  },
  deckGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  deckButton: {
    marginBottom: 0,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  listRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  flex1: {
    flex: 1,
  },
  removeBtn: {
    color: theme.colors.tertiary,
    fontSize: 13,
    paddingHorizontal: 4,
  },
  reminderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  dateGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dateInput: {
    width: 48,
    textAlign: 'center',
    paddingHorizontal: 4,
  },
  gridHeader: {
    flexDirection: 'row',
    marginBottom: 4,
  },
  gridPeriodCol: {
    width: 72,
  },
  gridDayLabel: {
    flex: 1,
    textAlign: 'center',
    fontSize: 12,
    fontWeight: '600',
  },
  gridRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  gridPeriodLabel: {
    width: 72,
    fontSize: 11,
    color: theme.colors.secondary,
  },
  gridCell: {
    flex: 1,
    height: 40,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surface,
    marginHorizontal: 2,
    paddingHorizontal: 4,
    fontSize: 11,
    color: theme.colors.ink,
    textAlign: 'center',
  },
  gridCellWide: {
    flex: 1,
    height: 44,
    borderRadius: theme.radius.sm,
    backgroundColor: theme.colors.surface,
    marginHorizontal: 2,
    paddingHorizontal: 12,
    fontSize: 14,
    color: theme.colors.ink,
  },
  adaptiveGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  adaptiveItem: {
    width: '30%',
    aspectRatio: 4 / 3,
    borderRadius: theme.radius.md,
    overflow: 'hidden',
    backgroundColor: theme.colors.surface,
  },
  adaptiveImg: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  adaptiveRemoveBtn: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  adaptiveRemoveText: {
    color: '#fff',
    fontSize: 11,
    lineHeight: 14,
  },
  adaptiveIndex: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: 'rgba(0,0,0,0.35)',
    paddingVertical: 2,
    alignItems: 'center',
  },
  adaptiveIndexText: {
    color: '#fff',
    fontSize: 10,
  },
  adaptiveAddBtn: {
    width: '30%',
    aspectRatio: 4 / 3,
    borderRadius: theme.radius.md,
    borderWidth: 1.5,
    borderColor: theme.colors.border,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
  },
  adaptiveAddIcon: {
    fontSize: 22,
    color: theme.colors.secondary,
    lineHeight: 26,
  },
});
