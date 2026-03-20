import { Pressable, type PressableProps, StyleSheet, ViewStyle } from 'react-native';
import { InkText } from '@/components/ui/InkText';
import { theme } from '@/lib/theme';

type Props = PressableProps & {
  label: string;
  variant?: 'primary' | 'secondary' | 'ghost';
  block?: boolean;
};

export function InkButton({ label, variant = 'primary', block, style, ...props }: Props) {
  return (
    <Pressable
      {...props}
      style={({ pressed }) => [
        styles.base,
        block ? styles.block : null,
        variants[variant],
        pressed ? styles.pressed : null,
        style as ViewStyle,
      ]}>
      <InkText style={variant === 'primary' ? styles.primaryText : styles.secondaryText}>{label}</InkText>
    </Pressable>
  );
}

const variants = StyleSheet.create({
  primary: {
    backgroundColor: theme.colors.ink,
  },
  secondary: {
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  ghost: {
    backgroundColor: 'transparent',
  },
});

const styles = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: 14,
  },
  block: {
    width: '100%',
  },
  pressed: {
    opacity: 0.85,
  },
  primaryText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  secondaryText: {
    color: theme.colors.ink,
    fontWeight: '600',
  },
});
