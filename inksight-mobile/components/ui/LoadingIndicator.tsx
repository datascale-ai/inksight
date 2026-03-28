import { useEffect, useRef, useState } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { useIsFetching } from '@tanstack/react-query';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { theme } from '@/lib/theme';

const DELAY_MS = 400;   // don't flash for fast requests
const FADE_MS = 200;
const MIN_DURATION_MS = 300; // keep visible at least this long after appearing

export function LoadingIndicator() {
  const fetchingCount = useIsFetching();
  const isLoading = fetchingCount > 0;
  const insets = useSafeAreaInsets();

  const opacity = useRef(new Animated.Value(0)).current;
  const [visible, setVisible] = useState(false);
  const showTimerRef = { current: null as ReturnType<typeof setTimeout> | null };

  useEffect(() => {
    if (isLoading) {
      // Delay showing so quick requests (< DELAY_MS) don't flash
      if (showTimerRef.current) clearTimeout(showTimerRef.current);
      showTimerRef.current = setTimeout(() => {
        setVisible(true);
        Animated.timing(opacity, {
          toValue: 1,
          duration: FADE_MS,
          useNativeDriver: true,
        }).start();
      }, DELAY_MS);
    } else {
      if (showTimerRef.current) clearTimeout(showTimerRef.current);
      // Keep visible for MIN_DURATION then fade out
      const hideTimer = setTimeout(() => {
        Animated.timing(opacity, {
          toValue: 0,
          duration: FADE_MS,
          useNativeDriver: true,
        }).start(() => setVisible(false));
      }, MIN_DURATION_MS);
      return () => clearTimeout(hideTimer);
    }

    return () => {
      if (showTimerRef.current) clearTimeout(showTimerRef.current);
    };
  }, [isLoading, opacity]);

  if (!visible) return null;

  return (
    <Animated.View
      style={[
        styles.container,
        { top: insets.top, opacity },
        // stay above page content, below toasts (9999)
      ]}
      pointerEvents="none"
    >
      <Text style={styles.text}>Loading…</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 0,
    right: 0,
    backgroundColor: theme.colors.ink,
    paddingVertical: 5,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9998,
  },
  text: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.5,
  },
});
