import { Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { ModeIcon } from '@/components/content/ModeIcon';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { listModes } from '@/features/modes/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

const COLUMNS = 2;
const GAP = 10;
const PADDING = theme.spacing.lg;

export default function BrowseModesScreen() {
  const { t } = useI18n();
  const { width: screenWidth } = useWindowDimensions();
  const cardWidth = (screenWidth - PADDING * 2 - GAP * (COLUMNS - 1)) / COLUMNS;
  const modesQuery = useQuery({
    queryKey: ['browse-modes-catalog'],
    queryFn: listModes,
  });

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('catalog.title')}</InkText>
      <InkText dimmed>{t('catalog.subtitle')}</InkText>

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
            <InkCard style={styles.card}>
              <View style={styles.iconWrap}>
                <ModeIcon modeId={mode.mode_id} />
              </View>
              <InkText style={styles.modeTitle}>{mode.display_name}</InkText>
              <InkText dimmed style={styles.modeSummary}>{mode.description || mode.mode_id}</InkText>
            </InkCard>
          </Pressable>
        ))}
      </View>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 28,
    fontWeight: '600',
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: GAP,
  },
  card: {
    width: '100%',
    alignItems: 'center',
    paddingHorizontal: 6,
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
    fontSize: 14,
    fontWeight: '600',
    textAlign: 'center',
  },
  modeSummary: {
    marginTop: 4,
    fontSize: 12,
    textAlign: 'center',
  },
});
