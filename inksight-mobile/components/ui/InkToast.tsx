import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { theme } from '@/lib/theme';

export type ToastVariant = 'success' | 'error' | 'info';

export type ToastConfig = {
  id: string;
  message: string;
  variant: ToastVariant;
};

type Props = {
  toast: ToastConfig;
  onDismiss: (id: string) => void;
};

const DURATION_MS = 2500;
const ANIMATION_DURATION_MS = 250;

export function InkToast({ toast, onDismiss }: Props) {
  const insets = useSafeAreaInsets();
  const translateY = useRef(new Animated.Value(-80)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Slide in
    Animated.parallel([
      Animated.timing(translateY, {
        toValue: 0,
        duration: ANIMATION_DURATION_MS,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: ANIMATION_DURATION_MS,
        useNativeDriver: true,
      }),
    ]).start();

    // Schedule slide out
    const dismissTimer = setTimeout(() => {
      // Start exit animation early so total visible time is ~DURATION_MS
      Animated.parallel([
        Animated.timing(translateY, {
          toValue: -80,
          duration: ANIMATION_DURATION_MS,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0,
          duration: ANIMATION_DURATION_MS,
          useNativeDriver: true,
        }),
      ]).start(() => {
        onDismiss(toast.id);
      });
    }, DURATION_MS - ANIMATION_DURATION_MS);

    return () => clearTimeout(dismissTimer);
  }, [toast.id, translateY, opacity, onDismiss]);

  const variantStyle = variantStyles[toast.variant];

  return (
    <Animated.View
      style={[
        styles.container,
        variantStyle.container,
        { top: insets.top + theme.spacing.sm, transform: [{ translateY }], opacity },
      ]}
      pointerEvents="none"
    >
      <Text style={[styles.message, variantStyle.text]} numberOfLines={2}>
        {toast.message}
      </Text>
    </Animated.View>
  );
}

const variantStyles = {
  success: StyleSheet.create({
    container: {
      backgroundColor: theme.colors.success,
    },
    text: {
      color: '#FFFFFF',
    },
  }),
  error: StyleSheet.create({
    container: {
      backgroundColor: theme.colors.danger,
    },
    text: {
      color: '#FFFFFF',
    },
  }),
  info: StyleSheet.create({
    container: {
      backgroundColor: theme.colors.ink,
    },
    text: {
      color: '#FFFFFF',
    },
  }),
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: theme.spacing.lg,
    right: theme.spacing.lg,
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm + 2,
    alignItems: 'center',
    zIndex: 9999,
    shadowColor: theme.colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 1,
    shadowRadius: 8,
    elevation: 8,
  },
  message: {
    fontFamily: theme.fonts.serif,
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
});
