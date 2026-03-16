import { useState } from 'react';
import { Animated, Image, Pressable, StyleSheet, View } from 'react-native';
import { Heart, Share2 } from 'lucide-react-native';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { ModeIcon } from '@/components/content/ModeIcon';
import { theme } from '@/lib/theme';

type Props = {
  modeId: string;
  title: string;
  summary: string;
  attribution?: string;
  imageUrl?: string;
  favorite?: boolean;
  favoriteScale?: Animated.Value;
  onToggleFavorite?: () => void;
  onShare?: () => void;
  onPress?: () => void;
  onLongPress?: () => void;
};

export function ContentCard({ modeId, title, summary, attribution, imageUrl, favorite, favoriteScale, onToggleFavorite, onShare, onPress, onLongPress }: Props) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  return (
    <InkCard>
      <View style={styles.header}>
        <View style={styles.modePill}>
          <ModeIcon modeId={modeId} size={16} color={theme.colors.secondary} />
          <InkText style={styles.modeText}>{title}</InkText>
        </View>
        <View style={styles.actions}>
          {onToggleFavorite ? (
            <Pressable onPress={onToggleFavorite} style={styles.actionButton}>
              <Animated.View style={favoriteScale ? { transform: [{ scale: favoriteScale }] } : undefined}>
                <Heart
                  size={18}
                  color={favorite ? theme.colors.danger : theme.colors.secondary}
                  fill={favorite ? theme.colors.danger : 'transparent'}
                  strokeWidth={theme.strokeWidth}
                />
              </Animated.View>
            </Pressable>
          ) : null}
          {onShare ? (
            <Pressable onPress={onShare} style={styles.actionButton}>
              <Share2 size={18} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
            </Pressable>
          ) : null}
        </View>
      </View>

      {imageUrl && !imageError ? (
        <View style={styles.imageWrap}>
          {!imageLoaded ? <View style={styles.imagePlaceholder} /> : null}
          <Image
            source={{ uri: imageUrl }}
            style={[styles.image, !imageLoaded ? styles.imageHidden : null]}
            resizeMode="cover"
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />
        </View>
      ) : null}

      <Pressable onPress={onPress} onLongPress={onLongPress} disabled={!onPress && !onLongPress} style={styles.body}>
        <InkText serif style={styles.summary}>
          {summary}
        </InkText>
        {attribution ? (
          <InkText serif dimmed style={styles.attribution}>
            {attribution}
          </InkText>
        ) : null}
      </Pressable>
    </InkCard>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  modeText: {
    fontSize: 12,
    color: theme.colors.secondary,
    letterSpacing: 2,
  },
  actions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionButton: {
    width: 32,
    height: 32,
    borderRadius: theme.radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: theme.colors.surface,
  },
  body: {
    marginTop: theme.spacing.lg,
    gap: theme.spacing.sm,
  },
  imageWrap: {
    marginTop: theme.spacing.md,
    borderRadius: theme.radius.md,
    overflow: 'hidden',
    backgroundColor: theme.colors.surface,
  },
  image: {
    width: '100%',
    aspectRatio: 4 / 3,
  },
  imageHidden: {
    position: 'absolute',
    opacity: 0,
  },
  imagePlaceholder: {
    width: '100%',
    aspectRatio: 4 / 3,
    backgroundColor: theme.colors.surface,
  },
  summary: {
    fontSize: 24,
    lineHeight: 42,
    letterSpacing: 1.2,
  },
  attribution: {
    fontSize: 14,
  },
});
