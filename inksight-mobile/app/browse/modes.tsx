import { Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { ModeIcon } from '@/components/content/ModeIcon';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { listModes, type ModeCatalogItem } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { localizeCatalogMode } from '@/lib/mode-display';
import { theme } from '@/lib/theme';

const GRID_GAP = 12;
const COLS = 3;

function ModeCard({ mode, locale, cardWidth }: { mode: ModeCatalogItem; locale: string; cardWidth: number }) {
  const { display_name, description } = localizeCatalogMode(mode, locale);
  return (
    <Pressable
      style={{ width: cardWidth }}
      onPress={() =>
        router.push(
          `/browse/${encodeURIComponent(mode.mode_id)}?kind=mode&title=${encodeURIComponent(display_name)}&summary=${encodeURIComponent(description || display_name)}`,
        )
      }
    >
      <InkCard style={[styles.card, { width: cardWidth }]}>
        <View style={styles.iconWrap}>
          <ModeIcon modeId={mode.mode_id} />
        </View>
        <View style={styles.titleBlock}>
          <InkText numberOfLines={2} ellipsizeMode="tail" style={styles.modeTitle}>
            {display_name}
          </InkText>
        </View>
        <View style={styles.summaryBlock}>
          <InkText
            numberOfLines={3}
            ellipsizeMode="tail"
            dimmed
            style={styles.modeSummary}
          >
            {description || mode.mode_id}
          </InkText>
        </View>
      </InkCard>
    </Pressable>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <View style={styles.sectionHeader}>
      <InkText style={styles.sectionTitle}>{title}</InkText>
    </View>
  );
}

export default function BrowseModesScreen() {
  const { locale, t } = useI18n();
  const { width: windowWidth } = useWindowDimensions();
  const modesQuery = useQuery({
    queryKey: ['browse-modes-catalog'],
    queryFn: listModes,
  });

  const horizontalPad = theme.spacing.lg * 2;
  const cardWidth = Math.max(
    96,
    Math.floor((windowWidth - horizontalPad - GRID_GAP * (COLS - 1)) / COLS),
  );

  const allModes = modesQuery.data?.modes || [];
  const builtinModes = allModes.filter((m) => m.source !== 'custom');
  const customModes = allModes.filter((m) => m.source === 'custom');

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('catalog.title')}</InkText>
      <InkText dimmed>{t('catalog.subtitle')}</InkText>

      {builtinModes.length > 0 && (
        <View style={styles.section}>
          <SectionHeader title={t('catalog.builtinModes', 'Built-in modes')} />
          <View style={styles.grid}>
            {builtinModes.map((mode) => (
              <ModeCard key={mode.mode_id} mode={mode} locale={locale} cardWidth={cardWidth} />
            ))}
          </View>
        </View>
      )}

      {customModes.length > 0 && (
        <View style={styles.section}>
          <SectionHeader title={t('catalog.customModes', 'Custom modes')} />
          <View style={styles.grid}>
            {customModes.map((mode) => (
              <ModeCard key={mode.mode_id} mode={mode} locale={locale} cardWidth={cardWidth} />
            ))}
          </View>
        </View>
      )}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  section: {
    marginTop: 24,
  },
  sectionHeader: {
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    columnGap: GRID_GAP,
    rowGap: GRID_GAP,
    justifyContent: 'center',
  },
  card: {
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: theme.spacing.md,
    height: 196,
    justifyContent: 'flex-start',
    overflow: 'hidden',
  },
  titleBlock: {
    marginTop: 10,
    width: '100%',
    minHeight: 32,
    justifyContent: 'center',
  },
  summaryBlock: {
    marginTop: 4,
    width: '100%',
    height: 42,
  },
  iconWrap: {
    width: 42,
    height: 42,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modeTitle: {
    fontSize: 12,
    lineHeight: 16,
    fontWeight: '600',
    textAlign: 'center',
  },
  modeSummary: {
    fontSize: 11,
    lineHeight: 14,
    textAlign: 'center',
  },
});
