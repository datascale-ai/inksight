import { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';
import { theme } from '@/lib/theme';

export function InkLoadingLine() {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(progress, {
        toValue: 1,
        duration: 1400,
        easing: Easing.inOut(Easing.ease),
        useNativeDriver: false,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [progress]);

  const width = progress.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: ['0%', '76%', '0%'],
  });

  return (
    <View style={styles.track}>
      <Animated.View style={[styles.bar, { width }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    width: '100%',
    height: 3,
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.border,
    overflow: 'hidden',
  },
  bar: {
    height: '100%',
    borderRadius: theme.radius.pill,
    backgroundColor: theme.colors.ink,
  },
});
