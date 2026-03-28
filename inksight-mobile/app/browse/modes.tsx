import { Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { ModeIcon } from '@/components/content/ModeIcon';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { listModes } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { localizeCatalogMode } from '@/lib/mode-display';
import { theme } from '@/lib/theme';

const GRID_GAP = 12;
const COLS = 3;

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

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('catalog.title')}</InkText>
      <InkText dimmed>{t('catalog.subtitle')}</InkText>

      <View style={styles.grid}>
        {(modesQuery.data?.modes || []).map((mode) => {
          const { display_name, description } = localizeCatalogMode(mode, locale);
          return (
            <Pressable
              key={mode.mode_id}
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
                <InkText style={styles.modeTitle}>{display_name}</InkText>
                <InkText dimmed style={styles.modeSummary}>{description || mode.mode_id}</InkText>
              </InkCard>
            </Pressable>
          );
        })}
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
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
    paddingHorizontal: 10,
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
    marginTop: 10,
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  modeSummary: {
    marginTop: 4,
    fontSize: 11,
    textAlign: 'center',
  },
});
