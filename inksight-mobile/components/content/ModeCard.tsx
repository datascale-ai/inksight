import { Animated, Pressable, StyleSheet, View } from 'react-native';
import { Heart, Share2, Sunrise, Sunset } from 'lucide-react-native';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { ModeIcon } from '@/components/content/ModeIcon';
import type { TodayItem } from '@/features/content/api';
import { theme } from '@/lib/theme';

type Props = {
  item: TodayItem;
  variant: 'poetry' | 'daily' | 'weather';
  favorite: boolean;
  favoriteScale: Animated.Value;
  onToggleFavorite: () => void;
  onShare: () => void;
  onPress: () => void;
  onLongPress: () => void;
};

function CardHeader({ item, favorite, favoriteScale, onToggleFavorite, onShare }: Pick<Props, 'item' | 'favorite' | 'favoriteScale' | 'onToggleFavorite' | 'onShare'>) {
  return (
    <View style={styles.header}>
      <View style={styles.modePill}>
        <ModeIcon modeId={item.mode_id} size={16} color={theme.colors.secondary} />
        <InkText style={styles.modeText}>{item.display_name}</InkText>
      </View>
      <View style={styles.actions}>
        <Pressable onPress={onToggleFavorite} style={styles.actionButton}>
          <Animated.View style={{ transform: [{ scale: favoriteScale }] }}>
            <Heart
              size={18}
              color={favorite ? theme.colors.danger : theme.colors.secondary}
              fill={favorite ? theme.colors.danger : 'transparent'}
              strokeWidth={theme.strokeWidth}
            />
          </Animated.View>
        </Pressable>
        <Pressable onPress={onShare} style={styles.actionButton}>
          <Share2 size={18} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
        </Pressable>
      </View>
    </View>
  );
}

/* ── POETRY ── */
function PoetryBody({ content }: { content: Record<string, unknown> }) {
  const title = typeof content.title === 'string' ? content.title : '';
  const author = typeof content.author === 'string' ? content.author : '';
  const lines = Array.isArray(content.lines) ? (content.lines as string[]) : [];
  const note = typeof content.note === 'string' ? content.note : '';

  return (
    <View style={styles.poetryBody}>
      <View style={styles.decorLine} />
      {title ? <InkText serif dimmed style={styles.poetryTitle}>{title}</InkText> : null}
      {lines.map((line, i) => (
        <InkText serif key={i} style={styles.poetryLine}>{line}</InkText>
      ))}
      {author ? <InkText serif dimmed style={styles.poetryAuthor}>— {author}</InkText> : null}
      <View style={styles.decorLine} />
      {note ? <InkText dimmed style={styles.poetryNote}>{note}</InkText> : null}
    </View>
  );
}

/* ── DAILY ── */
function DailyBody({ content }: { content: Record<string, unknown> }) {
  const quote = typeof content.quote === 'string' ? content.quote : (typeof content.text === 'string' ? content.text : '');
  const author = typeof content.author === 'string' ? content.author : '';
  const bookTitle = typeof content.book_title === 'string' ? content.book_title : '';
  const bookDesc = typeof content.book_desc === 'string' ? content.book_desc : '';
  const bookAuthor = typeof content.book_author === 'string' ? content.book_author : '';
  const seasonText = typeof content.season_text === 'string' ? content.season_text : '';

  return (
    <View style={styles.dailyBody}>
      <InkText style={styles.dailyQuoteMark}>{'\u201C'}</InkText>
      <View style={styles.dailyQuoteWrap}>
        <InkText serif style={styles.dailyQuote}>{quote}</InkText>
        {author ? <InkText serif dimmed style={styles.dailyAuthor}>— {author}</InkText> : null}
      </View>

      {bookTitle ? (
        <View style={styles.bookCard}>
          <InkText style={styles.bookTitle}>{bookTitle}</InkText>
          {bookAuthor ? <InkText dimmed style={styles.bookAuthor}>{bookAuthor}</InkText> : null}
          {bookDesc ? <InkText dimmed style={styles.bookDesc}>{bookDesc}</InkText> : null}
        </View>
      ) : null}

      {seasonText ? <InkText dimmed style={styles.seasonText}>{seasonText}</InkText> : null}
    </View>
  );
}

/* ── WEATHER ── */
type ForecastDay = { day?: string; date?: string; temp_range?: string; desc?: string };

function WeatherBody({ content }: { content: Record<string, unknown> }) {
  const city = typeof content.city === 'string' ? content.city : '';
  const temp = typeof content.today_temp === 'string' ? content.today_temp : '';
  const desc = typeof content.today_desc === 'string' ? content.today_desc : '';
  const advice = typeof content.advice === 'string' ? content.advice : '';
  const forecast = Array.isArray(content.forecast) ? (content.forecast as ForecastDay[]).slice(0, 3) : [];
  const sunrise = typeof content.sunrise === 'string' ? content.sunrise : '';
  const sunset = typeof content.sunset === 'string' ? content.sunset : '';

  return (
    <View style={styles.weatherBody}>
      <View style={styles.weatherMain}>
        <View>
          <InkText dimmed style={styles.weatherCity}>{city}</InkText>
          <InkText serif style={styles.weatherTemp}>{temp}°C</InkText>
        </View>
        <InkText style={styles.weatherDesc}>{desc}</InkText>
      </View>

      {advice ? <InkText dimmed style={styles.weatherAdvice}>{advice}</InkText> : null}

      {forecast.length > 0 ? (
        <View style={styles.forecastRow}>
          {forecast.map((f, i) => (
            <View key={i} style={[styles.forecastItem, { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 }]}>
              <InkText dimmed style={styles.forecastDay}>{f.day}</InkText>
              <InkText style={styles.forecastTemp}>{f.temp_range}</InkText>
              <InkText dimmed style={styles.forecastDesc}>{f.desc}</InkText>
            </View>
          ))}
        </View>
      ) : null}

      {sunrise || sunset ? (
        <View style={styles.sunRow}>
          {sunrise ? (
            <View style={styles.sunItem}>
              <Sunrise size={14} color={theme.colors.tertiary} strokeWidth={theme.strokeWidth} />
              <InkText dimmed style={styles.sunText}>{sunrise}</InkText>
            </View>
          ) : null}
          {sunset ? (
            <View style={styles.sunItem}>
              <Sunset size={14} color={theme.colors.tertiary} strokeWidth={theme.strokeWidth} />
              <InkText dimmed style={styles.sunText}>{sunset}</InkText>
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

/* ── Main ── */
export function ModeCard(props: Props) {
  const { item, variant, onPress, onLongPress } = props;
  const isWeather = variant === 'weather';

  return (
    <InkCard style={isWeather ? styles.weatherCard : undefined}>
      <CardHeader {...props} />
      <Pressable onPress={onPress} onLongPress={onLongPress}>
        {variant === 'poetry' ? <PoetryBody content={item.content} /> : null}
        {variant === 'daily' ? <DailyBody content={item.content} /> : null}
        {variant === 'weather' ? <WeatherBody content={item.content} /> : null}
      </Pressable>
    </InkCard>
  );
}

const styles = StyleSheet.create({
  /* shared header */
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  modePill: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  modeText: { fontSize: 12, color: theme.colors.secondary, letterSpacing: 2 },
  actions: { flexDirection: 'row', gap: 8 },
  actionButton: {
    width: 32, height: 32, borderRadius: theme.radius.pill,
    alignItems: 'center', justifyContent: 'center', backgroundColor: theme.colors.surface,
  },

  /* poetry */
  poetryBody: { alignItems: 'center', marginTop: theme.spacing.lg, gap: theme.spacing.xs },
  decorLine: { width: 40, height: 1, backgroundColor: theme.colors.tertiary, marginVertical: theme.spacing.sm },
  poetryTitle: { fontSize: 16, marginBottom: 4 },
  poetryLine: { fontSize: 22, lineHeight: 40, textAlign: 'center', letterSpacing: 1.5 },
  poetryAuthor: { fontSize: 14, marginTop: 4 },
  poetryNote: { fontSize: 13, lineHeight: 20, textAlign: 'center', marginTop: 4 },

  /* daily */
  dailyBody: { marginTop: theme.spacing.md },
  dailyQuoteMark: { fontSize: 48, lineHeight: 52, color: theme.colors.tertiary },
  dailyQuoteWrap: { borderLeftWidth: 3, borderLeftColor: theme.colors.accent, paddingLeft: theme.spacing.md },
  dailyQuote: { fontSize: 20, lineHeight: 36, letterSpacing: 0.8 },
  dailyAuthor: { fontSize: 14, marginTop: theme.spacing.sm },
  bookCard: {
    marginTop: theme.spacing.md, padding: theme.spacing.md,
    backgroundColor: theme.colors.surface, borderRadius: theme.radius.sm, gap: 4,
  },
  bookTitle: { fontSize: 15, fontWeight: '600' },
  bookAuthor: { fontSize: 13 },
  bookDesc: { fontSize: 13, lineHeight: 20 },
  seasonText: { fontSize: 13, marginTop: theme.spacing.sm, fontStyle: 'italic' },

  /* weather */
  weatherCard: { backgroundColor: theme.colors.surface },
  weatherBody: { marginTop: theme.spacing.md, gap: theme.spacing.md },
  weatherMain: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  weatherCity: { fontSize: 14 },
  weatherTemp: { fontSize: 40, fontWeight: '700', lineHeight: 48 },
  weatherDesc: { fontSize: 18, color: theme.colors.secondary },
  weatherAdvice: { fontSize: 15, lineHeight: 24 },
  forecastRow: { flexDirection: 'row', gap: theme.spacing.sm },
  forecastItem: {
    flex: 1, alignItems: 'center', gap: 4,
    paddingVertical: theme.spacing.sm, backgroundColor: theme.colors.card,
    borderRadius: theme.radius.sm,
  },
  forecastDay: { fontSize: 12, fontWeight: '600' },
  forecastTemp: { fontSize: 13 },
  forecastDesc: { fontSize: 12, maxWidth: 60 },
  sunRow: { flexDirection: 'row', gap: theme.spacing.lg },
  sunItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  sunText: { fontSize: 12 },
});
