import { useEffect, useRef, useState } from 'react';
import { Animated } from 'react-native';
import type { TodayItem } from '@/features/content/api';
import { isFavoriteTodayItem, toggleLocalFavorite } from '@/features/content/storage';
import { mediumImpact } from '@/features/feedback/haptics';

export function useFavoriteState(item: TodayItem | undefined) {
  const [isFavorite, setIsFavorite] = useState(false);
  const favoriteScale = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!item) {
      setIsFavorite(false);
      return;
    }
    isFavoriteTodayItem(item).then(setIsFavorite);
  }, [item]);

  async function toggle() {
    if (!item) return null;
    Animated.sequence([
      Animated.spring(favoriteScale, { toValue: 1.3, useNativeDriver: true, friction: 3, tension: 200 }),
      Animated.spring(favoriteScale, { toValue: 1, useNativeDriver: true, friction: 4 }),
    ]).start();
    const result = await toggleLocalFavorite(item);
    setIsFavorite(result.active);
    await mediumImpact();
    return result;
  }

  return { isFavorite, favoriteScale, toggle };
}
